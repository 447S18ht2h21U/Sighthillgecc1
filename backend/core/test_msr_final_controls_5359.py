from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError
from .services import validate_snapshot

class MSRFinalControls5359(SimpleTestCase):
    def test_true_and_false(self):
        for value in (True, False):
            self.assertIs(
                validate_snapshot({"marketing_promotion": value})[
                    "marketing_promotion"
                ],
                value,
            )

    def test_invalid_checkbox(self):
        for value in ("yes", None, 1):
            with self.assertRaises(ValidationError):
                validate_snapshot({"marketing_promotion": value})

    def test_legacy_snapshot_without_checkbox(self):
        result = validate_snapshot({"commercial_notes": "Existing MSR"})
        self.assertNotIn("marketing_promotion", result)

    def test_no_pricing_effect(self):
        result = validate_snapshot({
            "marketing_promotion": True,
            "base_price": "12500.00",
            "discount": "0.00",
            "tax": "0.00",
            "total_price": "12500.00",
        })
        self.assertEqual(result["total_price"], "12500.00")
        self.assertEqual(result["discount"], "0.00")
