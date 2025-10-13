import os
import time
import pandas as pd
import numpy as np
from pathlib import Path


class RatesProcessor:
    """Processes FX rate data and generates converted prices."""

    def __init__(self, data_dir: Path, results_dir: Path, verbose: bool = False):
        """Initialize processor with data and results directories."""
        self.data_dir = Path(data_dir).resolve()
        self.results_dir = Path(results_dir).resolve()
        self.verbose = verbose  # controls level of output

    def _log(self, message: str, level: str = "INFO"):
        """Print INFO only if verbose or if level is WARN/ERROR."""
        if self.verbose or level in {"WARN", "ERROR"}:
            print(f"[{level}] {message}")

    # Step 1: Load data
    def load_data(self):
        """Load datasets and validate structure."""
        try:
            self._log("Loading data...")
            self.ccy_df = pd.read_csv(self.data_dir / "rates_ccy_data.csv")
            self.price_df = pd.read_parquet(self.data_dir / "rates_price_data.parq.gzip")
            self.spot_df = pd.read_parquet(self.data_dir / "rates_spot_rate_data.parq.gzip")

            self._log(
                f"Loaded {len(self.price_df)} price rows, {len(self.spot_df)} spot rate rows, {len(self.ccy_df)} currency pairs."
            )
        except Exception as e:
            raise RuntimeError(f"Failed to load data: {e}")

    # Step 2: Prepare data
    def _prepare_data(self):
        """Normalize timestamps and ensure sorted input for merge_asof."""
        self.price_df["timestamp"] = pd.to_datetime(self.price_df["timestamp"], errors="coerce", utc=True)
        self.spot_df["timestamp"] = pd.to_datetime(self.spot_df["timestamp"], errors="coerce", utc=True)

        self.price_df.dropna(subset=["timestamp", "ccy_pair"], inplace=True)
        self.spot_df.dropna(subset=["timestamp", "ccy_pair"], inplace=True)

        self.price_df.sort_values(["ccy_pair", "timestamp"], inplace=True, kind="mergesort")
        self.spot_df.sort_values(["ccy_pair", "timestamp"], inplace=True, kind="mergesort")

    # Step 3: Merge with recent spot rates
    def find_recent_spot_rate(self):
        """Attach most recent spot_mid_rate (within 1h) to each price."""
        self._prepare_data()
        tolerance = pd.Timedelta("1h")

        try:
            start = time.time()
            merged = pd.merge_asof(
                self.price_df,
                self.spot_df,
                on="timestamp",
                by="ccy_pair",
                direction="backward",
                tolerance=tolerance,
                suffixes=("", "_spot"),
            )
            self._log(f"merge_asof completed in {(time.time() - start)*1000:.0f} ms")
            return merged
        except ValueError as e:
            if "keys must be sorted" not in str(e):
                raise
            self._log("merge_asof failed (keys must be sorted) – retrying per pair...", level="WARN")
            return self._merge_per_pair(tolerance)

    def _merge_per_pair(self, tolerance: pd.Timedelta) -> pd.DataFrame:
        """Fallback: per-currency-pair merge for robustness."""
        start = time.time()
        merged_groups = []

        for pair, grp_price in self.price_df.groupby("ccy_pair", sort=False):
            grp_spot = self.spot_df[self.spot_df["ccy_pair"] == pair]
            if grp_spot.empty:
                grp_price = grp_price.copy()
                grp_price["spot_mid_rate"] = np.nan
                merged_groups.append(grp_price)
            else:
                merged_groups.append(
                    pd.merge_asof(
                        grp_price.sort_values("timestamp"),
                        grp_spot.sort_values("timestamp"),
                        on="timestamp",
                        direction="backward",
                        tolerance=tolerance,
                        suffixes=("", "_spot"),
                    )
                )

        merged = pd.concat(merged_groups, ignore_index=True)
        self._log(f"Fallback merge completed in {(time.time()-start)*1000:.0f} ms")
        return merged

    # Step 4: Apply conversion logic
    def apply_conversion(self, merged_df: pd.DataFrame):
        """Apply conversion rules using ccy_df reference."""
        try:
            if "ccy_pair" not in self.ccy_df.columns:
                raise RuntimeError("Missing 'ccy_pair' in currency data")

            merged_df = merged_df.merge(self.ccy_df, on="ccy_pair", how="left")

            def compute(row):
                if pd.isna(row.get("ccy_pair")):
                    return np.nan
                if not bool(row.get("requires_conversion", False)):
                    return row.get("price")
                if pd.isna(row.get("spot_mid_rate")):
                    return np.nan
                conv_factor = row.get("conversion_factor")
                if pd.isna(conv_factor) or conv_factor == 0:
                    return np.nan
                return (row.get("price") / conv_factor) + row.get("spot_mid_rate")

            merged_df["new_price"] = merged_df.apply(compute, axis=1)
            merged_df["conversion_status"] = np.where(
                merged_df["new_price"].isna(), "insufficient_data", "ok"
            )
            self._log("Conversion logic applied successfully.")
            return merged_df
        except Exception as e:
            raise RuntimeError(f"Failed to apply conversion: {e}")

    # Step 5: Save results
    def save_results(self, df: pd.DataFrame):
        """Save results to CSV in results_dir."""
        try:
            os.makedirs(self.results_dir, exist_ok=True)
            output_path = self.results_dir / "final_rates.csv"
            df.to_csv(output_path, index=False)
            self._log(f"Results saved to {output_path}")
        except Exception as e:
            raise RuntimeError(f"Failed to save results: {e}")

    # Run processing pipeline
    def run(self):
        self.load_data()
        merged = self.find_recent_spot_rate()
        result = self.apply_conversion(merged)
        self.save_results(result)
        self._log("Processing complete.")
