from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class ModuleManagerKoreanMetadataTests(unittest.TestCase):
    def test_backoffice_module_name_and_description_are_korean(self) -> None:
        source = (ROOT / "modules" / "kuraneabackoffice" / "kuraneabackoffice.php").read_text()

        self.assertIn("$this->displayName = 'ORDENOWA 관리자 화면 지원';", source)
        self.assertIn(
            "$this->description = '한국어 관리자 로그인, 게시된 브랜드 표시 및 관리자 번역 오버레이를 지원합니다.';",
            source,
        )

    def test_postcode_module_name_and_description_are_korean(self) -> None:
        source = (ROOT / "modules" / "kuraneapostcode" / "kuraneapostcode.php").read_text()

        self.assertIn("$this->displayName = '일본 우편번호·주소 검색';", source)
        self.assertIn(
            "$this->description = '고객 주소 입력란에서 일본 우편번호와 주소 후보를 오프라인으로 제공합니다.';",
            source,
        )


if __name__ == "__main__":
    unittest.main()
