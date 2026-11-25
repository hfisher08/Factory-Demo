"""Estimate the value of AI agent adoption for an engineering team."""

import argparse
import decimal
import html
import math
import sys
from dataclasses import dataclass
from typing import List, Sequence, Tuple


@dataclass
class YearResult:
    year: int
    adoption_percent: float
    value: float
    cost: float
    net: float
    cumulative_net: float


@dataclass
class RoiResult:
    hourly_cost: float
    hours_saved_per_year: float
    annual_value: float
    annual_cost: float
    net_value: float
    roi_percent: float
    payback_months: float
    engineers: int
    loaded_annual_cost: float
    hours_saved_per_week: float
    working_weeks: int
    hours_per_week: float
    ramp: Tuple[float, float, float]
    years: List[YearResult]
    three_year_value: float
    three_year_cost: float
    three_year_net: float
    three_year_roi_percent: float
    first_year_payback_months: float


DEFAULT_RAMP = (50.0, 80.0, 100.0)
RAMP_ERROR = "--ramp must be three percentages from 0 to 100, for example 50,80,100"
TOO_LARGE = "inputs are too large to produce a meaningful estimate"


def _too_large(value) -> bool:
    # Python ints can exceed the float range; math.isfinite would raise on them.
    try:
        float(value)
    except OverflowError:
        return True
    return False


def _is_finite(value) -> bool:
    return math.isfinite(value)


def _validate_ramp(ramp: Sequence[float]) -> Tuple[float, float, float]:
    try:
        values = tuple(ramp)
    except TypeError:
        raise ValueError(RAMP_ERROR) from None
    if len(values) != 3:
        raise ValueError(RAMP_ERROR)
    for v in values:
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ValueError(RAMP_ERROR)
        if _too_large(v) or not _is_finite(v) or not 0 <= v <= 100:
            raise ValueError(RAMP_ERROR)
    # Adding 0.0 turns -0.0 into 0.0 so it never displays as "-0%".
    return tuple(float(v) + 0.0 for v in values)


def parse_ramp(text: str) -> Tuple[float, float, float]:
    try:
        values = [float(part) for part in text.split(",")]
    except ValueError:
        raise ValueError(RAMP_ERROR) from None
    return _validate_ramp(values)


def _payback_months(annual_tool_cost: float, annual_value: float) -> float:
    # The licence is paid at the start of each year, so it only pays back within
    # a year if that year's value exceeds the cost.
    if annual_value > annual_tool_cost:
        return annual_tool_cost / (annual_value / 12)
    return float("inf")


def calculate_roi(
    engineers: int,
    loaded_annual_cost: float,
    hours_saved_per_week: float,
    annual_tool_cost: float,
    working_weeks: int = 46,
    hours_per_week: float = 40,
    ramp: Sequence[float] = DEFAULT_RAMP,
) -> RoiResult:
    inputs = (engineers, loaded_annual_cost, hours_saved_per_week, annual_tool_cost,
              working_weeks, hours_per_week)
    if any(_too_large(v) for v in inputs):
        raise ValueError(TOO_LARGE)
    if not _is_finite(engineers) or engineers <= 0:
        raise ValueError("--engineers must be greater than 0")
    if not _is_finite(loaded_annual_cost) or loaded_annual_cost <= 0:
        raise ValueError("--loaded-cost must be a number greater than 0")
    if not _is_finite(annual_tool_cost) or annual_tool_cost <= 0:
        raise ValueError("--tool-cost must be a number greater than 0")
    if not _is_finite(working_weeks) or not 1 <= working_weeks <= 52:
        raise ValueError("--weeks must be between 1 and 52")
    if not _is_finite(hours_per_week) or hours_per_week <= 0:
        raise ValueError("hours per week must be a number greater than 0")
    if not _is_finite(hours_saved_per_week) or not (
        0 <= hours_saved_per_week <= hours_per_week
    ):
        raise ValueError(
            f"--hours-saved must be between 0 and {hours_per_week:g} "
            "(the hours in a working week)"
        )
    ramp = _validate_ramp(ramp)

    hourly_cost = loaded_annual_cost / (working_weeks * hours_per_week)
    hours_saved_per_year = engineers * hours_saved_per_week * working_weeks
    annual_value = hours_saved_per_year * hourly_cost
    net_value = annual_value - annual_tool_cost
    roi_percent = net_value / annual_tool_cost * 100
    payback_months = _payback_months(annual_tool_cost, annual_value)

    years = []
    cumulative_net = 0.0
    for year, adoption in enumerate(ramp, start=1):
        value = annual_value * adoption / 100
        net = value - annual_tool_cost
        cumulative_net += net
        years.append(YearResult(year, adoption, value, annual_tool_cost, net, cumulative_net))
    three_year_value = sum(y.value for y in years)
    three_year_cost = annual_tool_cost * len(years)
    three_year_net = three_year_value - three_year_cost
    three_year_roi_percent = three_year_net / three_year_cost * 100
    first_year_payback_months = _payback_months(annual_tool_cost, years[0].value)

    # Finite inputs can still overflow, e.g. a loaded cost of 1e308.
    if not all(_is_finite(v) for v in (hourly_cost, annual_value, net_value, roi_percent,
                                       three_year_value, three_year_cost,
                                       three_year_net, three_year_roi_percent)):
        raise ValueError(TOO_LARGE)
    return RoiResult(
        hourly_cost=hourly_cost,
        hours_saved_per_year=hours_saved_per_year,
        annual_value=annual_value,
        annual_cost=annual_tool_cost,
        net_value=net_value,
        roi_percent=roi_percent,
        payback_months=payback_months,
        engineers=engineers,
        loaded_annual_cost=loaded_annual_cost,
        hours_saved_per_week=hours_saved_per_week,
        working_weeks=working_weeks,
        hours_per_week=hours_per_week,
        ramp=ramp,
        years=years,
        three_year_value=three_year_value,
        three_year_cost=three_year_cost,
        three_year_net=three_year_net,
        three_year_roi_percent=three_year_roi_percent,
        first_year_payback_months=first_year_payback_months,
    )


CURRENCY_SYMBOLS = {"USD": "$", "GBP": "£", "EUR": "€"}


def format_money(amount: float, currency: str = "USD", decimals: int = 0) -> str:
    symbol = CURRENCY_SYMBOLS[currency]
    # Round before taking the sign so tiny negatives don't display as "-£0".
    rounded = round(amount, decimals)
    sign = "-" if rounded < 0 else ""
    return f"{sign}{symbol}{abs(rounded):,.{decimals}f}"


def format_percent(value: float) -> str:
    # Round halves away from zero (187.5 -> 188, 12.5 -> 13), as a reader checking by
    # hand would; Python's round() would give 12. int() also turns -0 into 0.
    rounded = decimal.Decimal(value).quantize(decimal.Decimal(1), decimal.ROUND_HALF_UP)
    return f"{int(rounded):,}%"


def format_number(value: float) -> str:
    if float(value).is_integer():
        return f"{value:,.0f}"
    return f"{value:,.6f}".rstrip("0").rstrip(".")


def format_adoption(value: float) -> str:
    return f"{format_number(value)}%"


def format_ramp(ramp: Sequence[float], separator: str = " / ") -> str:
    return separator.join(format_adoption(v) for v in ramp)


def format_ramp_words(ramp: Sequence[float]) -> str:
    first, second, third = (format_adoption(v) for v in ramp)
    return f"{first}, {second} and {third}"


def format_payback(payback_months: float,
                   never: str = "Does not pay back (value does not exceed cost)") -> str:
    if math.isinf(payback_months):
        return never
    return f"{payback_months:.1f} months"


def format_first_year_payback(result: RoiResult) -> str:
    return format_payback(result.first_year_payback_months,
                          "Does not pay back in year one")


def summary_rows(result: RoiResult, currency: str = "USD"):
    return [
        ("Engineer hourly cost", format_money(result.hourly_cost, currency, 2)),
        ("Hours saved per year", f"{result.hours_saved_per_year:,.0f}"),
        ("Estimated value of time saved", format_money(result.annual_value, currency)),
        ("Annual tool cost", format_money(result.annual_cost, currency)),
        ("Estimated net annual value", format_money(result.net_value, currency)),
        ("Annual ROI at full adoption", format_percent(result.roi_percent)),
        ("Payback at full adoption", format_payback(result.payback_months)),
    ]


def three_year_summary_rows(result: RoiResult):
    return [
        ("Three-year ROI", format_percent(result.three_year_roi_percent)),
        ("Payback in year one", format_first_year_payback(result)),
    ]


def input_rows(result: RoiResult, currency: str = "USD"):
    return [
        ("Engineers", format_number(result.engineers)),
        ("Fully loaded annual cost per engineer",
         format_money(result.loaded_annual_cost, currency)),
        ("Hours saved per engineer per week", format_number(result.hours_saved_per_week)),
        ("Working weeks per year", format_number(result.working_weeks)),
        ("Hours per working week", format_number(result.hours_per_week)),
        ("Annual tool cost", format_money(result.annual_cost, currency)),
        ("Adoption ramp (years 1–3)", format_ramp(result.ramp)),
    ]


ROUNDING_NOTE = (
    "Figures are rounded for display. Totals are calculated from unrounded values, "
    "so displayed figures may not multiply or add up exactly."
)


def full_adoption_heading(result: RoiResult) -> str:
    if result.ramp[2] == 100:
        return "At full adoption (year 3 onwards)"
    return "At full adoption (100%)"


def headline_subline(result: RoiResult) -> str:
    ramp = f"Adoption by year: {format_ramp(result.ramp, ' → ')}."
    full = format_percent(result.roi_percent)
    if result.ramp[2] == 100:
        return f"{ramp} At full adoption: {full} a year."
    return f"{ramp} Full adoption is not reached; at 100% the annual ROI would be {full}."


def caveats(result: RoiResult) -> Tuple[str, ...]:
    return (
        "It assumes every hour saved becomes productive work.",
        f"The three-year view assumes adoption of {format_ramp_words(result.ramp)} in "
        "years one to three. The full-adoption figures assume no ramp-up, so they are "
        "a best case.",
        "It treats the tool cost as recurring every year, paid at the start of each "
        "year, at the full price even while adoption ramps up.",
        "Three-year figures are simple totals; they are not discounted for the time "
        "value of money.",
        "It excludes implementation, training and review costs.",
    )


def _aligned(rows) -> str:
    width = max(len(label) for label, _ in rows) + 2
    return "\n".join(f"{label + ':':<{width}}{value}" for label, value in rows)


def format_summary(result: RoiResult, currency: str = "USD") -> str:
    return _aligned(summary_rows(result, currency))


def format_three_year(result: RoiResult, currency: str = "USD") -> str:
    money = lambda amount: format_money(amount, currency)  # noqa: E731
    rows = [
        (f"Year {y.year} at {format_adoption(y.adoption_percent)} adoption",
         f"value {money(y.value)}, cost {money(y.cost)}, net {money(y.net)}, "
         f"cumulative net {money(y.cumulative_net)}")
        for y in result.years
    ]
    rows.append(("Three-year total",
                 f"value {money(result.three_year_value)}, "
                 f"cost {money(result.three_year_cost)}, "
                 f"net {money(result.three_year_net)}"))
    rows.extend(three_year_summary_rows(result))
    heading = (f"Three-year view (adoption {format_ramp(result.ramp, ' → ')}, "
               "tool cost fixed each year)")
    return f"{heading}\n{_aligned(rows)}"


def _table_rows(rows) -> str:
    return "".join(
        f"<tr><th>{html.escape(label)}</th><td>{html.escape(value)}</td></tr>"
        for label, value in rows
    )


def _three_year_table(result: RoiResult, currency: str) -> str:
    def cells(values):
        return "".join(f"<td>{html.escape(v)}</td>" for v in values)

    money = lambda amount: format_money(amount, currency)  # noqa: E731
    head = "".join(f"<th>{h}</th>" for h in (
        "Year", "Adoption", "Estimated value of time saved", "Tool cost", "Net",
        "Cumulative net"))
    body = "".join(
        f"<tr><th>Year {y.year}</th>"
        + cells((format_adoption(y.adoption_percent), money(y.value), money(y.cost),
                 money(y.net), money(y.cumulative_net)))
        + "</tr>"
        for y in result.years
    )
    total = ('<tr class="total"><th>Total</th>'
             + cells(("", money(result.three_year_value), money(result.three_year_cost),
                      money(result.three_year_net), ""))
             + "</tr>")
    return (f'<table class="three-year"><thead><tr>{head}</tr></thead>'
            f"<tbody>{body}{total}</tbody></table>")


def render_html(customer: str, result: RoiResult, currency: str = "USD") -> str:
    three_year = _three_year_table(result, currency)
    three_year_summary = _table_rows(three_year_summary_rows(result))
    rows = _table_rows(summary_rows(result, currency))
    inputs = _table_rows(input_rows(result, currency))
    currency_note = html.escape(
        f"All amounts are in {currency} ({CURRENCY_SYMBOLS[currency]}). "
        "No exchange-rate conversion is applied."
    )
    caveat_items = "".join(f"<li>{html.escape(c)}</li>" for c in caveats(result))
    headline = html.escape(format_percent(result.three_year_roi_percent))
    subline = html.escape(headline_subline(result))
    full_heading = html.escape(full_adoption_heading(result))
    name = html.escape(customer)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>ROI estimate for {name}</title>
<style>
  body {{ font-family: -apple-system, Helvetica, Arial, sans-serif; max-width: 720px;
         margin: 48px auto; color: #1c1917; }}
  h1 {{ font-size: 24px; margin-bottom: 4px; }}
  h2 {{ font-size: 18px; margin: 40px 0 0; }}
  p {{ color: #57534e; margin-top: 0; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 24px; }}
  th, td {{ padding: 12px 8px; border-bottom: 1px solid #e7e5e4; text-align: left; }}
  td {{ text-align: right; font-variant-numeric: tabular-nums; font-weight: 600; }}
  .three-year {{ font-size: 14px; }}
  .three-year thead th {{ text-align: right; color: #57534e; font-weight: 600; }}
  .three-year thead th:first-child {{ text-align: left; }}
  .three-year td {{ font-weight: 400; }}
  .three-year .total th, .three-year .total td {{ font-weight: 700;
         border-top: 2px solid #1c1917; }}
  .big {{ font-size: 40px; font-weight: 700; color: #ea580c; margin: 24px 0 0; }}
  .sub {{ font-size: 15px; margin-top: 4px; }}
  .note {{ font-size: 14px; margin-top: 12px; }}
  ul {{ color: #57534e; padding-left: 20px; }}
  li {{ margin: 6px 0; }}
</style>
</head>
<body>
<h1>AI agent ROI estimate: {name}</h1>
<p>Illustrative estimate. Results depend entirely on the inputs used.</p>
<div class="big">{headline} three-year ROI</div>
<p class="sub">{subline}</p>
<h2>Three-year view</h2>
{three_year}
<table class="three-year-summary">{three_year_summary}</table>
<h2>{full_heading}</h2>
<table class="results">{rows}</table>
<p class="note">{html.escape(ROUNDING_NOTE)}</p>
<h2>Inputs and assumptions</h2>
<table class="inputs">{inputs}</table>
<p class="note">{currency_note}</p>
<h2>Caveats</h2>
<p>This is an estimate, not a forecast.</p>
<ul class="caveats">{caveat_items}</ul>
</body>
</html>
"""


HELP_EXAMPLE = ('python3 roi.py --customer "Acme Bank UK" --engineers 100 '
                '--loaded-cost 150000 --hours-saved 4 --tool-cost 400000 --currency GBP')


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=f"example:\n  {HELP_EXAMPLE}",
        # Keeps the example on one line so it can be copied and run as-is.
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--customer", default="Prospect",
                        help='Customer name shown on the report (default "Prospect")')
    parser.add_argument("--engineers", type=int, required=True,
                        help="Number of engineers using the tool")
    parser.add_argument("--loaded-cost", type=float, required=True,
                        help="Fully loaded annual cost per engineer, in the chosen --currency")
    parser.add_argument("--hours-saved", type=float, required=True,
                        help="Hours saved per engineer per week")
    parser.add_argument("--tool-cost", type=float, required=True,
                        help="Annual cost of the tool, in the chosen --currency")
    parser.add_argument("--weeks", type=int, default=46,
                        help="Working weeks per year, from 1 to 52 (default 46)")
    parser.add_argument("--ramp", default="50,80,100",
                        help="Adoption percentages for years one, two and three, "
                             "separated by commas (default 50,80,100)")
    parser.add_argument("--currency", choices=sorted(CURRENCY_SYMBOLS), default="USD",
                        help="Currency for all money inputs and outputs. "
                             "Labels only: no exchange-rate conversion is applied.")
    parser.add_argument("--html", metavar="PATH", help="Also write an HTML report")
    args = parser.parse_args(argv)

    customer = args.customer.strip() or "Prospect"

    try:
        ramp = parse_ramp(args.ramp)
        result = calculate_roi(args.engineers, args.loaded_cost, args.hours_saved,
                               args.tool_cost, working_weeks=args.weeks, ramp=ramp)
    except ValueError as exc:
        parser.error(str(exc))

    if result.hours_saved_per_week > 0.2 * result.hours_per_week:
        share = result.hours_saved_per_week / result.hours_per_week * 100
        print(f"Warning: --hours-saved {result.hours_saved_per_week:g} is "
              f"{round(share, 1):g}% "
              f"of a {result.hours_per_week:g}-hour week. A customer may see this as "
              "unrealistic; double-check it before sharing.", file=sys.stderr)

    # Write the report before printing so a bad path fails cleanly, not mid-output.
    if args.html is not None and not args.html.strip():
        parser.error("--html needs a file path, for example --html report.html")
    if args.html is not None:
        # Render first so a rendering error can't leave an empty file behind.
        page = render_html(customer, result, args.currency)
        try:
            with open(args.html, "w", encoding="utf-8") as f:
                f.write(page)
        except OSError as exc:
            parser.error(f"could not write HTML report to {args.html}: "
                         f"{exc.strerror or exc}")

    print(f"ROI estimate for {customer}\n")
    print(format_three_year(result, args.currency))
    print()
    print(full_adoption_heading(result))
    print(format_summary(result, args.currency))
    print(f"\n{ROUNDING_NOTE}")
    print("Estimate only: it assumes every hour saved becomes productive work and "
          f"adoption of {format_ramp_words(result.ramp)} in years one to three. "
          "Use --html for the full inputs and caveats.")
    if args.html is not None:
        print(f"\nHTML report written to {args.html}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
