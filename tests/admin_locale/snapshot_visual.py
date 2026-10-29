#!/usr/bin/env python3
"""Render a sanitized native KernelBrowser HTML snapshot in isolated Chromium.

This is a visual renderer for already-produced server HTML, not an HTTP-route
acceptance test. It never opens the MBO/Facebook route and never permits a
browser request except to its own loopback preview server. That preview server
can fetch only allowlisted static GET assets from localhost:18081.
"""

from __future__ import annotations

import argparse
import base64
import html
import hashlib
from html.parser import HTMLParser
import http.client
import json
import os
from pathlib import Path
import re
import shutil
import stat
import struct
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from dataclasses import dataclass, field
from typing import Iterable
from urllib.parse import urljoin, urlsplit


APP_ORIGIN = "http://localhost:18081"
# PS 9.2.0 config.yml uses Core\Version::VERSION as the Symfony asset version;
# StaticVersionStrategy formats it as %s?%s. No runtime override is accepted.
REVIEWED_ASSET_VERSION = '9.2.0'
APP_DOCUMENT_BASE = APP_ORIGIN + "/admin-kuranea/index.php"
ASSET_PREFIX = "/asset"
MAX_HTML_BYTES = 8 * 1024 * 1024
MAX_ASSET_BYTES = 6 * 1024 * 1024
MAX_TOTAL_ASSET_BYTES = 24 * 1024 * 1024
MAX_ASSET_REQUESTS = 64
VIEWPORTS = (390, 1440)
VIEWPORT_HEIGHT = 1100

EXPECTED = {
    "mbo": {
        "target_id": None,
        "target_class": "error-header",
        "required_text": "Addons에 연결하는 데 문제가 있는 것 같습니다. 페이지를 새로고침하거나 방화벽 설정을 확인해 주세요.",
        "forbidden_text": "It looks like we have trouble connecting to Addons. Please refresh the page or check your firewall configuration.",
    },
    "facebook": {
        "target_id": "ordenowa-facebook-transport-error",
        "target_class": None,
        "required_text": "Facebook 계정 연결을 일시적으로 사용할 수 없습니다 Facebook 서비스에 연결하는 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.",
        "forbidden_text": "cURL error",
    },
}

ASSET_ROOTS = (
    "/admin-kuranea/themes/new-theme/public/",
    "/admin-kuranea/themes/default/public/",
    "/themes/new-theme/public/",
    "/themes/default/public/",
    "/js/jquery/plugins/fancybox/",
    "/js/jquery/plugins/chosen/",
    "/img/admin/",
    "/modules/ps_mbo/views/img/",
)
ASSET_MIME = {
    ".css": {"text/css"},
    ".woff": {"font/woff", "application/font-woff", "application/x-font-woff"},
    ".woff2": {"font/woff2", "application/font-woff2", "application/x-font-woff2"},
    ".ttf": {"font/ttf", "application/x-font-ttf", "application/octet-stream"},
    ".otf": {"font/otf", "application/x-font-opentype", "application/octet-stream"},
    ".svg": {"image/svg+xml"},
    ".png": {"image/png"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".webp": {"image/webp"},
    ".ico": {"image/x-icon", "image/vnd.microsoft.icon"},
}
ALLOWED_ASSET_EXTENSIONS = frozenset(ASSET_MIME)
ASSET_PATH_RE = re.compile(r"\A/[A-Za-z0-9_./-]{1,1024}\Z")
SAFE_ID_RE = re.compile(r"\A[A-Za-z][A-Za-z0-9_-]{0,100}\Z")
SAFE_CLASS_TOKEN_RE = re.compile(r"\A[A-Za-z_][A-Za-z0-9_-]{0,80}\Z")
PRIVATE_TITLE_RE = re.compile(
    r"(?:[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}|https?://|\btoken\s*[=:]|\b[A-F0-9]{32,}\b)",
    re.IGNORECASE,
)
CSS_ONLY_ROOTS = ("/js/jquery/plugins/fancybox/", "/js/jquery/plugins/chosen/")
ALLOWED_TAGS_DROP = frozenset({"script", "iframe", "frame", "object", "embed", "applet", "noscript"})
VOID_TAGS = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"})


class SnapshotError(ValueError):
    """A fixed, safe-to-report snapshot validation failure."""


@dataclass
class Node:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list["Node | str"] = field(default_factory=list)

    def get(self, name: str, default: str = "") -> str:
        return self.attrs.get(name.lower(), default)


class _TreeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("#document")
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized: dict[str, str] = {}
        for key, value in attrs:
            key = key.lower()
            if key in normalized:
                raise SnapshotError("duplicate_html_attribute")
            normalized[key] = "" if value is None else value
        node = Node(tag.lower(), normalized)
        self.stack[-1].children.append(node)
        if node.tag not in VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag.lower() not in VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return

    def handle_data(self, data: str) -> None:
        if data:
            self.stack[-1].children.append(data)


def parse_html(source: str) -> Node:
    parser = _TreeParser()
    try:
        parser.feed(source)
        parser.close()
    except SnapshotError:
        raise
    except Exception as error:
        raise SnapshotError("html_parse_failed") from error
    return parser.root


def _walk(node: Node) -> Iterable[Node]:
    yield node
    for child in node.children:
        if isinstance(child, Node):
            yield from _walk(child)


def _has_class(node: Node, name: str) -> bool:
    return name in node.get("class").split()


def _find_all(node: Node, *, tag: str | None = None, element_id: str | None = None, class_name: str | None = None) -> list[Node]:
    found = []
    for child in _walk(node):
        if tag is not None and child.tag != tag:
            continue
        if element_id is not None and child.get("id") != element_id:
            continue
        if class_name is not None and not _has_class(child, class_name):
            continue
        found.append(child)
    return found


def _text(node: Node) -> str:
    pieces: list[str] = []
    for child in node.children:
        if isinstance(child, str):
            pieces.append(child)
        else:
            pieces.append(_text(child))
    return " ".join(" ".join(pieces).split())


def _parent_path(root: Node, target: Node) -> list[Node] | None:
    def visit(node: Node, path: list[Node]) -> list[Node] | None:
        if node is target:
            return path + [node]
        for child in node.children:
            if isinstance(child, Node):
                result = visit(child, path + [node])
                if result is not None:
                    return result
        return None
    return visit(root, [])


def _clone_branch(root: Node, target: Node) -> Node:
    path = _parent_path(root, target)
    if not path:
        raise SnapshotError("selected_node_outside_document")
    clone = Node(path[0].tag, dict(path[0].attrs))
    cursor = clone
    for source in path[1:]:
        next_node = Node(source.tag, dict(source.attrs))
        cursor.children.append(next_node)
        cursor = next_node
    cursor.children = _clone_full(target).children
    return clone


def _clone_full(node: Node) -> Node:
    return Node(node.tag, dict(node.attrs), [(_clone_full(child) if isinstance(child, Node) else child) for child in node.children])


def normalize_asset_url(raw_url: str, *, document_base: str = APP_DOCUMENT_BASE) -> tuple[str, str]:
    """Return (upstream path, extension) for one safe same-origin static asset."""
    if not raw_url or len(raw_url) > 2048 or any(ord(ch) < 0x20 for ch in raw_url):
        raise SnapshotError("invalid_asset_url")
    absolute = urljoin(document_base, raw_url)
    parts = urlsplit(absolute)
    if (parts.scheme != "http" or parts.hostname != "localhost" or parts.port != 18081
            or parts.username is not None or parts.password is not None
            or parts.query not in ('', REVIEWED_ASSET_VERSION) or parts.fragment or "%" in parts.path):
        raise SnapshotError("asset_origin_or_query_rejected")
    path = parts.path
    if not ASSET_PATH_RE.fullmatch(path) or "//" in path or any(seg in {".", "..", ""} for seg in path.split("/")[1:]):
        raise SnapshotError("asset_path_rejected")
    ext = Path(path).suffix.lower()
    if ext not in ALLOWED_ASSET_EXTENSIONS or not any(path.startswith(root) for root in ASSET_ROOTS):
        raise SnapshotError("asset_path_rejected")
    if any(path.startswith(root) for root in CSS_ONLY_ROOTS) and ext != ".css":
        raise SnapshotError("asset_type_rejected")
    return path, ext


def _stylesheet_nodes(head: Node) -> list[Node]:
    styles: list[Node] = []
    for node in _find_all(head, tag="link"):
        rel = {part.lower() for part in node.get("rel").split()}
        if "stylesheet" in rel:
            styles.append(node)
    if not styles:
        raise SnapshotError("stylesheet_missing")
    return styles


def _find_card(node: Node, kind: str) -> tuple[Node, Node, Node]:
    expected = EXPECTED[kind]
    if kind == "mbo":
        markers = _find_all(node, tag="p", class_name="error-header")
    else:
        markers = _find_all(node, element_id=expected["target_id"])
    if len(markers) != 1:
        raise SnapshotError("error_marker_cardinality")
    marker = markers[0]
    marker_text = _text(marker)
    required = expected["required_text"]
    if marker_text != required:
        raise SnapshotError("error_copy_mismatch")
    if expected["forbidden_text"] and expected["forbidden_text"] in _text(node):
        raise SnapshotError("forbidden_error_copy_present")
    current = marker
    card = None
    row = None
    while current is not node:
        if _has_class(current, "card"):
            card = current
        if _has_class(current, "row"):
            row = current
        path = _parent_path(node, current)
        if not path or len(path) < 2:
            break
        current = path[-2]
        if card is not None and row is not None:
            break
    if card is None or row is None:
        raise SnapshotError("error_card_structure_mismatch")
    if _text(card) != required:
        raise SnapshotError("error_card_unexpected_text")
    return marker, card, row


def _copy_safe_node(node: Node, asset_paths: set[str]) -> Node | None:
    if node.tag in ALLOWED_TAGS_DROP or node.tag in {"form", "input", "textarea", "select", "option", "button", "style", "meta", "base"}:
        return None
    if node.get("id") == "header-employee-container" or node.get("class").split() and "employee-dropdown" in node.get("class").split():
        return None
    attrs: dict[str, str] = {}
    for key, value in node.attrs.items():
        if key.startswith("on") or key in {"href", "action", "formaction", "formtarget", "target", "srcset", "poster", "style", "title", "alt", "value", "data-token", "data-base-url"} or key.startswith("data-"):
            continue
        if key in {"src", "xlink:href"}:
            if node.tag != "img" or key != "src":
                continue
            path, _ext = normalize_asset_url(value)
            asset_paths.add(path)
            attrs["src"] = ASSET_PREFIX + path
            continue
        # Keep only geometry/semantic attributes that do not encode URLs or identity.
        if key == "id":
            if not SAFE_ID_RE.fullmatch(value):
                raise SnapshotError("unsafe_dom_identifier")
            attrs[key] = value
        elif key == "class":
            classes = value.split()
            if len(classes) > 40 or any(not SAFE_CLASS_TOKEN_RE.fullmatch(token) for token in classes):
                raise SnapshotError("unsafe_dom_class")
            attrs[key] = " ".join(classes)
        elif key == "role" and value in {"alert", "status", "region", "presentation"}:
            attrs[key] = value
        elif key == "aria-live" and value in {"off", "polite", "assertive"}:
            attrs[key] = value
        elif key == "aria-hidden" and value in {"true", "false"}:
            attrs[key] = value
        elif key == "aria-current" and value in {"page", "step", "location", "date", "time", "true", "false"}:
            attrs[key] = value
        elif key == "dir" and value in {"ltr", "rtl", "auto"}:
            attrs[key] = value
        elif key == "lang" and value.lower() in {"ko", "ko-kr"}:
            attrs[key] = value.lower()
    if node.tag == "link":
        rel = {part.lower() for part in node.get("rel").split()}
        if "stylesheet" not in rel:
            return None
        path, _ext = normalize_asset_url(node.get("href"))
        asset_paths.add(path)
        attrs = {"rel": "stylesheet", "href": ASSET_PREFIX + path, "media": "all"}
    copied = Node(node.tag, attrs)
    for child in node.children:
        if isinstance(child, str):
            copied.children.append(child)
        else:
            safe_child = _copy_safe_node(child, asset_paths)
            if safe_child is not None:
                copied.children.append(safe_child)
    return copied


def _serialize(node: Node) -> str:
    if node.tag == "#document":
        return "".join(_serialize(child) if isinstance(child, Node) else html.escape(child, quote=False) for child in node.children)
    attrs = "".join(f' {key}="{html.escape(value, quote=True)}"' for key, value in node.attrs.items())
    if node.tag in VOID_TAGS:
        return f"<{node.tag}{attrs}>"
    body = "".join(_serialize(child) if isinstance(child, Node) else html.escape(child, quote=False) for child in node.children)
    return f"<{node.tag}{attrs}>{body}</{node.tag}>"


@dataclass(frozen=True)
class SafeSnapshot:
    html: str
    asset_paths: frozenset[str]
    kind: str


def sanitize_snapshot(source_bytes: bytes, kind: str) -> SafeSnapshot:
    if kind not in EXPECTED:
        raise SnapshotError("kind_invalid")
    if not isinstance(source_bytes, bytes) or not source_bytes or len(source_bytes) > MAX_HTML_BYTES:
        raise SnapshotError("private_snapshot_size_invalid")
    try:
        source = source_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise SnapshotError("private_snapshot_encoding_invalid") from error
    root = parse_html(source)
    html_nodes = _find_all(root, tag="html")
    heads = _find_all(root, tag="head")
    bodies = _find_all(root, tag="body")
    if len(html_nodes) != 1 or len(heads) != 1 or len(bodies) != 1:
        raise SnapshotError("native_document_structure_invalid")
    html_node, head, body = html_nodes[0], heads[0], bodies[0]
    if not re.match(r"\Ako(?:[-_]\w+)?\Z", html_node.get("lang"), re.IGNORECASE):
        raise SnapshotError("korean_document_language_missing")
    toolbars = _find_all(body, tag="div", class_name="header-toolbar")
    main_divs = _find_all(body, element_id="main-div")
    content_divs = _find_all(body, tag="div", class_name="content-div")
    if len(toolbars) != 1 or len(main_divs) != 1 or len(content_divs) != 1:
        raise SnapshotError("native_toolbar_structure_invalid")
    titles = _find_all(toolbars[0], tag="h1", class_name="title")
    title_text = _text(titles[0]) if len(titles) == 1 else ""
    if not title_text or len(title_text) > 120 or PRIVATE_TITLE_RE.search(title_text):
        raise SnapshotError("native_toolbar_structure_invalid")
    if content_divs[0] not in _walk(main_divs[0]):
        raise SnapshotError("native_content_outside_main")
    _marker, error_card, _error_row = _find_card(body, kind)
    if error_card not in _walk(content_divs[0]):
        raise SnapshotError("error_card_outside_native_content")

    asset_paths: set[str] = set()
    safe_head = Node("head", children=[Node("meta", {"charset": "utf-8"})])
    for link in _stylesheet_nodes(head):
        safe_link = _copy_safe_node(link, asset_paths)
        if safe_link is not None:
            safe_head.children.append(safe_link)
    # Preserve the native wrappers around the page heading, while excluding
    # toolbar actions, account controls, links, and unrelated text.
    safe_toolbar_branch = _clone_branch(toolbars[0], titles[0])
    safe_toolbar = _copy_safe_node(safe_toolbar_branch, asset_paths)
    # Preserve the real row/column/card ancestry but omit every sibling in the
    # row, which can otherwise contain page- or employee-specific text.
    safe_main_branch = _clone_branch(main_divs[0], error_card)
    safe_main = _copy_safe_node(safe_main_branch, asset_paths)
    body_class = body.get("class")
    safe_body_attrs: dict[str, str] = {}
    if body_class:
        classes = body_class.split()
        if len(classes) > 40 or any(not SAFE_CLASS_TOKEN_RE.fullmatch(token) for token in classes):
            raise SnapshotError("unsafe_body_class")
        safe_body_attrs["class"] = " ".join(classes)
    safe_body = Node("body", safe_body_attrs)
    if safe_toolbar is None or safe_main is None:
        raise SnapshotError("native_visual_branch_invalid")
    safe_body.children.extend([safe_toolbar, safe_main])
    safe_html = Node("html", {"lang": "ko"}, [safe_head, safe_body])
    output = "<!doctype html>" + _serialize(safe_html)
    if any(secret in output for secret in ("data-token", "data-base-url", "<script", "<form", "<iframe", "onerror=")):
        raise SnapshotError("sanitized_dom_contains_active_or_secret_fields")
    if not asset_paths:
        raise SnapshotError("static_assets_missing")
    return SafeSnapshot(output, frozenset(asset_paths), kind)


def _expected_mime(path: str) -> set[str]:
    ext = Path(path).suffix.lower()
    return ASSET_MIME.get(ext, set())


class _PreviewHandler(BaseHTTPRequestHandler):
    server_version = "ORDENOWA-Static-Visual-Preview"
    sys_version = ""

    def log_message(self, _format: str, *args: object) -> None:
        # Never log request URLs or payloads; the caller receives aggregate counts only.
        return

    @property
    def config(self) -> "_PreviewServer":
        return self.server  # type: ignore[return-value]

    def do_POST(self) -> None:
        self.config.mutation_attempts += 1
        self.send_error(405)

    def do_PUT(self) -> None:
        self.config.mutation_attempts += 1
        self.send_error(405)

    def do_DELETE(self) -> None:
        self.config.mutation_attempts += 1
        self.send_error(405)

    def do_GET(self) -> None:
        parts = urlsplit(self.path)
        if parts.query or parts.fragment:
            self.config.blocked_asset_requests += 1
            self.send_error(404)
            return
        if parts.path == "/":
            payload = self.config.snapshot.html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", self.config.csp)
            self.end_headers()
            self.wfile.write(payload)
            return
        if parts.path == "/favicon.ico":
            self.send_response(204)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        if parts.path.startswith(ASSET_PREFIX + "/"):
            asset_path = parts.path[len(ASSET_PREFIX):]
        elif any(parts.path.startswith(root) for root in ASSET_ROOTS):
            # Some upstream CSS uses root-relative static URLs. Serve those
            # only when the exact path still passes the same static allowlist.
            asset_path = parts.path
        else:
            self.config.blocked_asset_requests += 1
            self.send_error(404)
            return
        try:
            data, mime = fetch_static_asset(asset_path)
        except SnapshotError:
            self.config.blocked_asset_requests += 1
            self.send_error(404)
            return
        self.config.asset_requests += 1
        self.config.asset_bytes += len(data)
        if self.config.asset_requests > MAX_ASSET_REQUESTS or self.config.asset_bytes > MAX_TOTAL_ASSET_BYTES:
            self.config.blocked_asset_requests += 1
            self.send_error(413)
            return
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)


class _PreviewServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, snapshot: SafeSnapshot):
        self.snapshot = snapshot
        self.asset_requests = 0
        self.asset_bytes = 0
        self.blocked_asset_requests = 0
        self.mutation_attempts = 0
        super().__init__(("127.0.0.1", 0), _PreviewHandler)
        self.csp = (
            "default-src 'none'; "
            "img-src 'self'; style-src 'self'; font-src 'self'; "
            "script-src 'none'; connect-src 'none'; form-action 'none'; "
            "frame-src 'none'; object-src 'none'; base-uri 'none'; "
            "worker-src 'none'; manifest-src 'none'"
        )
        self.url = f"http://127.0.0.1:{self.server_port}/"


def fetch_static_asset(path: str) -> tuple[bytes, str]:
    if not ASSET_PATH_RE.fullmatch(path) or "?" in path or "#" in path or "%" in path or ".." in path.split("/"):
        raise SnapshotError("asset_path_rejected")
    if not any(path.startswith(root) for root in ASSET_ROOTS):
        raise SnapshotError("asset_path_rejected")
    ext = Path(path).suffix.lower()
    allowed_mime = _expected_mime(path)
    if ext not in ALLOWED_ASSET_EXTENSIONS or not allowed_mime:
        raise SnapshotError("asset_type_rejected")
    if any(path.startswith(root) for root in CSS_ONLY_ROOTS) and ext != ".css":
        raise SnapshotError("asset_type_rejected")
    connection = http.client.HTTPConnection("localhost", 18081, timeout=5)
    try:
        connection.request("GET", path, headers={"Host": "localhost:18081", "Accept": ", ".join(sorted(allowed_mime)), "Connection": "close"})
        response = connection.getresponse()
        if response.status != 200 or response.getheader("Location"):
            raise SnapshotError("static_asset_fetch_failed")
        mime = (response.getheader("Content-Type") or "").split(";", 1)[0].strip().lower()
        if mime not in allowed_mime:
            raise SnapshotError("static_asset_mime_mismatch")
        data = response.read(MAX_ASSET_BYTES + 1)
        if len(data) > MAX_ASSET_BYTES:
            raise SnapshotError("static_asset_size_limit")
        return data, mime
    except SnapshotError:
        raise
    except Exception as error:
        raise SnapshotError("static_asset_fetch_failed") from error
    finally:
        connection.close()


def _png_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 24 or not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise SnapshotError("screenshot_png_invalid")
    width, height = struct.unpack("!II", data[16:24])
    if not 1 <= width <= 4096 or not 1 <= height <= 4096:
        raise SnapshotError("screenshot_dimensions_invalid")
    return width, height


def _validate_private_paths(private_html: Path, private_dir: Path, artifact_dir: Path, runner_temp: Path) -> tuple[Path, Path, Path, Path]:
    if private_html.is_symlink() or private_dir.is_symlink() or artifact_dir.is_symlink() or runner_temp.is_symlink():
        raise SnapshotError("path_symlink_rejected")
    try:
        private_dir_real = private_dir.resolve(strict=True)
        runner_real = runner_temp.resolve(strict=True)
        artifact_real = artifact_dir.resolve(strict=True)
        private_real = private_html.resolve(strict=True)
    except OSError as error:
        raise SnapshotError("path_unavailable") from error
    if not private_real.is_file() or private_real.parent != private_dir_real:
        raise SnapshotError("private_input_scope_invalid")
    if not artifact_real.is_dir() or not runner_real.is_dir():
        raise SnapshotError("artifact_path_invalid")
    if runner_real not in artifact_real.parents or runner_real not in private_dir_real.parents:
        raise SnapshotError("path_outside_runner_temp")
    mode = stat.S_IMODE(private_real.stat().st_mode)
    if os.name == "posix" and mode & 0o077:
        raise SnapshotError("private_input_permissions_invalid")
    if private_real.stat().st_size > MAX_HTML_BYTES:
        raise SnapshotError("private_snapshot_size_invalid")
    return private_real, private_dir_real, artifact_real, runner_real


def _safe_write(path: Path, payload: bytes) -> None:
    if path.exists() or path.is_symlink():
        raise SnapshotError("output_already_exists")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd: int | None = None
    try:
        fd = os.open(path, flags, 0o600)
        with os.fdopen(fd, "wb") as stream:
            fd = None
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        if fd is not None:
            os.close(fd)
        path.unlink(missing_ok=True)
        raise


_CAPTURE_STATE_SCRIPT = r"""
  const kind=arguments[0];
  const done=arguments[arguments.length-1];
  Promise.all([document.fonts.ready, ...Array.from(document.images, image => image.decode().catch(() => false))]).then(() => {
    const toolbar=document.querySelector('.header-toolbar');
    const title=toolbar?.querySelector('h1.title');
    const main=document.querySelector('#main-div');
    const content=document.querySelector('#main-div .content-div');
    const card=kind === 'mbo' ? document.querySelector('.error-header')?.closest('.card')
      : document.querySelector('#ordenowa-facebook-transport-error')?.closest('.card');
    const marker=kind === 'mbo' ? document.querySelector('.error-header')
      : document.querySelector('#ordenowa-facebook-transport-error');
    const text=(marker?.innerText ?? marker?.textContent ?? '').replace(/\s+/g,' ').trim();
    const expected=kind === 'mbo'
      ? 'Addons에 연결하는 데 문제가 있는 것 같습니다. 페이지를 새로고침하거나 방화벽 설정을 확인해 주세요.'
      : 'Facebook 계정 연결을 일시적으로 사용할 수 없습니다 Facebook 서비스에 연결하는 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.';
    const rect=(node)=>{const r=node?.getBoundingClientRect();return r?{x:r.x,y:r.y,right:r.right,bottom:r.bottom,width:r.width,height:r.height}:null;};
    done({ok:!!toolbar&&!!title&&!!main&&!!content&&!!card&&!!marker&&text===expected
          && document.documentElement.lang.toLowerCase().startsWith('ko')
          && !document.body.hasAttribute('data-token')
          && !Array.from(document.querySelectorAll('script,form,iframe')).length
          && document.documentElement.scrollWidth<=innerWidth+1
          && Array.from(document.images).every(image=>image.complete&&image.naturalWidth>0),
      toolbar:rect(toolbar),main:rect(main),card:rect(card),
      viewport:{width:innerWidth,height:innerHeight},scrollWidth:document.documentElement.scrollWidth,
      titlePresent:!!title&&!!title.textContent.trim(),expectedCopy:text===expected});
  }).catch(() => done({ok:false}));
"""


def _capture_viewport(driver: object, width: int, kind: str) -> tuple[bytes, dict[str, int]]:
    driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {
        "width": width, "height": VIEWPORT_HEIGHT, "deviceScaleFactor": 1, "mobile": False,
    })
    driver.execute_cdp_cmd("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": "light"}]})
    driver.get(driver._ordenowa_preview_url)
    state = driver.execute_async_script(_CAPTURE_STATE_SCRIPT, kind)
    if not isinstance(state, dict) or state.get("ok") is not True:
        raise SnapshotError("browser_visual_assertion_failed")
    toolbar = state.get("toolbar")
    main = state.get("main")
    card = state.get("card")
    view = state.get("viewport")
    if not all(isinstance(obj, dict) for obj in (toolbar, main, card, view)):
        raise SnapshotError("browser_geometry_unavailable")
    scroll_to = max(0, float(toolbar["y"]) + float(driver.execute_script("return window.scrollY")))
    driver.execute_script("window.scrollTo(0, arguments[0])", scroll_to)
    geometry = driver.execute_script("""
      const t=document.querySelector('.header-toolbar').getBoundingClientRect();
      const c=(arguments[0]==='mbo'?document.querySelector('.error-header')?.closest('.card'):
        document.querySelector('#ordenowa-facebook-transport-error')?.closest('.card')).getBoundingClientRect();
      return {x:Math.floor(Math.min(t.left,c.left)), y:Math.floor(t.top),
        right:Math.ceil(Math.max(t.right,c.right)), bottom:Math.ceil(c.bottom),
        viewportWidth:innerWidth, viewportHeight:innerHeight};
    """, kind)
    if not isinstance(geometry, dict):
        raise SnapshotError("browser_geometry_unavailable")
    x = int(geometry["x"])
    y = int(geometry["y"])
    crop_width = int(geometry["right"]) - x
    crop_height = int(geometry["bottom"]) - y
    if (crop_width < 320 or crop_height < 100 or crop_width > width
            or crop_height > VIEWPORT_HEIGHT or x < 0 or y < 0
            or geometry["right"] > geometry["viewportWidth"]
            or geometry["bottom"] > geometry["viewportHeight"]):
        raise SnapshotError("native_error_crop_out_of_viewport")
    result = driver.execute_cdp_cmd("Page.captureScreenshot", {
        "format": "png", "fromSurface": True, "captureBeyondViewport": False,
        "clip": {"x": x, "y": y, "width": crop_width, "height": crop_height, "scale": 1},
    })
    data = result.get("data") if isinstance(result, dict) else None
    if not isinstance(data, str):
        raise SnapshotError("screenshot_capture_failed")
    try:
        image = base64.b64decode(data, validate=True)
    except ValueError as error:
        raise SnapshotError("screenshot_png_invalid") from error
    image_width, image_height = _png_dimensions(image)
    if abs(image_width - crop_width) > 2 or abs(image_height - crop_height) > 2:
        raise SnapshotError("screenshot_crop_dimensions_mismatch")
    return image, {"viewport_width": width, "viewport_height": VIEWPORT_HEIGHT,
                   "png_width": image_width, "png_height": image_height}


def _network_audit(driver: object, expected_origin: str) -> None:
    try:
        entries = driver.get_log("performance")
    except Exception as error:
        raise SnapshotError("browser_network_audit_unavailable") from error
    for entry in entries:
        try:
            message = json.loads(entry["message"])["message"]
        except Exception:
            continue
        if message.get("method") != "Network.requestWillBeSent":
            continue
        params = message.get("params", {})
        request = params.get("request", {})
        url = request.get("url", "")
        method = request.get("method", "")
        if not isinstance(url, str) or not url.startswith(expected_origin + "/") or method != "GET" or "?" in url or "#" in url:
            raise SnapshotError("browser_network_policy_violation")


def render_private_snapshot(private_html: Path, private_dir: Path, artifact_dir: Path, runner_temp: Path, kind: str, expected_sha256: str) -> dict[str, object]:
    input_path, _private_root, output_root, _runner_root = _validate_private_paths(private_html, private_dir, artifact_dir, runner_temp)
    try:
        source_bytes = input_path.read_bytes()
    except OSError as error:
        raise SnapshotError("private_input_read_failed") from error
    finally:
        # The one-shot snapshot contains a native CSRF token and ephemeral
        # employee context. Keep it private and consume it exactly once.
        input_path.unlink(missing_ok=True)
    if re.fullmatch(r'[0-9a-f]{64}', expected_sha256) is None or hashlib.sha256(source_bytes).hexdigest() != expected_sha256:
        raise SnapshotError('native_response_snapshot_hash_mismatch')
    snapshot = sanitize_snapshot(source_bytes, kind)
    del source_bytes

    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
    except Exception as error:
        raise SnapshotError("selenium_unavailable") from error
    chromedriver = shutil.which("chromedriver")
    if not chromedriver:
        raise SnapshotError("chromedriver_unavailable")

    outputs: list[Path] = []
    captures: list[dict[str, int]] = []
    summary_path = output_root / f"{kind}-native-kernelbrowser-snapshot.json"
    expected_png_paths = [output_root / f"{kind}-native-kernelbrowser-snapshot-redacted-{width}.png" for width in VIEWPORTS]
    if summary_path.exists() or summary_path.is_symlink() or any(path.exists() or path.is_symlink() for path in expected_png_paths):
        raise SnapshotError("output_already_exists")
    driver = None
    profile_dir: Path | None = None
    server = _PreviewServer(snapshot)
    server_thread = threading.Thread(target=server.serve_forever, name="ordenowa-static-preview", daemon=True)
    try:
        server_thread.start()
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-background-networking")
        options.add_argument("--disable-sync")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-default-apps")
        options.add_argument("--metrics-recording-only")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        options.add_argument("--force-color-profile=srgb")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        profile_dir = Path(tempfile.mkdtemp(prefix="ordenowa-visual-chrome-", dir=str(private_dir)))
        profile_dir.chmod(0o700)
        options.add_argument("--user-data-dir=" + str(profile_dir))
        options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
        service = Service(executable_path=chromedriver, log_output=os.devnull)
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(20)
        driver.set_script_timeout(15)
        driver._ordenowa_preview_url = server.url
        for width in VIEWPORTS:
            image, dimensions = _capture_viewport(driver, width, kind)
            filename = f"{kind}-native-kernelbrowser-snapshot-redacted-{width}.png"
            destination = output_root / filename
            _safe_write(destination, image)
            outputs.append(destination)
            dimensions["assets_fetched"] = server.asset_requests
            dimensions["blocked_asset_requests"] = server.blocked_asset_requests
            dimensions["mutation_attempts"] = server.mutation_attempts
            _network_audit(driver, server.url.rstrip("/"))
            if server.blocked_asset_requests or server.mutation_attempts:
                raise SnapshotError("preview_policy_violation")
            captures.append(dimensions)
    except SnapshotError:
        for path in outputs:
            path.unlink(missing_ok=True)
        raise
    except Exception as error:
        for path in outputs:
            path.unlink(missing_ok=True)
        raise SnapshotError("chromium_render_failed") from error
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=5)
        if profile_dir is not None:
            shutil.rmtree(profile_dir, ignore_errors=True)

    result: dict[str, object] = {
        "schema": 1,
        "passed": True,
        "kind": kind,
        "native_response_snapshot_sha256": expected_sha256,
        "render_scope": "chromium_render_of_native_kernelbrowser_snapshot",
        "network_policy": "loopback_preview_and_localhost_18081_static_get_allowlist",
        "page_scripts_allowed": False,
        "forms_enabled": False,
        "frames_enabled": False,
        "raw_html_uploaded": False,
        "external_network_attempts": 0,
        "mutation_attempts": server.mutation_attempts,
        "blocked_asset_requests": server.blocked_asset_requests,
        "asset_requests": server.asset_requests,
        "captures": captures,
    }
    try:
        _safe_write(summary_path, (json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"))
    except Exception:
        for path in outputs:
            path.unlink(missing_ok=True)
        raise
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", required=True, choices=tuple(EXPECTED))
    parser.add_argument("--private-html", required=True, type=Path)
    parser.add_argument("--private-dir", required=True, type=Path)
    parser.add_argument("--artifact-dir", required=True, type=Path)
    parser.add_argument("--runner-temp", required=True, type=Path)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = render_private_snapshot(args.private_html, args.private_dir, args.artifact_dir, args.runner_temp, args.kind, args.expected_sha256)
    except SnapshotError as error:
        safe = {"schema": 1, "passed": False, "kind": args.kind, "failure_code": str(error)}
        print(json.dumps(safe, sort_keys=True, separators=(",", ":")))
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
