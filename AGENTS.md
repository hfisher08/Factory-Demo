# ROI calculator: agent guide

Command-line tool (`roi.py`) that estimates the annual value of an AI agent rollout
and can write an HTML report. Tests live in `test_roi.py`.

## Rules

- Use only the Python standard library. Do not add third-party packages.
- Stay compatible with Python 3.9: no `match` statements, no `X | Y` type unions,
  no other syntax or library features newer than 3.9.
- Every new feature needs at least one test in `test_roi.py`.
- Before saying you're finished, run the tests and confirm they all pass:
  `python3 -m unittest -v`

## Commands

- Run tests: `python3 -m unittest -v`
- Sample run: `python3 roi.py --customer "Acme" --engineers 100 --loaded-cost 200000 --hours-saved 4 --tool-cost 500000 --html report.html`

## Notes

- `report.html` is generated output and is ignored by git.
- The report's inline JavaScript recalculates every figure live in the browser. It
  must mirror `calculate_roi` and the `format_*` helpers, and stay free of external
  dependencies. When you change a calculation, wording or format, change both sides.
