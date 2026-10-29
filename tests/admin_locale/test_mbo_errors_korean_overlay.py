from __future__ import annotations

import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "modules" / "kuraneabackoffice"
NAMESPACE = {"x": "urn:oasis:names:tc:xliff:document:1.2"}
SOURCE = (
    "It looks like we have trouble connecting to Addons. Please refresh the page "
    "or check your firewall configuration."
)
TARGET = "Addons에 연결하는 데 문제가 있는 것 같습니다. 페이지를 새로고침하거나 방화벽 설정을 확인해 주세요."


class MboErrorsKoreanOverlayTests(unittest.TestCase):
    def test_error_domain_loads_the_verified_korean_xliff_translation(self) -> None:
        subscriber_path = MODULE / "src" / "AdminLocaleSubscriber.php"
        subscriber = subscriber_path.read_text(encoding="utf-8")
        loader = subscriber.split("private function loadKoreanCatalogue(", 1)[1]
        mapping_block = re.search(
            r"foreach\s*\(\s*\[(.*?)\]\s*as\s*\$domain\s*=>\s*\$filename\s*\)",
            loader,
            re.DOTALL,
        )
        self.assertIsNotNone(mapping_block, "missing module-owned catalogue overlay map")
        mapping = dict(
            re.findall(r"\x27([^\x27]+)\x27\s*=>\s*\x27([^\x27]+)\x27", mapping_block.group(1))
        )
        self.assertEqual("ModulesMboErrors.ko-KR.xlf", mapping.get("Modules.Mbo.Errors"))
        self.assertIn(
            "$this->translator->addResource(\x27xlf\x27, $translationFile, $locale, $catalogueDomain);",
            loader,
            "the mapped XLIFF must be registered with Symfony\x27s xlf loader",
        )
        self.assertIn(
            "$catalogue->addCatalogue($loader->load($translationFile, $locale, $catalogueDomain));",
            loader,
            "the module-owned catalogue must be merged after PrestaShop\x27s database catalogue",
        )

        path = MODULE / "translations" / "ko-KR" / mapping["Modules.Mbo.Errors"]
        self.assertTrue(path.is_file(), "the registered Korean MBO error catalogue is missing")
        root = ET.parse(path).getroot()
        self.assertEqual("1.2", root.attrib.get("version"))
        file_node = root.find("x:file", NAMESPACE)
        self.assertIsNotNone(file_node)
        self.assertEqual("en-US", file_node.attrib.get("source-language"))
        self.assertEqual("ko-KR", file_node.attrib.get("target-language"))
        units = root.findall(".//x:trans-unit", NAMESPACE)
        self.assertEqual(1, len(units), "keep this focused overlay limited to the verified source")
        self.assertEqual("8a5560b05facacdbc10e870b1152e41b", units[0].attrib.get("id"))
        self.assertEqual(SOURCE, units[0].findtext("x:source", namespaces=NAMESPACE))
        self.assertEqual(TARGET, units[0].findtext("x:target", namespaces=NAMESPACE))
        self.assertNotEqual(SOURCE, TARGET)


    def test_native_acceptance_runs_real_translation_lifecycle(self) -> None:
        script = (ROOT / "tests" / "procurement" / "ci_acceptance.sh").read_text(encoding="utf-8")
        boundary = script.split("native_boundaries() {", 1)[1].split(
            "\n}\nrun_phase native_boundary native_boundaries", 1
        )[0]
        self.assertIn(
            'compose exec -T -u www-data prestashop php '
            '/var/www/html/tests/admin_locale/locale_lifecycle.php '
            '/var/www/html/vendor/autoload.php /var/www/html || return "$?"',
            boundary,
            "actual upstream translation lifecycle failure must fail the native boundary",
        )


if __name__ == "__main__":
    unittest.main()

