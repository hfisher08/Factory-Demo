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
- CI: GitHub Actions runs the same tests on Python 3.9 and 3.12 on every push to
  `main` and every pull request. Keep the suite green before pushing.
- Sample run: `python3 roi.py --customer "Acme" --engineers 100 --loaded-cost 200000 --hours-saved 4 --tool-cost 500000 --html report.html`

## Notes

- `report.html` is generated output and is ignored by git.
- `docs/` is published publicly via GitHub Pages. Generated reports committed there
  are live at `https://hfisher08.github.io/Factory-Demo/<file>` within a minute of
  pushing. Never commit real customer data to `docs/` without the customer's ok.
- The report's inline JavaScript recalculates every figure live in the browser. It
  must mirror `calculate_roi` and the `format_*` helpers, and stay free of external
  dependencies. When you change a calculation, wording or format, change both sides.
- `FACTORY_WORDMARK` and `FACTORY_MARK` are the official logos from factory.ai,
  embedded as inline SVG so reports stay self-contained. Update them if the brand
  changes; keep `fill="currentColor"` so they follow the page's text colour.
