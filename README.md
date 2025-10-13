# price-data-processing
## Install dependencies
```
pip install -r requirements.txt
```

## Directory Structure
```
Parameta/
├── requirements.txt
├── rates_test/
|   ├── data/
|   │   ├── rates_ccy_data.csv
|   │   ├── rates_price_data.parq.gzip
|   │   └── rates_spot_rate_data.parq.gzip
|   ├── results/
|   │   └── final_rates.csv
|   └── scripts/
|       ├── main_rates.py
|       └── rates_processor.py
└── stdev_test
    ├── data
    |   └── stdev_price_data.parq.gzip
    ├── results
    |   └── stdev_results.csv
    └── scripts
        ├── main_stdev.py
        └── stdev_processor.py
```

## Problem 1 – Rates Processing

Computes converted prices based on provided currency pair and spot rate data.

Data Files:
- rates_ccy_data.csv: Reference file for currency pairs.
- rates_price_data.parq.gzip: Timestamped price data for the currency pairs.
- rates_spot_rate_data.parq.gzip: Timestamped spot rates with spot_mid_rate column.


### Solution
Conversion rules:
- If conversion not required → use existing price.

- If conversion required → (price / conversion_factor) + spot_mid_rate.

- If data insufficient → mark as insufficient_data.

- Uses merge_asof to attach the most recent spot rate within 1 hour before each price timestamp.

- Fallback per-currency-pair merge.

- Output is saved as results/final_rates.csv.

- Handles missing spot rates and conversion factors.

### Run
Run the pipeline from the command line from folder root:

`python Parameta/rates_test/scripts/main_rates.py [--data-dir DATA_DIR] [--results-dir RESULTS_DIR] [--verbose]`

Optional args: 

--data-dir: Path to input data (default: data/)

--results-dir: Path to output CSV (default: results/)

--verbose: Prints detailed INFO

```
python Parameta/rates_test/scripts/main_rates.py
```


## Problem 2 – Standard Deviation Problem

Data File:
- stdev_price_data.parq.gzip: contains snap_time, bid, mid, and ask prices for multiple security_ids.

### Goal: 
- For each security_id at each hourly snapshot, compute the rolling 20-hour standard deviation for bids, mids, and asks.

- Only contiguous hourly snapshots are considered. A missing hour breaks the window.

- Output all possible hourly snapshots present in the dataset.

- Save the results as a CSV file in the results/ folder (stdev_results.csv).

### Processing Notes:

The current implementation recalculates the rolling standard deviation from scratch at each snapshot.

The solution is class-based, using StdevProcessor, and can be run via the main_stdev.py script.

### Run

Run the pipeline from the command line from the folder root:

`python Parameta/stdev_test/scripts/main_stdev.py [--data-path DATA_PATH] [--results-dir RESULTS_DIR] [--verbose]`

Optional args:

--data-path: Path to input Parquet file (default: data/stdev_price_data.parq.gzip)

--results-dir: Path to output CSV (default: results/)

--verbose: Prints detailed INFO

```
python Parameta/stdev_test/scripts/main_stdev.py --verbose
```

Benchmark: computation completes in < 1 second on a 16GB RAM machine.