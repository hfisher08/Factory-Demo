import unittest

from roi import calculate_roi, main, render_html


class CalculateRoiTest(unittest.TestCase):
    def test_worked_example(self):
        # 100 engineers at $200k, saving 4 h/week over 46 weeks of 40 h:
        # hourly = 200000 / 1840; value = 100 * 4 * 46 * hourly = $2,000,000.
        r = calculate_roi(100, 200_000, 4, 500_000)
        self.assertAlmostEqual(r.annual_value, 2_000_000)
        self.assertAlmostEqual(r.net_value, 1_500_000)
        self.assertAlmostEqual(r.roi_percent, 300)
        self.assertAlmostEqual(r.payback_months, 3.0)
        self.assertEqual(r.hours_saved_per_year, 18_400)

    def test_zero_hours_saved_never_pays_back(self):
        r = calculate_roi(10, 150_000, 0, 50_000)
        self.assertEqual(r.annual_value, 0)
        self.assertEqual(r.roi_percent, -100)
        self.assertEqual(r.payback_months, float("inf"))

    def test_rejects_invalid_inputs(self):
        bad = [
            dict(engineers=0, loaded_annual_cost=1, hours_saved_per_week=1, annual_tool_cost=1),
            dict(engineers=1, loaded_annual_cost=0, hours_saved_per_week=1, annual_tool_cost=1),
            dict(engineers=1, loaded_annual_cost=1, hours_saved_per_week=-1, annual_tool_cost=1),
            dict(engineers=1, loaded_annual_cost=1, hours_saved_per_week=41, annual_tool_cost=1),
            dict(engineers=1, loaded_annual_cost=1, hours_saved_per_week=1, annual_tool_cost=0),
        ]
        for kwargs in bad:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                calculate_roi(**kwargs)


class OutputTest(unittest.TestCase):
    def test_html_escapes_customer_name(self):
        page = render_html("<script>", calculate_roi(1, 100_000, 1, 1_000))
        self.assertNotIn("<script>", page)
        self.assertIn("&lt;script&gt;", page)

    def test_cli_rejects_invalid_input(self):
        with self.assertRaises(SystemExit) as ctx:
            main(["--engineers", "0", "--loaded-cost", "1",
                  "--hours-saved", "1", "--tool-cost", "1"])
        self.assertEqual(ctx.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
