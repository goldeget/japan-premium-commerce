from __future__ import annotations

import unittest

from tests.e2e.admin_locale_diagnostics import (
    ORDER_LABEL_SOURCE_CATEGORIES,
    format_average_order_value_kpi_match,
    format_orders_body_match_sources,
)


class OrdersLocaleDiagnosticTests(unittest.TestCase):
    def test_average_order_kpi_diagnostic_is_a_boolean_category_only(self) -> None:
        self.assertEqual(format_average_order_value_kpi_match(True), "true")
        self.assertEqual(format_average_order_value_kpi_match(False), "false")
        self.assertEqual(format_average_order_value_kpi_match(None), "unknown")
        self.assertEqual(
            format_average_order_value_kpi_match("Average Order Value for private@example.invalid"),
            "unknown",
        )

    def test_matches_are_reported_as_fixed_categories_only(self) -> None:
        categories = {name: False for name in ORDER_LABEL_SOURCE_CATEGORIES}
        categories["toolbar"] = True
        categories["grid_body"] = True

        self.assertEqual(
            format_orders_body_match_sources(categories, True),
            "toolbar,grid_body",
        )

    def test_unclassified_body_match_is_bounded_and_no_match_is_explicit(self) -> None:
        categories = {name: False for name in ORDER_LABEL_SOURCE_CATEGORIES}

        self.assertEqual(format_orders_body_match_sources(categories, True), "other_visible_content")
        self.assertEqual(format_orders_body_match_sources(categories, False), "none")

    def test_malformed_or_private_source_metadata_is_never_echoed(self) -> None:
        categories = {name: False for name in ORDER_LABEL_SOURCE_CATEGORIES}
        categories["private@example.invalid"] = True

        result = format_orders_body_match_sources(categories, True)

        self.assertEqual(result, "unknown")
        self.assertNotIn("private@example.invalid", result)
        self.assertEqual(format_orders_body_match_sources("Order private@example.invalid", True), "unknown")


if __name__ == "__main__":
    unittest.main()
