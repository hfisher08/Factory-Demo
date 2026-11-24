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

Run the tests with `python3 -m unittest -v`.
