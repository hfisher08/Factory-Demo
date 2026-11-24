import contextlib
import io
import os
import tempfile
import unittest

from roi import calculate_roi, format_money, format_summary, main, render_html


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


class CurrencyTest(unittest.TestCase):
    def setUp(self):
        self.result = calculate_roi(100, 200_000, 4, 500_000)

    def test_format_money(self):
        self.assertEqual(format_money(2_000_000), "$2,000,000")
        self.assertEqual(format_money(2_000_000, "GBP"), "£2,000,000")
        self.assertEqual(format_money(108.6956, "EUR", 2), "€108.70")
        self.assertEqual(format_money(-1_500, "GBP"), "-£1,500")

    def test_summary_defaults_to_usd(self):
        summary = format_summary(self.result)
        self.assertIn("Annual value created:   $2,000,000", summary)
        self.assertNotIn("£", summary)

    def test_summary_and_html_use_chosen_currency(self):
        for code, symbol in (("GBP", "£"), ("EUR", "€")):
            with self.subTest(currency=code):
                summary = format_summary(self.result, code)
                self.assertIn(f"Annual value created:   {symbol}2,000,000", summary)
                self.assertIn(f"Engineer hourly cost:   {symbol}108.70", summary)
                self.assertNotIn("$", summary)
                page = render_html("Acme", self.result, code)
                self.assertIn(f"<td>{symbol}1,500,000</td>", page)
                self.assertNotIn("$", page)

    def test_cli_writes_report_in_chosen_currency(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "report.html")
            with contextlib.redirect_stdout(io.StringIO()) as out:
                code = main(["--engineers", "100", "--loaded-cost", "200000",
                             "--hours-saved", "4", "--tool-cost", "500000",
                             "--currency", "GBP", "--html", path])
            self.assertEqual(code, 0)
            self.assertIn("£2,000,000", out.getvalue())
            with open(path, encoding="utf-8") as f:
                self.assertIn("<td>£500,000</td>", f.read())

    def test_cli_rejects_unknown_currency(self):
        with contextlib.redirect_stderr(io.StringIO()), \
                self.assertRaises(SystemExit) as ctx:
            main(["--engineers", "1", "--loaded-cost", "1", "--hours-saved", "1",
                  "--tool-cost", "1", "--currency", "JPY"])
        self.assertEqual(ctx.exception.code, 2)


# === Calculation and validation tests ===
class CalculationValidationTest(unittest.TestCase):
    def test_payback_infinite_when_value_below_cost(self):
        r = calculate_roi(100, 150_000, 1, 400_000)
        self.assertAlmostEqual(r.annual_value, 375_000)
        self.assertEqual(r.payback_months, float("inf"))

    def test_payback_infinite_when_value_equals_cost(self):
        r = calculate_roi(100, 200_000, 4, 2_000_000)
        self.assertAlmostEqual(r.annual_value, 2_000_000)
        self.assertEqual(r.payback_months, float("inf"))

    def test_payback_finite_when_profitable(self):
        self.assertAlmostEqual(calculate_roi(100, 200_000, 4, 500_000).payback_months, 3.0)

    def test_weeks_bounds(self):
        for weeks in (0, 53, 60):
            with self.subTest(weeks=weeks), self.assertRaises(ValueError):
                calculate_roi(1, 1, 1, 1, working_weeks=weeks)
        for weeks in (1, 52):
            with self.subTest(weeks=weeks):
                self.assertEqual(calculate_roi(1, 1, 1, 1, working_weeks=weeks).working_weeks, weeks)

    def test_rejects_non_finite_inputs(self):
        base = dict(engineers=1, loaded_annual_cost=1, hours_saved_per_week=1,
                    annual_tool_cost=1, working_weeks=46, hours_per_week=40)
        for name in base:
            for value in (float("nan"), float("inf"), float("-inf")):
                kwargs = dict(base, **{name: value})
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    calculate_roi(**kwargs)

    def test_error_messages_use_cli_names(self):
        cases = [
            (dict(engineers=0), "--engineers must be greater than 0"),
            (dict(loaded_annual_cost=0), "--loaded-cost must be a number greater than 0"),
            (dict(annual_tool_cost=float("nan")), "--tool-cost must be a number greater than 0"),
            (dict(working_weeks=53), "--weeks must be between 1 and 52"),
            (dict(hours_saved_per_week=41),
             "--hours-saved must be between 0 and 40 (the hours in a working week)"),
            (dict(hours_saved_per_week=36, hours_per_week=35),
             "--hours-saved must be between 0 and 35 (the hours in a working week)"),
        ]
        base = dict(engineers=1, loaded_annual_cost=1, hours_saved_per_week=1, annual_tool_cost=1)
        for overrides, message in cases:
            with self.subTest(overrides=overrides):
                with self.assertRaises(ValueError) as ctx:
                    calculate_roi(**dict(base, **overrides))
                self.assertEqual(str(ctx.exception), message)


# === End of calculation and validation tests ===


# === Report and summary output tests ===


# === End of report and summary output tests ===


# === Command-line tests ===


# === End of command-line tests ===


if __name__ == "__main__":
    unittest.main()
