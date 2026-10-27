from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "modules/kuraneabusinessprofile/kuraneabusinessprofile.php"
APPENDER_PATH = ROOT / "modules/kuraneabusinessprofile/src/Customer/OrderConfirmationMailContent.php"
PHP_TEST_PATH = ROOT / "tests/business_profile/order_confirmation_mail.php"
UPGRADE_PATH = ROOT / "modules/kuraneabusinessprofile/upgrade/upgrade-1.0.1.php"


class OrderConfirmationMailContractTest(unittest.TestCase):
    def test_only_order_confirmation_registers_and_uses_the_mail_hook(self):
        module = MODULE_PATH.read_text(encoding="utf-8")
        self.assertIn("'actionEmailAddAfterContent'", module)
        self.assertIn("function hookActionEmailAddAfterContent(array $params)", module)
        self.assertIn("($params['template'] ?? '') !== 'order_conf'", module)
        self.assertRegex(module, r"OrderConfirmationMailContent::append\(\s*'order_conf'")

    def test_mail_profile_resolution_uses_mail_language_and_shop(self):
        module = MODULE_PATH.read_text(encoding="utf-8")
        self.assertIn("new Language((int) ($params['id_lang'] ?? 0))", module)
        self.assertIn("$params['id_shop'] ?? 0", module)
        self.assertIn("$mailShopId ?? $this->activeMailShopId ?? $this->context->shop->id", module)
        self.assertIn("->forShop($shopId, $isoCode)", module)

    def test_mail_shop_id_comes_from_the_pre_send_hook_for_multishop_delivery(self):
        module = MODULE_PATH.read_text(encoding="utf-8")
        upgrade_path = ROOT / "modules/kuraneabusinessprofile/upgrade/upgrade-1.0.2.php"
        self.assertIn("'actionEmailSendBefore'", module)
        self.assertIn("function hookActionEmailSendBefore(array $params)", module)
        self.assertIn("$params['idShop']", module)
        self.assertIn("$this->activeMailShopId", module)
        self.assertIn("$this->version = '1.0.5'", module)
        self.assertTrue(upgrade_path.is_file(), "existing installations need a 1.0.2 hook upgrade")
        self.assertIn("registerHook('actionEmailSendBefore')", upgrade_path.read_text(encoding="utf-8"))
        self.assertTrue((ROOT / "modules/kuraneabusinessprofile/upgrade/upgrade-1.0.3.php").is_file())
        self.assertTrue((ROOT / "modules/kuraneabusinessprofile/upgrade/upgrade-1.0.4.php").is_file())

    def test_pre_smtp_reset_diagnostic_is_run_scoped_and_contains_only_link_shape_booleans(self):
        module = MODULE_PATH.read_text(encoding="utf-8")
        install = module.split("public function install()", 1)[1].split("public function uninstall()", 1)[0]
        before = module.split("public function hookActionEmailSendBefore", 1)[1].split(
            "public function hookActionMailAlterMessageBeforeSend", 1
        )[0]
        hook = module.split("public function hookActionMailAlterMessageBeforeSend", 1)[1].split(
            "private function isIsolatedResetFixtureMessage", 1
        )[0]
        recipient_guard = module.split("private function isIsolatedResetFixtureMessage", 1)[1].split(
            "private function hasNativeResetLink", 1
        )[0]
        for marker in (
            "'actionMailAlterMessageBeforeSend'",
            "X-ORDENOWA-CI-Pre-SMTP-HTML-Native-Reset-Link",
            "X-ORDENOWA-CI-Pre-SMTP-Text-Native-Reset-Link",
            "X-ORDENOWA-CI-Pre-SMTP-Text-Mime-Native-Reset-Link",
            "X-ORDENOWA-CI-Reset-Text-Getter-Match-Reason",
            "X-ORDENOWA-CI-Reset-Text-Mime-Match-Reason",
            "'message_is_symfony_email' => 'Symfony-Email-Object'",
            "'text_setter_returned_same_message' => 'Text-Setter-Returned-Same-Message'",
            "'text_getter_returned_string' => 'Text-Getter-Returned-String'",
            "'text_mime_body_read_succeeded' => 'Text-Mime-Body-Read-Succeeded'",
            "'text_mime_body_identity_same_after_setter' => 'Text-Mime-Body-Identity-Same-After-Setter'",
            "'text_mime_body_reset_retry_attempted' => 'Text-Mime-Body-Reset-Retry-Attempted'",
            "'text_mime_body_changed_after_reset' => 'Text-Mime-Body-Changed-After-Reset'",
            "'text_plain_text_part_present' => 'Text-Plain-Part-Present'",
            "X-ORDENOWA-CI-Reset-URL-Candidate-Found",
            "X-ORDENOWA-CI-Reset-Template-Context-Recognized",
            "X-ORDENOWA-CI-Reset-Template-URL-Candidate-Present",
            "X-ORDENOWA-CI-Reset-Template-URL-Credentials-Complete",
            "X-ORDENOWA-CI-Reset-Template-URL-Native-Route",
            "'candidate_present' => 'HTML-URL-Candidate-Present'",
            "'token_present' => 'HTML-Token-Present'",
            "'reset_token_present' => 'HTML-Reset-Token-Present'",
            "'id_customer_present' => 'HTML-Customer-ID-Present'",
            "'scheme_host_port_match' => 'HTML-Scheme-Host-Port-Match'",
            "'path_match' => 'HTML-Path-Match'",
            "'credentials_complete' => 'HTML-Credentials-Complete'",
            "'candidate_selected' => 'HTML-Candidate-Selected'",
            "'X-ORDENOWA-CI-Reset-' . $suffix",
            "X-ORDENOWA-CI-Text-Setter-Available",
            "X-ORDENOWA-CI-Text-Setter-Invoked",
        ):
            self.assertIn(marker, install + hook)
        self.assertIn("function hookActionMailAlterMessageBeforeSend(array $params)", module)
        self.assertIn("private static ?array $pendingMailSendContext = null", module)
        self.assertIn("self::$pendingMailSendContext = [", before)
        self.assertIn("$sendContext = self::$pendingMailSendContext", hook)
        for marker in (
            "getenv('GITHUB_ACTIONS') !== 'true'",
            "getenv('KURANEA_CI_PROJECT_NAME') !== $project",
            "ordenowa-reset-locale-",
            "@example\\\\.invalid",
        ):
            self.assertIn(marker, recipient_guard)
        self.assertNotIn("getHtmlBody() .", hook)
        self.assertNotIn("getTextBody() .", hook)

    def test_password_reset_text_fallback_uses_the_native_same_shop_reset_url(self):
        module = MODULE_PATH.read_text(encoding="utf-8")
        before = module.split("public function hookActionEmailSendBefore", 1)[1].split(
            "public function hookActionMailAlterMessageBeforeSend", 1
        )[0]
        alter = module.split("public function hookActionMailAlterMessageBeforeSend", 1)[1].split(
            "private function isIsolatedResetFixtureMessage", 1
        )[0]
        validator = module.split("private function validatedNativeResetUrl", 1)[1].split(
            "private function hasNativeResetLink", 1
        )[0]
        extractor = module.split("private function extractNativeResetUrl", 1)[1].split(
            "private function hasNativeResetLink", 1
        )[0]
        link_matcher = module.split("private function hasNativeResetLink", 1)[1].split(
            "private function sameNativeResetRoute", 1
        )[0]

        self.assertIn("$this->activeMailTemplate !== 'password_query'", before)
        self.assertIn("$params['templateVars']['{url}']", before)
        self.assertIn("$params['idLang']", before)
        self.assertIn("$this->activeMailShopId", before)
        self.assertIn("$this->context->link->getPageLink(", validator)
        self.assertIn("resetRouteEvidence($parts, $native)", validator)
        self.assertIn("resetCredentialEvidence($parts)", validator)
        for key in ("'token'", "'reset_token'", "'id_customer'"):
            self.assertIn(key, link_matcher)
        self.assertIn("$mailTemplate === 'password_query'", alter)
        self.assertIn(
            "$resetUrl = $mailTemplate === 'password_query'\n"
            "                ? $this->extractNativeResetUrl($htmlBody, $mailLangId, $mailShopId, $htmlUrlEvidence)\n"
            "                : null;",
            alter,
        )
        self.assertLess(
            alter.index("$resetUrl = $mailTemplate === 'password_query'"),
            alter.index("if ($resetUrl === null"),
        )
        self.assertIn("$htmlBody", alter)
        self.assertIn("$params['id_lang']", alter)
        self.assertIn("$params['id_shop'] ?? $params['idShop']", alter)
        self.assertIn("$this->context->language->id", alter)
        self.assertIn("$this->context->shop->id", alter)
        fallback = alter.split("if ($resetUrl === null", 1)[1].split("$textSetterAvailable", 1)[0]
        self.assertIn("$mailTemplate === 'password_query'", fallback)
        self.assertIn("$nativeResetUrl", fallback)
        self.assertIn("$this->validatedNativeResetUrl(", fallback)
        self.assertIn("$mailLangId", fallback)
        self.assertIn("$mailShopId", fallback)
        self.assertNotIn("$this->hasNativeResetLink($htmlBody, $nativeResetUrl)", fallback)
        self.assertIn("$this->extractNativeResetUrl($htmlBody, $mailLangId, $mailShopId, $htmlUrlEvidence)", alter)
        self.assertIn("$textSetterAvailable = method_exists($message, 'text')", alter)
        self.assertIn("$textSetterInvoked = true", alter)
        self.assertIn("$resetUrl !== null", alter)
        self.assertIn("$message->text($replacement, 'utf-8')", alter)
        self.assertIn("$this->hasExactValidatedNativeResetUrl(", alter)
        self.assertIn("$message instanceof \\Symfony\\Component\\Mime\\Email", alter)
        self.assertIn("$setterResult === $message", alter)
        self.assertIn("$textGetterReturnedString = is_string($textReadback)", alter)
        self.assertIn("$textMimeBodyIdentitySameAfterSetter = $textMimeBodyBeforeSetter === $textMimeBody", alter)
        self.assertIn("$textMimeBodyResetRetryAttempted = true", alter)
        self.assertIn("$textMimeBodyChangedAfterReset = $textMimeBody !== $rebuiltMimeBody", alter)
        self.assertIn("$message->setBody(null)", alter)
        self.assertIn("$this->hasExactNativeResetUrlInMimeBody(", alter)
        self.assertIn("X-ORDENOWA-CI-Pre-SMTP-Text-Mime-Native-Reset-Link", alter)
        self.assertIn("$textGetterHasLink = $this->hasExactValidatedNativeResetUrl(", alter)
        self.assertIn("if (!$textGetterHasLink || !$textMimeHasLink)", alter)
        self.assertIn("getPageLink(", extractor)
        self.assertIn("resetRouteEvidence($parts, $native)", extractor)
        self.assertIn("resetCredentialEvidence($parts)", extractor)
        self.assertIn("finally", alter)
        self.assertIn("$this->activeNativeResetUrl = null", alter)
        self.assertIn("$this->activeMailLangId = null", alter)
        self.assertNotIn("error_log", alter)

    def test_reset_email_link_failure_diagnostics_are_boolean_and_keep_every_credential_guard(self):
        module = MODULE_PATH.read_text(encoding="utf-8")
        extractor = module.split("private function extractNativeResetUrl", 1)[1].split(
            "private function hasNativeResetLink", 1
        )[0]
        validator = module.split("private function validatedNativeResetUrl", 1)[1].split(
            "private function extractNativeResetUrl", 1
        )[0]
        credential_validator = module.split("private function resetCredentialEvidence", 1)[1].split(
            "private function resetRouteEvidence", 1
        )[0]
        for marker in (
            "resetCredentialEvidence($parts)",
            "resetRouteEvidence($parts, $native)",
            "credentials_complete",
            "candidate_selected",
            "scheme_host_port_match",
            "path_match",
        ):
            self.assertIn(marker, extractor + validator)
        for key in ("token_present", "reset_token_present", "id_customer_present"):
            self.assertIn(key, extractor)
            self.assertIn(key, validator)
        self.assertIn("$result['credentials_complete'] = $result['token_present']", module)
        self.assertIn("&& $result['reset_token_present']", module)
        self.assertIn("&& $result['id_customer_present']", module)
        self.assertIn("$credentialCounts[$key] === 1", credential_validator)
        self.assertIn("preg_split", credential_validator)
        self.assertIn("$this->resetCredentialEvidence($expected)", module)
        self.assertNotIn("error_log", extractor + validator)

        exact_verifier = module.split("private function hasExactValidatedNativeResetUrl", 1)[1].split(
            "private function sameNativeResetRoute", 1
        )[0]
        self.assertIn("$this->validatedNativeResetUrl(", exact_verifier)
        self.assertIn("$this->extractNativeResetUrl(", exact_verifier)
        self.assertIn("$candidateEvidence['credentials_complete']", exact_verifier)
        self.assertIn("$candidateEvidence['candidate_selected']", exact_verifier)
        self.assertIn("$candidateEvidence['scheme_host_port_match']", exact_verifier)
        self.assertIn("$candidateEvidence['path_match']", exact_verifier)
        self.assertIn("hash_equals($validatedExpectedUrl, $candidateUrl)", exact_verifier)
        self.assertIn("'expected_url_match'", exact_verifier)
        mime_verifier = module.split("private function hasExactNativeResetUrlInMimeBody", 1)[1].split(
            "public function publicProfile", 1
        )[0]
        self.assertIn("\\Symfony\\Component\\Mime\\Part\\TextPart", mime_verifier)
        self.assertIn("getMediaSubtype() !== 'plain'", mime_verifier)
        self.assertIn("\\Symfony\\Component\\Mime\\Part\\AbstractMultipartPart", mime_verifier)
        self.assertIn("getParts()", mime_verifier)

    def test_mail_shop_context_reaches_both_content_and_extra_vars_before_cleanup(self):
        module = MODULE_PATH.read_text(encoding="utf-8")

        def method_body(name):
            start = module.index(f"public function {name}")
            opening = module.index("{", start)
            depth = 0
            for index in range(opening, len(module)):
                if module[index] == "{":
                    depth += 1
                elif module[index] == "}":
                    depth -= 1
                    if depth == 0:
                        return module[opening + 1:index]
            self.fail(f"Could not find closing brace for {name}")

        after_content = method_body("hookActionEmailAddAfterContent")
        extra_vars = method_body("hookActionGetExtraMailTemplateVars")

        self.assertIn("$mailContextShopId = $this->activeMailShopId", after_content)
        self.assertIn("$this->mailShopAndIsoCode($params, $mailContextShopId)", after_content)
        self.assertIn("->forShop($shopId, $isoCode)", after_content)
        self.assertNotIn("$this->activeMailShopId = null", after_content)

        self.assertIn("$mailContextShopId = $this->activeMailShopId", extra_vars)
        self.assertIn("$this->mailShopAndIsoCode($params, $mailContextShopId)", extra_vars)
        self.assertIn("->forShop($shopId, $isoCode)", extra_vars)
        self.assertRegex(
            extra_vars,
            r"finally\s*\{\s*\$this->activeMailShopId\s*=\s*null;\s*\}",
            "the captured mail shop should be cleared after extra vars, including early returns",
        )

    def test_existing_install_upgrade_registers_the_new_hook(self):
        module = MODULE_PATH.read_text(encoding="utf-8")
        upgrade = UPGRADE_PATH.read_text(encoding="utf-8")
        self.assertIn("$this->version = '1.0.5'", module)
        self.assertIn("function upgrade_module_1_0_1", upgrade)
        self.assertIn("registerHook('actionEmailAddAfterContent')", upgrade)
        self.assertTrue((ROOT / "modules/kuraneabusinessprofile/upgrade/upgrade-1.0.3.php").is_file())
        self.assertTrue((ROOT / "modules/kuraneabusinessprofile/upgrade/upgrade-1.0.4.php").is_file())

    def test_appender_preserves_both_templates_and_uses_escaped_public_profile_output(self):
        appender = APPENDER_PATH.read_text(encoding="utf-8")
        self.assertIn("$template !== 'order_conf'", appender)
        self.assertIn("PublicFooterBuilder::build($profile, $commerceEnabled)", appender)
        self.assertIn("strip_tags", appender)
        self.assertIn("html_entity_decode", appender)
        self.assertIn("</body>", appender)
        self.assertIn("substr_replace", appender)

    def test_php_synthetic_regression_covers_core_sentinels_and_fail_closed_cases(self):
        php_test = PHP_TEST_PATH.read_text(encoding="utf-8")
        for expected in (
            "{order_name}",
            "{products}",
            "{total_paid}",
            "{products_txt}",
            "결제 안내",
            "</body>",
            "'new_order'",
            "bodylessHtml",
        ):
            self.assertIn(expected, php_test)


if __name__ == "__main__":
    unittest.main()
