# ROI calculator

Estimates the annual value of an AI agent rollout for an engineering team.

```
python3 roi.py --customer "Acme" --engineers 100 --loaded-cost 200000 \
  --hours-saved 4 --tool-cost 500000 --html report.html
```

Add `--currency GBP` or `--currency EUR` to label money in pounds or euros (default `USD`).
Inputs are taken in that currency; no exchange-rate conversion is applied.

Run the tests with `python3 -m unittest -v`.
