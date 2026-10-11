import unittest

from backend.pricing import PricingError, calculate_shipping_fee, determine_route


class PricingTests(unittest.TestCase):
    def test_special_etn_route(self):
        self.assertEqual(determine_route("Hà Nội", "TP.HCM", "ETN011"), "Hà Nội đi TP.HCM và ngược lại")

    def test_real_weight_when_all_sides_are_at_most_50cm(self):
        quote = calculate_shipping_fee(service="ETN011", origin="Hà Nội", destination="Đà Nẵng", actual_weight_kg=2.2, length_cm=50, width_cm=20, height_cm=20)
        self.assertEqual(quote.chargeable_weight_kg, 2.2)
        self.assertFalse(quote.used_volumetric_weight)
        self.assertEqual(quote.amount_vnd, 72000)

    def test_volumetric_weight_when_any_side_is_over_50cm(self):
        quote = calculate_shipping_fee(service="ETN011", origin="Hà Nội", destination="Đà Nẵng", actual_weight_kg=1, length_cm=60, width_cm=40, height_cm=30)
        self.assertEqual(quote.chargeable_weight_kg, 12.0)
        self.assertTrue(quote.used_volumetric_weight)
        self.assertEqual(quote.amount_vnd, 252500)

    def test_ctn_progressive_pricing(self):
        quote = calculate_shipping_fee(service="CTN001", origin="Hà Nội", destination="TP. Hồ Chí Minh", actual_weight_kg=2.4, length_cm=20, width_cm=20, height_cm=20)
        self.assertEqual(quote.route, "Cách vùng")
        self.assertEqual(quote.amount_vnd, 56311.2)

    def test_etn001_uses_configured_extra_weight_tier(self):
        # Bundled pricing.json defines an extra 500 g tier: 62,500 + 4,750.
        quote = calculate_shipping_fee(service="ETN001", origin="Hà Nội", destination="Đà Nẵng", actual_weight_kg=2.1, length_cm=20, width_cm=20, height_cm=20)
        self.assertEqual(quote.amount_vnd, 67250)

    def test_unknown_province_is_rejected(self):
        with self.assertRaises(PricingError):
            calculate_shipping_fee(service="ETN001", origin="Hà Nội", destination="Unknown Demo Province", actual_weight_kg=1, length_cm=20, width_cm=20, height_cm=20)


if __name__ == "__main__":
    unittest.main()
