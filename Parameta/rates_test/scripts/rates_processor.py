import os
import time 
import pandas as pd
import numpy as np

class RatesProcessor:
    """Processes datasets and generates converted prices."""

    def __init__(self, data_dir, results_dir, verbose=False):
        self.data_dir = data_dir
        self.results_dir = results_dir
        self.verbose = verbose

    def _log(self, msg):
        if self.verbose:
            print(f"[INFO] {msg}")

    def load_data(self):
        self._log("Loading data...")
        self.ccy_df = pd.read_csv(os.path.join(self.data_dir, "rates_ccy_data.csv"))
        self.price_df = pd.read_parquet(os.path.join(self.data_dir, "rates_price_data.parq.gzip"))
        self.spot_df = pd.read_parquet(os.path.join(self.data_dir, "rates_spot_rate_data.parq.gzip"))

        for df in [self.ccy_df, self.price_df, self.spot_df]:
            df.columns = df.columns.str.strip().str.lower()

        self.price_df["timestamp"] = pd.to_datetime(self.price_df["timestamp"], utc=True)
        self.spot_df["timestamp"] = pd.to_datetime(self.spot_df["timestamp"], utc=True)

        self._log(f"Loaded {len(self.price_df)} prices and {len(self.spot_df)} spot rates.")

    def find_recent_spot_rate(self):
        tolerance = pd.Timedelta("1h")
        df = self.price_df.sort_values(["ccy_pair", "timestamp"]).copy()
        df["spot_mid_rate"] = np.nan
        df["conversion_status"] = "unknown"

        spot_lookup = (
            self.spot_df
            .sort_values(["ccy_pair", "timestamp"])
            .groupby("ccy_pair", group_keys=False)
            .apply(lambda g: g.set_index("timestamp")["spot_mid_rate"], include_groups=False)
            .to_dict()
        )
        median_spots = self.spot_df.groupby("ccy_pair")["spot_mid_rate"].median().to_dict()

        for idx, row in df.iterrows():
            ccy = row["ccy_pair"]
            ts = row["timestamp"]

            if ccy not in spot_lookup:
                df.at[idx, "spot_mid_rate"] = median_spots.get(ccy, np.nan)
                df.at[idx, "conversion_status"] = (
                    "estimated_spot_rate" if not pd.isna(df.at[idx, "spot_mid_rate"]) else "missing_data"
                )
                continue

            g = spot_lookup[ccy]
            idx_pos = g.index.searchsorted(ts, side="right") - 1

            if idx_pos >= 0 and ts - g.index[idx_pos] <= tolerance:
                df.at[idx, "spot_mid_rate"] = g.iloc[idx_pos]
                df.at[idx, "conversion_status"] = "converted"
            else:
                older = g.index < ts
                if older.any():
                    df.at[idx, "spot_mid_rate"] = g[older].iloc[-1]
                    df.at[idx, "conversion_status"] = "estimated_spot_rate"
                else:
                    df.at[idx, "spot_mid_rate"] = median_spots.get(ccy, np.nan)
                    df.at[idx, "conversion_status"] = (
                        "estimated_spot_rate" if not pd.isna(df.at[idx, "spot_mid_rate"]) else "missing_data"
                    )

        self.price_df = df
        return df

    def apply_conversion(self, df):
        """
        Compute new prices based on conversion rules.

        Conversion Status Legend:
        - not_converted: Conversion not required; new_price = price.
        - converted: Conversion applied using spot_mid_rate and conversion_factor.
        - estimated_spot_rate: Spot rate was missing; used most recent or median value.
        - missing_spot_rate: Spot rate missing and cannot estimate; new_price = NaN.
        - missing_conversion_factor: Conversion factor missing; new_price = NaN.
        - estimated_conversion_factor: Conversion factor estimated from median of ccy_pair group and used successfully.
        - insufficient_data: Neither spot nor conversion factor available; new_price = NaN.
        - ok: Successful conversion with both spot and conversion factor.
        """
        merged = df.merge(self.ccy_df, on="ccy_pair", how="left")
        merged["convert_price"] = merged["convert_price"].astype(str).str.lower().map({"true": True, "false": False})

        # Precompute median conversion factors per ccy_pair
        median_conv = self.ccy_df.groupby("ccy_pair")["conversion_factor"].median().to_dict()

        new_prices = []
        new_status = []

        for _, row in merged.iterrows():
            price = row["price"]
            convert = row["convert_price"]
            spot = row["spot_mid_rate"]
            conv_factor = row["conversion_factor"]

            if not convert:
                new_prices.append(price)
                new_status.append("not_converted")
                continue

            # Try to use conversion_factor
            used_median = False
            if pd.isna(conv_factor):
                conv_factor = median_conv.get(row["ccy_pair"], np.nan)
                if not pd.isna(conv_factor):
                    used_median = True

            # Determine if we have sufficient data
            if pd.isna(conv_factor) or pd.isna(spot):
                new_prices.append(np.nan)
                new_status.append("insufficient_data")
                continue

            # Compute new_price
            new_prices.append((price / conv_factor) + spot)

            # Determine conversion status
            if row["conversion_status"] == "estimated_spot_rate":
                new_status.append("estimated_spot_rate")
            elif used_median:
                new_status.append("estimated_conversion_factor")
            else:
                new_status.append("converted")

        merged["new_price"] = new_prices
        merged["conversion_status"] = new_status

        return merged


    def save_results(self, df):
        os.makedirs(self.results_dir, exist_ok=True)
        df["new_price"] = df["new_price"].round(4)
        out = os.path.join(self.results_dir, "final_rates.csv")
        df.to_csv(out, index=False)
        self._log("Conversion status counts:")
        self._log(df["conversion_status"].value_counts())

    def run(self):
        start = time.time()
        self.load_data()
        df_with_spot = self.find_recent_spot_rate()
        final_df = self.apply_conversion(df_with_spot)
        self.save_results(final_df)
        self._log(f"Total pipeline execution time: {time.time() - start:.3f} sec")
