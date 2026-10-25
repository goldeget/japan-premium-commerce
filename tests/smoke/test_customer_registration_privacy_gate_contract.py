"""Guard the fail-closed customer registration boundary."""
from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COMMERCE_GATE = ROOT / "modules/kuraneabusinessprofile/src/Customer/CommerceGate.php"
MODULE = ROOT / "modules/kuraneabusinessprofile/kuraneabusinessprofile.php"
PUBLISHED_OUTPUT_TEST = ROOT / "tests/business_profile/published_output.php"
BUSINESS_PROFILE_WORKFLOW = ROOT / ".github/workflows/business-profile.yml"


def method_source(source: str, method_name: str) -> str:
    signature = f"function {method_name}"
    start = source.find(signature)
    if start < 0:
        return ""
    body_start = source.index("{", start)
    depth = 0
    for index in range(body_start, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    raise AssertionError(f"unterminated method: {method_name}")


class CustomerRegistrationPrivacyGateContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.commerce_gate = COMMERCE_GATE.read_text(encoding="utf-8")
        cls.module = MODULE.read_text(encoding="utf-8")
        cls.registration_gate = method_source(cls.commerce_gate, "isRegistrationEnabled")
        cls.front_controller_hook = method_source(cls.module, "hookActionFrontControllerInitBefore")

    def test_registration_requires_the_existing_seller_gate_or_exact_ci_override(self) -> None:
        self.assertIn(
            "self::isEnabled($publishedProfile, $externalAuthorizationConfirmed)",
            self.registration_gate,
        )
        self.assertIn("self::isIsolatedCiCheckoutEnabled()", self.registration_gate)

    def test_only_registration_and_account_creation_posts_are_blocked(self) -> None:
        self.assertRegex(
            self.front_controller_hook,
            r"\$controllerName === 'registration'\s*"
            r"\|\|\s*\(\$controllerName === 'authentication'\s*"
            r"&&\s*\\Tools::isSubmit\('submitCreate'\)\)",
        )
        self.assertIn("CommerceGate::isRegistrationEnabled(", self.front_controller_hook)
        self.assertIn("\\Tools::redirect($this->context->link->getPageLink('index'))", self.front_controller_hook)
        self.assertNotIn("$controllerName === 'password'", self.front_controller_hook)

    def test_private_cache_headers_are_set_before_registration_redirect(self) -> None:
        cache_policy = self.front_controller_hook.index("header('Cache-Control: private, no-store, max-age=0'")
        registration_check = self.front_controller_hook.find("$isCustomerRegistrationRequest =")
        self.assertGreaterEqual(registration_check, 0, "the registration gate must be handled by the private route hook")
        if registration_check < 0:
            return
        self.assertLess(cache_policy, registration_check)

    def test_php_runtime_contract_checks_pending_and_exact_ci_registration_gate(self) -> None:
        runtime_test = PUBLISHED_OUTPUT_TEST.read_text(encoding="utf-8")
        for required in (
            "CommerceGate::isRegistrationEnabled($published)",
            "A pending seller profile must not expose customer registration",
            "Customer registration may open inside the exact disposable Actions project",
            "Customer registration must reject a Compose project from another Actions attempt",
        ):
            with self.subTest(required=required):
                self.assertIn(required, runtime_test)

        workflow = BUSINESS_PROFILE_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("run: php tests/business_profile/published_output.php", workflow)


if __name__ == "__main__":
    unittest.main()
