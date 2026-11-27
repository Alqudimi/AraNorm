# Annotate findings (round 17)

annotate output in this coverage version marks EVERY executed line with '>'
and unexecuted with '!'. It is NOT a reliable partial-branch indicator
(unlike older versions where '>' meant partial). The ONLY reliable source
for partials is coverage json: num_partial_branches=26, num_missing=2.

Reliable next step: per-test branch coverage diffing.
- Measure partial lines per module before/after running each new test.
- Use coverage run --branch on a single test file, then json + annotate
  compare of partial counts.

Known targets (from json totals):
- cli.py missing_lines=[352]: sentiment file-not-found — we have a test
  (test_cli_sentiment_file_not_found) that passes with rc==1, but the branch
  at 352 shows as missing when measured alone?? Actually when running full
  suite missing=2. Need per-module per-line recheck after full clean run.
