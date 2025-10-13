# price-data-processing
## Install dependencies
```
pip install -r requirements.txt
```

## Directory Structure
```
Parameta/
├── requirements.txt
└── rates_test/
    ├── data/
    │   ├── rates_ccy_data.csv
    │   ├── rates_price_data.parq.gzip
    │   └── rates_spot_rate_data.parq.gzip
    ├── results/
    │   └── final_rates.csv
    └── scripts/
        ├── main_rates.py
        └── rates_processor.py
```

## Problem 1 – Rates Processing

Computes converted prices based on provided currency pair and spot rate data.

Data Files:
- rates_ccy_data.csv: Reference file for currency pairs.
- rates_price_data.parq.gzip: Timestamped price data for the currency pairs.
- rates_spot_rate_data.parq.gzip: Timestamped spot rates with spot_mid_rate column.


## Solution
Conversion rules:
- If conversion not required → use existing price.

- If conversion required → (price / conversion_factor) + spot_mid_rate.

- If data insufficient → mark as insufficient_data.

- Uses merge_asof to attach the most recent spot rate within 1 hour before each price timestamp.

- Fallback per-currency-pair merge.

- Output is saved as results/final_rates.csv.


## Run
Run the pipeline from the command line from folder root:

`python Parameta/rates_test/scripts/main_rates.py [--data-dir DATA_DIR] [--results-dir RESULTS_DIR] [--verbose]`

Optional args: 

--data-dir: Path to input data (default: data/)

--results-dir: Path to output CSV (default: results/)

--verbose: Prints detailed INFO

```
python Parameta/rates_test/scripts/main_rates.py
```

Notes:
- Benchmark: computation completes in < 1 second on a 16GB RAM machine.
- Handles missing spot rates and conversion factors.