"""Bounded raw-MIME checks shared by isolated customer email acceptance."""
from __future__ import annotations

import re
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser


MAX_RAW_MESSAGE_BYTES = 512 * 1024
_LOCALE_MARKERS = {
    "ja": {
        "account": ("アカウント", "登録"),
        "order_conf": ("注文",),
    },
    "en": {
        "account": ("account",),
        "order_conf": ("order",),
    },
    "ko": {
        "account": ("계정", "회원"),
        "order_conf": ("주문",),
    },
}


class MailpitMimeError(AssertionError):
    """A raw captured message failed one bounded MIME or locale check."""

    def __init__(self, reason: str) -> None:
        if reason not in {
            "raw_size_invalid",
            "mime_parse_failed",
            "html_part_missing",
            "html_part_ambiguous",
            "text_part_missing",
            "text_part_ambiguous",
            "mime_part_decode_failed",
            "locale_invalid",
            "template_invalid",
            "locale_marker_missing",
            "order_reference_missing",
        }:
            raise ValueError("unknown isolated mail acceptance result")
        self.reason = reason
        super().__init__("isolated native email did not satisfy its raw-MIME contract")


class _VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._excluded_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"head", "script", "style", "template", "svg"}:
            self._excluded_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"head", "script", "style", "template", "svg"} and self._excluded_depth:
            self._excluded_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._excluded_depth:
            self._parts.append(data)

    @property
    def text(self) -> str:
        return " ".join(" ".join(self._parts).split())


def parse_raw_mime_parts(source: bytes) -> tuple[str, str]:
    """Return the unique non-attachment HTML and plain-text bodies."""
    if not isinstance(source, bytes) or not source or len(source) > MAX_RAW_MESSAGE_BYTES:
        raise MailpitMimeError("raw_size_invalid")
    bodies: dict[str, list[str]] = {"html": [], "text": []}
    try:
        parsed = BytesParser(policy=policy.default).parsebytes(source)

        def collect(part) -> None:
            if part.get_content_disposition() == "attachment" or part.get_filename() is not None:
                return
            content_type = part.get_content_type().lower()
            if content_type in {"message/rfc822", "message/global", "message/delivery-status"}:
                return
            if part.is_multipart():
                for child in part.iter_parts():
                    collect(child)
                return
            key = "html" if content_type == "text/html" else "text" if content_type == "text/plain" else None
            if key:
                content = part.get_content()
                if not isinstance(content, str):
                    raise MailpitMimeError("mime_part_decode_failed")
                bodies[key].append(content)

        collect(parsed)
    except MailpitMimeError:
        raise
    except Exception:
        raise MailpitMimeError("mime_parse_failed") from None
    for key in ("html", "text"):
        if not bodies[key]:
            raise MailpitMimeError(f"{key}_part_missing")
        if len(bodies[key]) != 1:
            raise MailpitMimeError(f"{key}_part_ambiguous")
    return bodies["html"][0], bodies["text"][0]


def assert_native_mail_locale(
    language: str,
    template: str,
    html_body: str,
    text_body: str,
    order_reference: str | None = None,
) -> None:
    """Require localized visible content in both raw MIME bodies."""
    if language not in _LOCALE_MARKERS:
        raise MailpitMimeError("locale_invalid")
    if template not in {"account", "order_conf"}:
        raise MailpitMimeError("template_invalid")
    html_text = _VisibleText()
    try:
        html_text.feed(html_body)
        html_text.close()
    except Exception:
        raise MailpitMimeError("mime_parse_failed") from None
    visible_parts = (html_text.text, text_body)
    markers = _LOCALE_MARKERS[language][template]
    for body in visible_parts:
        without_urls = re.sub(r"https?://[^\s<>]+", " ", body, flags=re.IGNORECASE)
        normalized = without_urls.casefold()
        if not any(marker.casefold() in normalized for marker in markers):
            raise MailpitMimeError("locale_marker_missing")
        if order_reference is not None and order_reference not in body:
            raise MailpitMimeError("order_reference_missing")
