import contextlib
import io
import os
import tempfile
import unittest

from roi import (calculate_roi, format_money, format_summary, format_three_year, main,
                 parse_ramp, render_html)


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
        with contextlib.redirect_stderr(io.StringIO()), \
                self.assertRaises(SystemExit) as ctx:
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

    def test_rejects_integer_too_large_for_float(self):
        with self.assertRaises(ValueError) as ctx:
            calculate_roi(10 ** 400, 1, 1, 1)
        self.assertEqual(str(ctx.exception),
                         "inputs are too large to produce a meaningful estimate")

    def test_rejects_inputs_that_overflow(self):
        with self.assertRaises(ValueError) as ctx:
            calculate_roi(100, 1e308, 4, 1)
        self.assertEqual(str(ctx.exception),
                         "inputs are too large to produce a meaningful estimate")


class ThreeYearCalculationTest(unittest.TestCase):
    def test_acme_gbp_example(self):
        # Full-adoption value is 100 * 4 * 150000 / 40 = 1,500,000 a year.
        r = calculate_roi(100, 150_000, 4, 400_000)
        self.assertEqual(r.ramp, (50.0, 80.0, 100.0))
        self.assertEqual([y.adoption_percent for y in r.years], [50, 80, 100])
        for y, value, net, cumulative in zip(
                r.years,
                (750_000, 1_200_000, 1_500_000),
                (350_000, 800_000, 1_100_000),
                (350_000, 1_150_000, 2_250_000)):
            with self.subTest(year=y.year):
                self.assertAlmostEqual(y.value, value)
                self.assertAlmostEqual(y.cost, 400_000)
                self.assertAlmostEqual(y.net, net)
                self.assertAlmostEqual(y.cumulative_net, cumulative)
        self.assertAlmostEqual(r.three_year_value, 3_450_000)
        self.assertAlmostEqual(r.three_year_cost, 1_200_000)
        self.assertAlmostEqual(r.three_year_net, 2_250_000)
        self.assertAlmostEqual(r.three_year_roi_percent, 187.5)
        self.assertAlmostEqual(r.first_year_payback_months, 6.4)
        # Full-adoption figures are unchanged by the ramp.
        self.assertAlmostEqual(r.roi_percent, 275)
        self.assertAlmostEqual(r.payback_months, 3.2)

    def test_worked_usd_example(self):
        r = calculate_roi(100, 200_000, 4, 500_000)
        self.assertAlmostEqual(r.three_year_value, 4_600_000)
        self.assertAlmostEqual(r.three_year_net, 3_100_000)
        self.assertAlmostEqual(r.three_year_roi_percent, 3_100_000 / 1_500_000 * 100)
        self.assertAlmostEqual(r.first_year_payback_months, 6.0)

    def test_custom_ramp(self):
        r = calculate_roi(100, 150_000, 4, 400_000, ramp=(25, 60, 90))
        self.assertEqual([y.value for y in r.years], [375_000, 900_000, 1_350_000])
        self.assertAlmostEqual(r.three_year_roi_percent, (2_625_000 - 1_200_000) / 1_200_000 * 100)
        self.assertAlmostEqual(r.first_year_payback_months, float("inf"))

    def test_zero_ramp(self):
        r = calculate_roi(100, 150_000, 4, 400_000, ramp=(0, 0, 0))
        self.assertEqual(r.three_year_value, 0)
        self.assertEqual(r.three_year_roi_percent, -100)
        self.assertEqual(r.first_year_payback_months, float("inf"))

    def test_year_one_value_at_or_below_cost_never_pays_back_in_year_one(self):
        # Year one at 50% of 800,000 equals the 400,000 cost exactly.
        equal = calculate_roi(100, 80_000, 4, 400_000)
        self.assertAlmostEqual(equal.years[0].value, 400_000)
        self.assertEqual(equal.first_year_payback_months, float("inf"))
        below = calculate_roi(100, 150_000, 1, 400_000)
        self.assertEqual(below.first_year_payback_months, float("inf"))

    def test_rejects_invalid_ramp(self):
        message = "--ramp must be three percentages from 0 to 100, for example 50,80,100"
        for ramp in ((50, 80), (50, 80, 100, 100), (50, 80, 101), (-1, 80, 100),
                     (float("nan"), 80, 100), (50, float("inf"), 100),
                     ("50", 80, 100), (True, 80, 100), (10 ** 400, 80, 100), 50):
            with self.subTest(ramp=ramp):
                with self.assertRaises(ValueError) as ctx:
                    calculate_roi(100, 150_000, 4, 400_000, ramp=ramp)
                self.assertEqual(str(ctx.exception), message)

    def test_parse_ramp(self):
        self.assertEqual(parse_ramp("50,80,100"), (50.0, 80.0, 100.0))
        self.assertEqual(parse_ramp(" 33.5 , 70, 100 "), (33.5, 70.0, 100.0))
        for text in ("", "50,80", "50,80,abc", "50;80;100", "50,80,1e400", "nan,80,100"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_ramp(text)


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
                       "adoption of 50%, 80% and 100% in years one to three",
                       "full-adoption figures assume no ramp-up, so they are a best case",
                       "paid at the start of each year, at the full price even while "
                       "adoption ramps up",
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
        self.assertIn("<tr><th>ROI</th><td>0%</td></tr>", page)
        self.assertIn("At full adoption: 0% a year.", page)

    def test_negative_roi_keeps_sign(self):
        r = calculate_roi(10, 150_000, 0, 50_000)
        self.assertIn("-100%", format_summary(r))

    def test_html_has_rounding_footnote(self):
        page = render_html("Acme", self.result)
        self.assertIn("Figures are rounded for display. Totals are calculated "
                      "from unrounded values", page)

    def test_not_paying_back_wording(self):
        r = calculate_roi(10, 150_000, 0, 50_000)
        wording = "Does not pay back (value does not exceed cost)"
        self.assertIn(wording, format_summary(r))
        self.assertIn(f"<td>{wording}</td>", render_html("Acme", r))
        self.assertNotIn("never", format_summary(r))

    def test_value_equal_to_cost_wording(self):
        r = calculate_roi(100, 200_000, 4, 2_000_000)
        summary = format_summary(r)
        self.assertIn("Does not pay back (value does not exceed cost)", summary)
        self.assertNotIn("below", summary)

    def test_money_never_shows_negative_zero(self):
        self.assertEqual(format_money(-0.4, "GBP"), "£0")
        self.assertEqual(format_money(-0.004, "USD", 2), "$0.00")
        self.assertEqual(format_money(-0.6, "EUR"), "-€1")
        r = calculate_roi(1, 100_000, 4, 10_000.4)
        self.assertNotIn("-$0", format_summary(r))
        self.assertNotIn("-$0", render_html("Acme", r))

    def test_inputs_show_value_as_entered(self):
        page = render_html("Acme", calculate_roi(1, 100_000, 4.125, 1))
        self.assertIn("<tr><th>Hours saved per engineer per week</th><td>4.125</td></tr>", page)

    def test_finite_payback_wording(self):
        self.assertIn("3.0 months", format_summary(self.result))

    def test_html_escapes_customer_name_in_all_places(self):
        page = render_html('<b>"A&B"</b>', self.result, "GBP")
        self.assertNotIn("<b>", page)
        self.assertEqual(page.count("&lt;b&gt;&quot;A&amp;B&quot;&lt;/b&gt;"), 2)


class ThreeYearReportTest(unittest.TestCase):
    def setUp(self):
        self.result = calculate_roi(100, 150_000, 4, 400_000)

    def test_headline_is_three_year_roi(self):
        page = render_html("Acme", self.result, "GBP")
        self.assertIn('<div class="big">188% three-year ROI</div>', page)
        self.assertIn("Adoption ramps 50% → 80% → 100%. At full adoption: 275% a year.", page)
        self.assertIn("<h2>At full adoption (year 3 onwards)</h2>", page)
        self.assertIn("<tr><th>Payback at full adoption</th><td>3.2 months</td></tr>", page)

    def test_three_year_table_in_each_currency(self):
        for code, s in (("USD", "$"), ("GBP", "£"), ("EUR", "€")):
            with self.subTest(currency=code):
                page = render_html("Acme", self.result, code)
                table = page.split('<table class="three-year">', 1)[1].split("</table>", 1)[0]
                self.assertIn(f"<tr><th>Year 1</th><td>50%</td><td>{s}750,000</td>"
                              f"<td>{s}400,000</td><td>{s}350,000</td><td>{s}350,000</td></tr>",
                              table)
                self.assertIn(f"<tr><th>Year 3</th><td>100%</td><td>{s}1,500,000</td>"
                              f"<td>{s}400,000</td><td>{s}1,100,000</td>"
                              f"<td>{s}2,250,000</td></tr>", table)
                self.assertIn(f'<tr class="total"><th>Total</th><td></td>'
                              f"<td>{s}3,450,000</td><td>{s}1,200,000</td>"
                              f"<td>{s}2,250,000</td><td></td></tr>", table)
                self.assertIn("<tr><th>Three-year ROI</th><td>188%</td></tr>", page)
                self.assertIn("<tr><th>Payback in year one</th><td>6.4 months</td></tr>", page)

    def test_inputs_show_ramp(self):
        r = calculate_roi(100, 150_000, 4, 400_000, ramp=(33.5, 70, 100))
        page = render_html("Acme", r)
        self.assertIn("<tr><th>Adoption ramp (years 1–3)</th>"
                      "<td>33.5% / 70% / 100%</td></tr>", page)
        self.assertIn("adoption of 33.5%, 70% and 100% in years one to three", page)

    def test_no_payback_in_year_one_wording(self):
        r = calculate_roi(100, 150_000, 4, 400_000, ramp=(0, 80, 100))
        self.assertIn("<td>Does not pay back in year one</td>", render_html("Acme", r))
        self.assertIn("Payback in year one:     Does not pay back in year one",
                      format_three_year(r))

    def test_no_negative_zero_anywhere(self):
        # Year 3 net is 10,000 - 10,000.4 = -0.4, which must show as $0.
        r = calculate_roi(1, 100_000, 4, 10_000.4, ramp=(100, 100, 100))
        for output in (render_html("Acme", r), format_three_year(r), format_summary(r)):
            self.assertNotIn("-$0", output)
            self.assertNotIn("-0%", output)

    def test_terminal_three_year_view(self):
        out = format_three_year(self.result, "GBP")
        self.assertIn("Three-year view (adoption 50% → 80% → 100%, tool cost fixed each year)",
                      out)
        self.assertIn("Year 2 at 80% adoption:  value £1,200,000, cost £400,000, net £800,000, "
                      "cumulative net £1,150,000", out)
        self.assertIn("Three-year ROI:          188%", out)


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

    def test_warning_share_is_not_rounded_down_to_threshold(self):
        _, _, err = run_cli(BASE_ARGS + ["--hours-saved", "8.1"])
        self.assertIn("--hours-saved 8.1 is 20.2% of a 40-hour week", err)

    def test_empty_html_path_is_an_error(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                self.assertRaises(SystemExit) as ctx:
            main(BASE_ARGS + ["--hours-saved", "4", "--html", ""])
        self.assertEqual(ctx.exception.code, 2)
        self.assertIn("--html needs a file path", err.getvalue())

    def test_overflowing_inputs_exit_cleanly_without_writing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "report.html")
            err = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err), \
                    self.assertRaises(SystemExit) as ctx:
                main(["--engineers", "100", "--loaded-cost", "1e308", "--hours-saved", "4",
                      "--tool-cost", "1", "--html", path])
            self.assertFalse(os.path.exists(path))
        self.assertEqual(ctx.exception.code, 2)
        self.assertIn("inputs are too large", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())

    def test_terminal_output_includes_rounding_note_and_caveat(self):
        _, out, _ = run_cli(BASE_ARGS + ["--hours-saved", "4"])
        self.assertIn("Figures are rounded for display.", out)
        self.assertIn("Estimate only:", out)

    def test_weeks_help_explains_range_and_default(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
            main(["--help"])
        self.assertIn("Working weeks per year, from 1 to 52 (default 46)",
                      " ".join(out.getvalue().split()))

    def test_customer_name_is_stripped(self):
        _, out, _ = run_cli(BASE_ARGS + ["--hours-saved", "4", "--customer", "  Acme  "])
        self.assertIn("ROI estimate for Acme\n", out)


class RampCommandLineTest(unittest.TestCase):
    ARGS = ["--engineers", "100", "--loaded-cost", "150000", "--hours-saved", "4",
            "--tool-cost", "400000", "--currency", "GBP"]

    def test_default_ramp(self):
        code, out, _ = run_cli(self.ARGS)
        self.assertEqual(code, 0)
        self.assertIn("Three-year ROI:          188%", out)
        self.assertIn("adoption of 50%, 80% and 100% in years one to three", out)

    def test_custom_ramp(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "report.html")
            code, out, _ = run_cli(self.ARGS + ["--ramp", "25,60,90", "--html", path])
            self.assertEqual(code, 0)
            self.assertIn("Year 1 at 25% adoption", out)
            with open(path, encoding="utf-8") as f:
                self.assertIn("25% / 60% / 90%", f.read())

    def test_bad_ramp_exits_cleanly(self):
        for ramp in ("50,80", "50,80,120", "a,b,c"):
            with self.subTest(ramp=ramp):
                err = io.StringIO()
                with contextlib.redirect_stdout(io.StringIO()), \
                        contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as ctx:
                    main(self.ARGS + ["--ramp", ramp])
                self.assertEqual(ctx.exception.code, 2)
                self.assertIn("--ramp must be three percentages from 0 to 100", err.getvalue())
                self.assertNotIn("Traceback", err.getvalue())

    def test_ramp_help(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
            main(["--help"])
        self.assertIn("Adoption percentages for years one, two and three, separated by "
                      "commas (default 50,80,100)", " ".join(out.getvalue().split()))


# === End of command-line tests ===


if __name__ == "__main__":
    unittest.main()
