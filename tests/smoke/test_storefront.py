"""HTTP smoke checks for the running KURANEA PrestaShop instance."""
from __future__ import annotations

import os
import re
import unittest
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit
from urllib.request import urlopen

BASE_URL = os.environ.get("SHOP_BASE_URL", "http://127.0.0.1:8080").rstrip("/")


class PageMetadata(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.html_lang = ""
        self.stylesheets: list[str] = []
        self.links: list[dict[str, str]] = []
        self.images: list[dict[str, str]] = []
        self.inputs: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        if tag == "html":
            self.html_lang = values.get("lang", "")
        if tag == "link" and "stylesheet" in values.get("rel", "").split():
            self.stylesheets.append(values.get("href", ""))
        if tag == "link":
            self.links.append(values)
        if tag == "img":
            self.images.append(values)
        if tag == "input":
            self.inputs.append(values)


def fetch(url: str) -> tuple[int, str, str]:
    with urlopen(url, timeout=20) as response:
        return response.status, response.geturl(), response.read().decode("utf-8", errors="replace")


class StorefrontSmokeTests(unittest.TestCase):
    def test_japanese_storefront_returns_200(self) -> None:
        status, final_url, body = fetch(f"{BASE_URL}/")
        metadata = PageMetadata()
        metadata.feed(body)
        self.assertEqual(status, 200)
        final = urlsplit(final_url)
        base = urlsplit(BASE_URL)
        self.assertIn(final.hostname, {base.hostname, "localhost"})
        self.assertEqual(final.port, base.port)
        self.assertTrue(metadata.html_lang.startswith("ja"), metadata.html_lang)
        self.assertIn("KURANEA", body)

    def test_kuranea_child_theme_css_is_served(self) -> None:
        status, final_url, body = fetch(f"{BASE_URL}/")
        self.assertEqual(status, 200)
        metadata = PageMetadata()
        metadata.feed(body)
        css_urls = [urljoin(final_url, href) for href in metadata.stylesheets if ".css" in href]
        self.assertTrue(css_urls, "no stylesheet link found")
        css = "\n".join(fetch(url)[2] for url in css_urls)
        self.assertIn("--kuranea-ink", css)
        self.assertIn(":focus-visible", css)
        self.assertIn(".container", css)

    def test_brand_logo_manifest_and_mobile_navigation_are_present(self) -> None:
        status, final_url, body = fetch(f"{BASE_URL}/")
        self.assertEqual(status, 200)
        metadata = PageMetadata()
        metadata.feed(body)
        logo = next((image for image in metadata.images if "kuranea-logo-desktop.png" in image.get("src", "")), None)
        self.assertIsNotNone(logo, "official desktop brand logo was not rendered")
        self.assertEqual(logo.get("alt"), "KURANEA クラネア")
        self.assertTrue(any(link.get("rel") == "manifest" for link in metadata.links), "web manifest link is missing")
        self.assertTrue(any(link.get("rel") == "apple-touch-icon" for link in metadata.links), "Apple touch icon is missing")
        self.assertIn("kuranea-mobile-nav", body)
        self.assertIn("kuranea-logo-mobile.webp", body)

    def test_admin_login_is_reachable(self) -> None:
        status, final_url, body = fetch(f"{BASE_URL}/admin-kuranea/")
        self.assertEqual(status, 200)
        self.assertIn("/admin-kuranea/login", final_url)
        self.assertGreaterEqual(len(re.findall(r'<input[^>]+type=[\"\'](?:email|password)', body)), 2)
        self.assertIn("KURANEA", body)


if __name__ == "__main__":
    unittest.main()
