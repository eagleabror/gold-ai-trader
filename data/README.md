# Local datasets

Only this policy file is tracked. Market CSVs, downloaded samples and generated
metadata stay outside Git through `.gitignore`. Models/artifacts are also ignored.

- `data/raw/`: user-supplied genuine historical CSV, with documented provenance.
- `data/synthetic-smoke/`: invented three-row code-validation example.
- `data/dukascopy-*/`: genuine downloaded data only after a successful acquisition.

Do not call a fixture real market data. Each generated bundle contains
`candles.csv` and `metadata.json`; keep them together. No genuine historical
sample is shipped or claimed in this repository. Do not include credentials in
source/reference metadata. Check provider terms before retaining or redistributing data.
