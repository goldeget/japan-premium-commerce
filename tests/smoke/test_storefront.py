"""HTTP smoke checks for the ORDENOWA PrestaShop instance."""
from __future__ import annotations

import os
import json
import re
import html
import unittest
from html.parser import HTMLParser
from urllib.parse import quote, urlencode, urljoin, urlsplit, urlunsplit
from urllib.error import HTTPError
from urllib.request import urlopen

BASE_URL = os.environ.get("SHOP_BASE_URL", "http://localhost:8080").rstrip("/")


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


class SearchFormParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.forms: list[dict[str, object]] = []
        self.current: dict[str, object] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        if tag == "form":
            self.current = {"action": values.get("action", ""), "inputs": []}
        elif tag == "input" and self.current is not None:
            inputs = self.current["inputs"]
            assert isinstance(inputs, list)
            inputs.append(values)

    def handle_endtag(self, tag: str) -> None:
        if tag == "form" and self.current is not None:
            self.forms.append(self.current)
            self.current = None


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
        self.assertIn("ORDENOWA", body)
        self.assertIn("企業と商品をつなぐ、次世代のB2B調達プラットフォーム", body)
        self.assertNotIn("KURANEA", body)
        css_urls = [urljoin(final_url, href) for href in metadata.stylesheets if ".css" in href]
        css = "\n".join(fetch(url)[2] for url in css_urls)
        self.assertIn('.page-index .ps-imageslider:has(img[src*="/sample-"])', css)
        self.assertIn(".page-index .ps-customtext:has(strong.dark)", css)
        self.assertIn('.page-index .ps-banner:has(img[src*="/sale70.png"])', css)

    def test_homepage_copy_and_mobile_navigation_follow_store_locale(self) -> None:
        cases = (
            ("/", "ja-JP", "企業と商品をつなぐ、次世代のB2B調達プラットフォーム", "ただいま、セレクションを準備しています。", "ホーム", "検索", "マイページ", "カート"),
            ("/en/", "en-US", "A next-generation B2B procurement platform connecting businesses and products", "We're preparing our first collection.", "Home", "Search", "Account", "Cart"),
            ("/ko/", "ko-KR", "기업과 상품을 연결하는 차세대 B2B 조달 플랫폼", "첫 컬렉션을 준비하고 있습니다.", "홈", "검색", "내 계정", "장바구니"),
        )
        for path, language, title, empty_copy, *navigation in cases:
            with self.subTest(path=path):
                status, _, body = fetch(f"{BASE_URL}{path}")
                metadata = PageMetadata()
                metadata.feed(body)
                self.assertEqual(status, 200)
                self.assertEqual(metadata.html_lang, language)
                self.assertIn(title, body)
                self.assertIn(empty_copy, body)
                for label in navigation:
                    self.assertIn(f">{label}<", body)

    def test_search_placeholder_follows_store_locale(self) -> None:
        cases = (
            ("/", "商品名・キーワードで検索"),
            ("/en/", "Search products..."),
            ("/ko/", "상품명 또는 키워드 검색"),
        )
        for path, expected_placeholder in cases:
            with self.subTest(path=path):
                status, _, body = fetch(f"{BASE_URL}{path}")
                metadata = PageMetadata()
                metadata.feed(body)
                self.assertEqual(status, 200)
                search = next((item for item in metadata.inputs if item.get("name") == "s"), None)
                self.assertIsNotNone(search, "Hummingbird search input is missing")
                self.assertEqual(search.get("placeholder"), expected_placeholder)

    def test_search_empty_state_uses_store_locale(self) -> None:
        cases = (
            ("/", "ja-JP", "商品は見つかりませんでした", "トップページへ戻る"),
            ("/en/", "en-US", "No search results for", "Back to home"),
            ("/ko/", "ko-KR", "검색 결과가 없습니다", "홈으로 돌아가기"),
        )
        for path, language, title, back_label in cases:
            with self.subTest(path=path):
                status, home_url, home = fetch(f"{BASE_URL}{path}")
                self.assertEqual(status, 200)
                parser = SearchFormParser()
                parser.feed(home)
                search_form = next(
                    (
                        form
                        for form in parser.forms
                        if any(item.get("name") == "s" for item in form["inputs"])
                    ),
                    None,
                )
                self.assertIsNotNone(search_form, "store search form is missing")
                search_url = urljoin(home_url, str(search_form["action"]))
                parts = urlsplit(search_url)
                search_path = quote(parts.path, safe="/%:@")
                search_url = urlunsplit((parts.scheme, parts.netloc, search_path, "", ""))
                status, final_url, body = fetch(
                    f"{search_url}?{urlencode({'controller': 'search', 's': 'kuranea-empty-state-qa'})}"
                )
                metadata = PageMetadata()
                metadata.feed(body)
                self.assertEqual(status, 200, final_url)
                self.assertEqual(metadata.html_lang, language)
                self.assertIn(title, body)
                self.assertIn(back_label, body)
                if language == "en-US":
                    self.assertIn("We couldn't find any matching products.", body)
                else:
                    self.assertNotIn("We couldn't find any matching products.", body)

    def test_empty_category_state_uses_store_locale(self) -> None:
        cases = (
            ("/2-home", "ja-JP", "現在、商品を掲載していません。", "ホームへ戻る"),
            ("/en/2-home", "en-US", "No products available at the moment", "Back to Home page"),
            ("/ko/2-home", "ko-KR", "현재 판매할 상품을 준비하고 있습니다.", "홈으로 돌아가기"),
        )
        for path, language, empty_copy, home_label in cases:
            with self.subTest(path=path):
                status, final_url, body = fetch(f"{BASE_URL}{path}")
                metadata = PageMetadata()
                metadata.feed(body)
                self.assertEqual(status, 200, final_url)
                self.assertEqual(metadata.html_lang, language)
                self.assertIn(empty_copy, body)
                self.assertIn(home_label, body)
                if language != "en-US":
                    self.assertNotIn("No products available at the moment", body)
                    self.assertNotIn("Back to Home page", body)

    def test_japanese_footer_links_have_japanese_accessible_text(self) -> None:
        status, _, body = fetch(f"{BASE_URL}/")
        self.assertEqual(status, 200)
        footer_match = re.search(r'<footer id="footer".*?</footer>', body, re.DOTALL)
        self.assertIsNotNone(footer_match, "store footer is missing")
        footer = html.unescape(footer_match.group(0))
        footer_text = " ".join(re.sub(r"<[^>]+>", " ", footer).split())

        for expected in (
            "値下げ商品",
            "新着商品",
            "ベストセラー",
            "人気商品一覧",
            "注文状況の確認",
            "商品リンクを開閉",
            "会社情報リンクを開閉",
            "アカウントリンクを開閉",
            "店舗情報を開閉",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, footer_text)

        for untranslated in (
            "Our special products",
            "Our terms and conditions of delivery",
            "Our secure payment method",
            "Order tracking",
            "Toggle your account links",
            "Toggle 商品 links",
            "Toggle 当社について links",
            "Toggle store information",
        ):
            with self.subTest(untranslated=untranslated):
                self.assertNotIn(untranslated, footer_text)

    def test_korean_footer_links_and_accessible_text_use_korean(self) -> None:
        status, _, body = fetch(f"{BASE_URL}/ko/")
        self.assertEqual(status, 200)
        footer_match = re.search(r'<footer id="footer".*?</footer>', body, re.DOTALL)
        self.assertIsNotNone(footer_match, "store footer is missing")
        footer = html.unescape(footer_match.group(0))
        footer_text = " ".join(re.sub(r"<[^>]+>", " ", footer).split())

        for expected in (
            "상품 링크 열기/닫기",
            "회사 정보 링크 열기/닫기",
            "계정 링크 열기/닫기",
            "매장 정보 링크 열기/닫기",
            "할인 상품",
            "배송 안내",
            "주문 조회",
            "로그인",
            "회원가입",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, footer_text)

        for untranslated in (
            "Toggle 상품 links",
            "Toggle 우리 회사 links",
            "Toggle your account links",
            "Toggle store information",
            "Order tracking",
            "Create an account",
        ):
            with self.subTest(untranslated=untranslated):
                self.assertNotIn(untranslated, footer_text)

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

    def test_brand_text_manifest_and_mobile_navigation_avoid_legacy_assets(self) -> None:
        status, final_url, body = fetch(f"{BASE_URL}/")
        self.assertEqual(status, 200)
        metadata = PageMetadata()
        metadata.feed(body)
        self.assertIn("ORDENOWA", body, "confirmed text brand should render while official artwork is unavailable")
        self.assertNotIn("KURANEA", body, "legacy brand should not be shown to customers")
        self.assertFalse(any("kuranea-logo-" in image.get("src", "") for image in metadata.images))
        self.assertTrue(any(link.get("rel") == "manifest" for link in metadata.links), "web manifest link is missing")
        self.assertFalse(any(link.get("rel") == "apple-touch-icon" for link in metadata.links), "unavailable official artwork must not be substituted")
        self.assertIn("kuranea-mobile-nav", body)
        manifest_url = next(link["href"] for link in metadata.links if link.get("rel") == "manifest")
        try:
            with urlopen(urljoin(final_url, manifest_url), timeout=20) as response:
                self.assertEqual(response.status, 200)
                manifest = json.load(response)
        except HTTPError as error:
            self.fail(f"web app manifest returned HTTP {error.code}")
        self.assertEqual(manifest.get("lang"), "ja-JP")
        self.assertEqual(manifest.get("name"), "オーデノワ")
        self.assertEqual(manifest.get("icons"), [])
        self.assertNotIn("KURANEA", json.dumps(manifest, ensure_ascii=False))

    def test_admin_login_is_reachable(self) -> None:
        status, final_url, body = fetch(f"{BASE_URL}/admin-kuranea/")
        self.assertEqual(status, 200)
        self.assertIn("/admin-kuranea/login", final_url)
        self.assertGreaterEqual(len(re.findall(r'<input[^>]+type=[\"\'](?:email|password)', body)), 2)
        self.assertIn("ORDENOWA", body)

    def test_postcode_lookup_endpoint_keeps_manual_entry_available(self) -> None:
        query = urlencode({
            "fc": "module",
            "module": "kuraneapostcode",
            "controller": "candidates",
            "q": "1000004",
        })
        request = urlopen(f"{BASE_URL}/?{query}", timeout=20)
        with request as response:
            self.assertEqual(response.status, 200)
            self.assertIn("application/json", response.headers.get("Content-Type", ""))
            payload = json.loads(response.read().decode("utf-8"))
        self.assertIs(payload.get("manual_entry_available"), True)
        self.assertIsInstance(payload.get("candidates"), list)


if __name__ == "__main__":
    unittest.main()
