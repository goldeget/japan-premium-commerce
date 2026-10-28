from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "modules/kuraneabackoffice"
FOLDER = MODULE / "translations/ko-KR"
NS = {"x": "urn:oasis:names:tc:xliff:document:1.2"}
EXPECTED = {
    "Admin.Advparameters.Feature": 12,
    "Admin.Advparameters.Help": 15,
    "Admin.Design.Feature": 2,
    "Admin.Design.Help": 3,
    "Admin.International.Feature": 1,
    "Admin.Navigation.Menu": 4,
    "Admin.Shipping.Feature": 1,
    "Admin.Shipping.Help": 6,
    "Admin.Shopparameters.Feature": 4,
    "Admin.Shopparameters.Help": 5,
    "Admin.Shopparameters.Notification": 3,
    "Modules.Classicedition.Admin": 2,
    "Modules.Onepagecheckout.Admin": 11,
}
CANONICAL_SYSTEM_COPY = {("Modules.Classicedition.Admin", "Welcome"): "시작하기"}


def units(path: Path):
    return ET.parse(path).findall(".//x:trans-unit", NS)


def source(unit):
    return unit.findtext("x:source", namespaces=NS) or ""


def target(unit):
    return unit.findtext("x:target", namespaces=NS) or ""


class ExpandedNativeKoreanCatalogueTests(unittest.TestCase):
    def test_observed_static_labels_have_unique_korean_targets_and_registered_domains(self):
        subscriber = (MODULE / "src/AdminLocaleSubscriber.php").read_text()
        total = 0
        for domain, count in EXPECTED.items():
            filename = domain.replace(".", "") + ".ko-KR.xlf"
            with self.subTest(domain=domain):
                catalogue = units(FOLDER / filename)
                identifiers = [unit.attrib["id"] for unit in catalogue]
                sources = [source(unit) for unit in catalogue]
                self.assertEqual(len(identifiers), len(set(identifiers)))
                self.assertEqual(len(sources), len(set(sources)))
                observed = [u for u in catalogue if u.attrib["id"].startswith("expanded-native-")]
                self.assertEqual(count, len(observed))
                self.assertTrue(f"'{domain}' => '{filename}'" in subscriber, domain)
                for unit in observed:
                    self.assertTrue(source(unit).strip())
                    self.assertRegex(target(unit), r"[가-힣]")
                    self.assertNotEqual(source(unit), target(unit))
                    canonical = CANONICAL_SYSTEM_COPY.get((domain, source(unit)))
                    if canonical is not None:
                        self.assertEqual(canonical, target(unit))
                total += len(observed)
        self.assertEqual(69, total)

    def test_placeholders_markup_and_technical_formats_are_preserved(self):
        placeholder = re.compile(r"%[A-Za-z_][A-Za-z0-9_]*%|%(?:\d+\$)?[sdif]|\{\{.*?\}\}")
        markup = re.compile(r"</?[^>]+>")
        for domain in EXPECTED:
            for unit in units(FOLDER / (domain.replace(".", "") + ".ko-KR.xlf")):
                if not unit.attrib["id"].startswith("expanded-native-"):
                    continue
                original, translated = source(unit), target(unit)
                with self.subTest(domain=domain, identifier=unit.attrib["id"]):
                    self.assertEqual(Counter(placeholder.findall(original)), Counter(placeholder.findall(translated)))
                    self.assertEqual(Counter(markup.findall(original)), Counter(markup.findall(translated)))
                    for technical in ("JPG/PNG", "WebP", "AVIF", "TLSv1.2", "HTTPS", "API", "0-4"):
                        if technical in original:
                            self.assertIn(technical, translated)
                    self.assertNotIn(original, ("WebP", "AVIF", "From", "To"))
                    self.assertFalse(original.startswith(("https://", "http://")))

    def test_email_menu_is_corrected_without_replacing_ambiguous_global_date_labels(self):
        navigation = {source(u): target(u) for u in units(FOLDER / "AdminNavigationMenu.ko-KR.xlf")}
        general = {source(u): target(u) for u in units(FOLDER / "AdminGlobal.ko-KR.xlf")}
        self.assertEqual("이메일", navigation["E-mail"])
        self.assertEqual("시작일", general["From"])
        self.assertEqual("종료일", general["To"])

    def test_home_copy_matches_native_module_translation_cas_and_strict_fresh_seed(self):
        canonical = CANONICAL_SYSTEM_COPY[("Modules.Classicedition.Admin", "Welcome")]
        catalogue = {source(u): target(u) for u in units(FOLDER / "ModulesClassiceditionAdmin.ko-KR.xlf")}
        repair = (MODULE / "src/Admin/KoreanAdminTabLabels.php").read_text()
        seed = (ROOT / "tests/procurement/ci_seed.php").read_text()
        expected_names = seed.split("$expectedKoreanTabs = [", 1)[1].split("];", 1)[0]
        repair_targets = re.findall(r"\['HOME',\s*'ps_classic_edition',\s*'Welcome',\s*'([^']+)'\]", repair)
        seed_targets = re.findall(r"(?m)^\s*'HOME'\s*=>\s*'([^']+)'\s*,", expected_names)
        self.assertEqual([canonical], repair_targets)
        self.assertEqual([canonical], seed_targets)
        self.assertEqual(canonical, catalogue["Welcome"])


if __name__ == "__main__":
    unittest.main()
