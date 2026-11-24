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


def format_summary(result: RoiResult, currency: str = "USD") -> str:
    payback = (
        "never" if result.payback_months == float("inf")
        else f"{result.payback_months:.1f} months"
    )
    return "\n".join([
        f"Engineer hourly cost:   {format_money(result.hourly_cost, currency, 2)}",
        f"Hours saved per year:   {result.hours_saved_per_year:,.0f}",
        f"Annual value created:   {format_money(result.annual_value, currency)}",
        f"Annual tool cost:       {format_money(result.annual_cost, currency)}",
        f"Net annual value:       {format_money(result.net_value, currency)}",
        f"ROI:                    {result.roi_percent:,.0f}%",
        f"Payback period:         {payback}",
    ])


def render_html(customer: str, result: RoiResult, currency: str = "USD") -> str:
    rows = "".join(
        f"<tr><th>{html.escape(label)}</th><td>{html.escape(value.strip())}</td></tr>"
        for label, value in (
            line.split(":", 1)
            for line in format_summary(result, currency).splitlines()
        )
    )
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
  p {{ color: #57534e; margin-top: 0; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 24px; }}
  th, td {{ padding: 12px 8px; border-bottom: 1px solid #e7e5e4; text-align: left; }}
  td {{ text-align: right; font-variant-numeric: tabular-nums; font-weight: 600; }}
  .big {{ font-size: 40px; font-weight: 700; color: #ea580c; margin: 24px 0 0; }}
</style>
</head>
<body>
<h1>AI agent ROI estimate: {name}</h1>
<p>Illustrative estimate. Results depend entirely on the inputs used.</p>
<div class="big">{result.roi_percent:,.0f}% ROI</div>
<table>{rows}</table>
</body>
</html>
"""


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--customer", default="Prospect")
    parser.add_argument("--engineers", type=int, required=True)
    parser.add_argument("--loaded-cost", type=float, required=True,
                        help="Fully loaded annual cost per engineer, in dollars")
    parser.add_argument("--hours-saved", type=float, required=True,
                        help="Hours saved per engineer per week")
    parser.add_argument("--tool-cost", type=float, required=True,
                        help="Annual cost of the tool, in dollars")
    parser.add_argument("--weeks", type=int, default=46)
    parser.add_argument("--currency", choices=sorted(CURRENCY_SYMBOLS), default="USD",
                        help="Currency for all money inputs and outputs. "
                             "Labels only: no exchange-rate conversion is applied.")
    parser.add_argument("--html", metavar="PATH", help="Also write an HTML report")
    args = parser.parse_args(argv)

    try:
        result = calculate_roi(args.engineers, args.loaded_cost, args.hours_saved,
                               args.tool_cost, working_weeks=args.weeks)
    except ValueError as exc:
        parser.error(str(exc))

    print(f"ROI estimate for {args.customer}\n")
    print(format_summary(result, args.currency))
    if args.html:
        with open(args.html, "w", encoding="utf-8") as f:
            f.write(render_html(args.customer, result, args.currency))
        print(f"\nHTML report written to {args.html}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
