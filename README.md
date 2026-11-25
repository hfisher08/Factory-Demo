# ROI calculator

Estimates the annual value of an AI agent rollout for an engineering team.

```
python3 roi.py --customer "Acme" --engineers 100 --loaded-cost 200000 \
  --hours-saved 4 --tool-cost 500000 --html report.html
```

Add `--currency GBP` or `--currency EUR` to label money in pounds or euros (default `USD`).
Inputs are taken in that currency; no exchange-rate conversion is applied.

If `--hours-saved` is more than 20% of the working week (over 8 hours of a 40-hour
week), the tool prints a warning to stderr but still runs. Double-check such
figures before sharing them with a customer.

## Three-year view

The report leads with a three-year ROI that allows for a gradual rollout. By default,
adoption is 50% in year one, 80% in year two and 100% in year three. Change it with
`--ramp`, for example `--ramp 25,60,90`. Each value is a percentage from 0 to 100.

The tool cost is charged in full every year, paid at the start of the year, even while
adoption ramps up. "Payback in year one" is how many months of year-one value it takes
to cover that year's cost. The full-adoption figures (year 3 onwards) are also shown,
and are a best case.

Run the tests with `python3 -m unittest -v`.
