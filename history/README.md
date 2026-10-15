# Historical DSE price archive

Place yearly CSV files here, for example `2013.csv` through `2024.csv`.

Required columns: `DATE,TRADING CODE,OPENP,HIGH,LOW,CLOSEP,YCP,VOLUME`.

`scripts/phase_engine.py` loads every `history/*.csv` file together with `docs/data/prices.csv`. Duplicate `(DATE, TRADING CODE)` rows are resolved in favor of the current `docs/data/prices.csv` data. Keep the original year files here; daily updates only refresh `docs/data/prices.csv`.