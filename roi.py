"""Estimate the value of AI agent adoption for an engineering team."""

import argparse
import html
import math
import sys
from dataclasses import dataclass


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


def calculate_roi(
    engineers: int,
    loaded_annual_cost: float,
    hours_saved_per_week: float,
    annual_tool_cost: float,
    working_weeks: int = 46,
    hours_per_week: float = 40,
) -> RoiResult:
    if not math.isfinite(engineers) or engineers <= 0:
        raise ValueError("--engineers must be greater than 0")
    if not math.isfinite(loaded_annual_cost) or loaded_annual_cost <= 0:
        raise ValueError("--loaded-cost must be a number greater than 0")
    if not math.isfinite(annual_tool_cost) or annual_tool_cost <= 0:
        raise ValueError("--tool-cost must be a number greater than 0")
    if not math.isfinite(working_weeks) or not 1 <= working_weeks <= 52:
        raise ValueError("--weeks must be between 1 and 52")
    if not math.isfinite(hours_per_week) or hours_per_week <= 0:
        raise ValueError("hours per week must be a number greater than 0")
    if not math.isfinite(hours_saved_per_week) or not (
        0 <= hours_saved_per_week <= hours_per_week
    ):
        raise ValueError(
            f"--hours-saved must be between 0 and {hours_per_week:g} "
            "(the hours in a working week)"
        )

    hourly_cost = loaded_annual_cost / (working_weeks * hours_per_week)
    hours_saved_per_year = engineers * hours_saved_per_week * working_weeks
    annual_value = hours_saved_per_year * hourly_cost
    net_value = annual_value - annual_tool_cost
    roi_percent = net_value / annual_tool_cost * 100
    # The tool cost recurs every year, so it only pays back if annual value exceeds it.
    payback_months = (
        annual_tool_cost / (annual_value / 12)
        if annual_value > annual_tool_cost
        else float("inf")
    )
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
    )


CURRENCY_SYMBOLS = {"USD": "$", "GBP": "£", "EUR": "€"}


def format_money(amount: float, currency: str = "USD", decimals: int = 0) -> str:
    symbol = CURRENCY_SYMBOLS[currency]
    sign = "-" if amount < 0 else ""
    return f"{sign}{symbol}{abs(amount):,.{decimals}f}"


def format_percent(value: float) -> str:
    # Rounding to an int first means values like -0.01 show as "0%", not "-0%".
    return f"{int(round(value)):,}%"


def format_number(value: float) -> str:
    if float(value).is_integer():
        return f"{value:,.0f}"
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def format_payback(payback_months: float) -> str:
    if math.isinf(payback_months):
        return "Does not pay back (value is below cost)"
    return f"{payback_months:.1f} months"


def summary_rows(result: RoiResult, currency: str = "USD"):
    return [
        ("Engineer hourly cost", format_money(result.hourly_cost, currency, 2)),
        ("Hours saved per year", f"{result.hours_saved_per_year:,.0f}"),
        ("Estimated value of time saved", format_money(result.annual_value, currency)),
        ("Annual tool cost", format_money(result.annual_cost, currency)),
        ("Estimated net annual value", format_money(result.net_value, currency)),
        ("ROI", format_percent(result.roi_percent)),
        ("Payback period", format_payback(result.payback_months)),
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
    ]


CAVEATS = (
    "It assumes every hour saved becomes productive work.",
    "It assumes full adoption from day one with no ramp-up, so the payback "
    "period is a best case.",
    "It excludes implementation, training and review costs.",
    "It treats the tool cost as recurring every year.",
)


def format_summary(result: RoiResult, currency: str = "USD") -> str:
    rows = summary_rows(result, currency)
    width = max(len(label) for label, _ in rows) + 2
    return "\n".join(f"{label + ':':<{width}}{value}" for label, value in rows)


def _table_rows(rows) -> str:
    return "".join(
        f"<tr><th>{html.escape(label)}</th><td>{html.escape(value)}</td></tr>"
        for label, value in rows
    )


def render_html(customer: str, result: RoiResult, currency: str = "USD") -> str:
    rows = _table_rows(summary_rows(result, currency))
    inputs = _table_rows(input_rows(result, currency))
    currency_note = html.escape(
        f"All amounts are in {currency} ({CURRENCY_SYMBOLS[currency]}). "
        "No exchange-rate conversion is applied."
    )
    caveats = "".join(f"<li>{html.escape(c)}</li>" for c in CAVEATS)
    roi = html.escape(format_percent(result.roi_percent))
    name = html.escape(customer)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>ROI estimate for {name}</title>
<style>
  body {{ font-family: -apple-system, Helvetica, Arial, sans-serif; max-width: 640px;
         margin: 48px auto; color: #1c1917; }}
  h1 {{ font-size: 24px; margin-bottom: 4px; }}
  h2 {{ font-size: 18px; margin: 40px 0 0; }}
  p {{ color: #57534e; margin-top: 0; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 24px; }}
  th, td {{ padding: 12px 8px; border-bottom: 1px solid #e7e5e4; text-align: left; }}
  td {{ text-align: right; font-variant-numeric: tabular-nums; font-weight: 600; }}
  .big {{ font-size: 40px; font-weight: 700; color: #ea580c; margin: 24px 0 0; }}
  .note {{ font-size: 14px; margin-top: 12px; }}
  ul {{ color: #57534e; padding-left: 20px; }}
  li {{ margin: 6px 0; }}
</style>
</head>
<body>
<h1>AI agent ROI estimate: {name}</h1>
<p>Illustrative estimate. Results depend entirely on the inputs used.</p>
<div class="big">{roi} ROI</div>
<table class="results">{rows}</table>
<p class="note">Figures are rounded for display. Totals are calculated from unrounded values, so displayed figures may not multiply out exactly.</p>
<h2>Inputs and assumptions</h2>
<table class="inputs">{inputs}</table>
<p class="note">{currency_note}</p>
<h2>Caveats</h2>
<p>This is an estimate, not a forecast.</p>
<ul class="caveats">{caveats}</ul>
</body>
</html>
"""


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--customer", default="Prospect")
    parser.add_argument("--engineers", type=int, required=True)
    parser.add_argument("--loaded-cost", type=float, required=True,
                        help="Fully loaded annual cost per engineer, in the chosen --currency")
    parser.add_argument("--hours-saved", type=float, required=True,
                        help="Hours saved per engineer per week")
    parser.add_argument("--tool-cost", type=float, required=True,
                        help="Annual cost of the tool, in the chosen --currency")
    parser.add_argument("--weeks", type=int, default=46)
    parser.add_argument("--currency", choices=sorted(CURRENCY_SYMBOLS), default="USD",
                        help="Currency for all money inputs and outputs. "
                             "Labels only: no exchange-rate conversion is applied.")
    parser.add_argument("--html", metavar="PATH", help="Also write an HTML report")
    args = parser.parse_args(argv)

    customer = args.customer.strip() or "Prospect"

    try:
        result = calculate_roi(args.engineers, args.loaded_cost, args.hours_saved,
                               args.tool_cost, working_weeks=args.weeks)
    except ValueError as exc:
        parser.error(str(exc))

    if result.hours_saved_per_week > 0.2 * result.hours_per_week:
        share = result.hours_saved_per_week / result.hours_per_week * 100
        print(f"Warning: --hours-saved {result.hours_saved_per_week:g} is {share:.0f}% "
              f"of a {result.hours_per_week:g}-hour week. A customer may see this as "
              "unrealistic; double-check it before sharing.", file=sys.stderr)

    # Write the report before printing so a bad path fails cleanly, not mid-output.
    if args.html:
        try:
            with open(args.html, "w", encoding="utf-8") as f:
                f.write(render_html(customer, result, args.currency))
        except OSError as exc:
            parser.error(f"could not write HTML report to {args.html}: "
                         f"{exc.strerror or exc}")

    print(f"ROI estimate for {customer}\n")
    print(format_summary(result, args.currency))
    if args.html:
        print(f"\nHTML report written to {args.html}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
