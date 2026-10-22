from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
PROFILE_CONTROLLER = ROOT / "modules" / "kuraneabusinessprofile" / "controllers" / "admin" / "AdminBusinessProfileController.php"
BANKS_CONTROLLER = ROOT / "modules" / "kuraneabusinessprofile" / "controllers" / "admin" / "AdminBusinessProfileBanksController.php"


def init_content_source(path: Path, next_method: str) -> str:
    source = path.read_text(encoding="utf-8")
    start = source.index("public function initContent(): void")
    end = source.index(next_method, start)
    return source[start:end]


class AdminAccessSourceContractTests(unittest.TestCase):
    def assert_lazy_access_is_initialized_before_policy(
        self,
        source: str,
        policy_method: str,
        required_permissions: tuple[str, ...],
    ) -> None:
        policy_at = source.index(f"if (!AdminAccessPolicy::{policy_method}(")
        access_calls = ["$this->viewAccess();"]
        access_calls.extend(f"$this->access('{permission}');" for permission in required_permissions)

        previous_at = -1
        for call in access_calls:
            with self.subTest(access_initializer=call):
                self.assertIn(call, source)
                initializer_at = source.index(call)
                self.assertLess(previous_at, initializer_at, "Lazy access checks should be initialized in order.")
                self.assertLess(initializer_at, policy_at, f"{call} must run before {policy_method} policy evaluation.")
                previous_at = initializer_at

    def assert_denied_before_admin_work(
        self,
        source: str,
        policy_method: str,
        korean_denial: str,
        protected_markers: tuple[str, ...],
        access_expression: str = "(array) ($this->tabAccess ?? [])",
    ) -> None:
        guard = f"if (!AdminAccessPolicy::{policy_method}({access_expression})) {{"
        self.assertIn(guard, source)
        guard_at = source.index(guard)

        status_at = source.index("http_response_code(403);", guard_at)
        denial_at = source.index(korean_denial, status_at)
        assign_at = source.index("$this->context->smarty->assign('content', $this->content);", denial_at)
        return_at = source.index("return;", assign_at)
        self.assertLess(guard_at, status_at)
        self.assertLess(status_at, denial_at)
        self.assertLess(denial_at, assign_at)
        self.assertLess(assign_at, return_at)

        for marker in protected_markers:
            with self.subTest(protected_operation=marker):
                self.assertIn(marker, source)
                self.assertLess(guard_at, source.index(marker))
                self.assertLess(return_at, source.index(marker))

    def assert_form_output_reaches_smarty(self, source: str, form_render: str) -> None:
        self.assertRegex(source, rf"\$this->content\s*\.\=\s*{re.escape(form_render)}")
        render_at = source.index(form_render)
        assignments = [
            match.start()
            for match in re.finditer(
                r"\$this->context->smarty->assign\('content', \$this->content\);",
                source,
            )
        ]
        self.assertGreaterEqual(len(assignments), 2, "Denied and rendered screens should both assign content to Smarty.")
        self.assertLess(render_at, assignments[-1])

    def test_business_profile_read_denial_precedes_repository_actions_and_form_render(self) -> None:
        source = init_content_source(PROFILE_CONTROLLER, "    private function processProfileActions(")
        self.assert_lazy_access_is_initialized_before_policy(source, "canView", ("edit", "add"))
        self.assert_denied_before_admin_work(
            source,
            "canView",
            "쇼핑몰 운영 설정을 조회할 권한이 없습니다.",
            (
                "new VersionedProfileRepository()",
                "$this->processProfileActions(",
                "parent::initContent();",
                "AdminProfileForm::render(",
            ),
        )
        self.assert_form_output_reaches_smarty(source, "AdminProfileForm::render(")

    def test_bank_profile_read_denial_precedes_repository_and_form_render(self) -> None:
        source = init_content_source(BANKS_CONTROLLER, "    private function renderFeedback(")
        self.assert_lazy_access_is_initialized_before_policy(source, "canViewBank", ("edit",))
        self.assert_denied_before_admin_work(
            source,
            "canViewBank",
            "은행 계좌를 조회할 권한이 없습니다.",
            (
                "parent::initContent();",
                "new VersionedProfileRepository()",
                "$draft = $repository->loadDraft($shopId);",
                "AdminBankAccountForm::render(",
            ),
            access_expression="$bankAccess",
        )
        self.assert_form_output_reaches_smarty(source, "AdminBankAccountForm::render(")


if __name__ == "__main__":
    unittest.main()
