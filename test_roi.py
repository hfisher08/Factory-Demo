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
        self.assertIn("Estimated value of time saved: $2,000,000", summary)
        self.assertNotIn("£", summary)

    def test_summary_and_html_use_chosen_currency(self):
        for code, symbol in (("GBP", "£"), ("EUR", "€")):
            with self.subTest(currency=code):
                summary = format_summary(self.result, code)
                self.assertIn(f"Estimated value of time saved: {symbol}2,000,000", summary)
                self.assertIn(f"Engineer hourly cost:          {symbol}108.70", summary)
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


class ReportOutputTest(unittest.TestCase):
    def setUp(self):
        self.result = calculate_roi(100, 200_000, 4, 500_000)

    def test_html_has_inputs_table_in_chosen_currency(self):
        r = calculate_roi(12, 150_000, 4.5, 60_000, working_weeks=44, hours_per_week=37.5)
        for code, symbol in (("USD", "$"), ("GBP", "£"), ("EUR", "€")):
            with self.subTest(currency=code):
                page = render_html("Acme", r, code)
                self.assertIn("<h2>Inputs and assumptions</h2>", page)
                inputs = page.split('<table class="inputs">', 1)[1].split("</table>", 1)[0]
                for label, value in (
                    ("Engineers", "12"),
                    ("Fully loaded annual cost per engineer", f"{symbol}150,000"),
                    ("Hours saved per engineer per week", "4.5"),
                    ("Working weeks per year", "44"),
                    ("Hours per working week", "37.5"),
                    ("Annual tool cost", f"{symbol}60,000"),
                ):
                    self.assertIn(f"<tr><th>{label}</th><td>{value}</td></tr>", inputs)
                self.assertIn(f"All amounts are in {code} ({symbol}). "
                              "No exchange-rate conversion is applied.", page)

    def test_renamed_labels_in_summary_and_html(self):
        summary = format_summary(self.result)
        page = render_html("Acme", self.result)
        for old, new in (("Annual value created", "Estimated value of time saved"),
                         ("Net annual value", "Estimated net annual value")):
            with self.subTest(label=new):
                self.assertIn(new, summary)
                self.assertIn(f"<th>{new}</th>", page)
                self.assertNotIn(old, summary)
                self.assertNotIn(old, page)

    def test_summary_values_are_aligned(self):
        lines = format_summary(self.result).splitlines()
        columns = {line.index("$") if "$" in line else None for line in lines}
        columns.discard(None)
        self.assertEqual(len(columns), 1)

    def test_html_lists_caveats(self):
        page = render_html("Acme", self.result)
        self.assertIn("<h2>Caveats</h2>", page)
        for phrase in ("every hour saved becomes productive work",
                       "no ramp-up, so the payback period is a best case",
                       "excludes implementation, training and review costs",
                       "tool cost as recurring every year"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, page)
        self.assertNotIn("typical", page.lower())

    def test_near_zero_negative_roi_shows_zero(self):
        r = calculate_roi(1, 100_000, 4, 10_001)
        self.assertLess(r.roi_percent, 0)
        summary = format_summary(r)
        page = render_html("Acme", r)
        self.assertNotIn("-0%", summary)
        self.assertNotIn("-0%", page)
        self.assertIn("ROI:", summary)
        self.assertTrue(summary.splitlines()[5].endswith(" 0%"))
        self.assertIn('<div class="big">0% ROI</div>', page)
        self.assertIn("<tr><th>ROI</th><td>0%</td></tr>", page)

    def test_negative_roi_keeps_sign(self):
        r = calculate_roi(10, 150_000, 0, 50_000)
        self.assertIn("-100%", format_summary(r))

    def test_html_has_rounding_footnote(self):
        page = render_html("Acme", self.result)
        self.assertIn("Figures are rounded for display. Totals are calculated "
                      "from unrounded values", page)

    def test_not_paying_back_wording(self):
        r = calculate_roi(10, 150_000, 0, 50_000)
        wording = "Does not pay back (value is below cost)"
        self.assertIn(wording, format_summary(r))
        self.assertIn(f"<td>{wording}</td>", render_html("Acme", r))
        self.assertNotIn("never", format_summary(r))

    def test_finite_payback_wording(self):
        self.assertIn("3.0 months", format_summary(self.result))

    def test_html_escapes_customer_name_in_all_places(self):
        page = render_html('<b>"A&B"</b>', self.result, "GBP")
        self.assertNotIn("<b>", page)
        self.assertEqual(page.count("&lt;b&gt;&quot;A&amp;B&quot;&lt;/b&gt;"), 2)


# === End of report and summary output tests ===


# === Command-line tests ===


BASE_ARGS = ["--engineers", "100", "--loaded-cost", "200000",
             "--tool-cost", "500000"]


def run_cli(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(args)
    return code, out.getvalue(), err.getvalue()


class CommandLineTest(unittest.TestCase):
    def test_warns_when_hours_saved_above_20_percent(self):
        code, out, err = run_cli(BASE_ARGS + ["--hours-saved", "10"])
        self.assertEqual(code, 0)
        self.assertIn("Warning: --hours-saved 10 is 25% of a 40-hour week", err)
        self.assertNotIn("Warning", out)
        self.assertIn("ROI estimate for", out)

    def test_no_warning_at_exactly_8_hours(self):
        code, _, err = run_cli(BASE_ARGS + ["--hours-saved", "8"])
        self.assertEqual(code, 0)
        self.assertEqual(err, "")

    def test_help_uses_currency_not_dollars(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as ctx:
            main(["--help"])
        self.assertEqual(ctx.exception.code, 0)
        text = " ".join(out.getvalue().split())
        self.assertNotIn("dollars", text)
        self.assertIn("in the chosen --currency", text)

    def test_bad_html_path_exits_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "missing", "report.html")
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                    self.assertRaises(SystemExit) as ctx:
                main(BASE_ARGS + ["--hours-saved", "4", "--html", path])
        self.assertEqual(ctx.exception.code, 2)
        self.assertIn(f"could not write HTML report to {path}: "
                      "No such file or directory", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())
        self.assertNotIn("ROI estimate", out.getvalue())

    def test_blank_customer_falls_back_to_prospect(self):
        for name in ("", "   "):
            with self.subTest(name=repr(name)), tempfile.TemporaryDirectory() as tmp:
                path = os.path.join(tmp, "report.html")
                code, out, _ = run_cli(BASE_ARGS + ["--hours-saved", "4",
                                                    "--customer", name, "--html", path])
                self.assertEqual(code, 0)
                self.assertIn("ROI estimate for Prospect\n", out)
                with open(path, encoding="utf-8") as f:
                    page = f.read()
                self.assertIn("<title>ROI estimate for Prospect</title>", page)
                self.assertIn("Prospect</h1>", page)

    def test_customer_name_is_stripped(self):
        _, out, _ = run_cli(BASE_ARGS + ["--hours-saved", "4", "--customer", "  Acme  "])
        self.assertIn("ROI estimate for Acme\n", out)


# === End of command-line tests ===


if __name__ == "__main__":
    unittest.main()
