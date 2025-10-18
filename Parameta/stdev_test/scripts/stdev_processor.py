import os
import time
import pandas as pd
import numpy as np
from pathlib import Path


class StdevProcessor:
    """
    Compute rolling 20-hour standard deviation of bid/mid/ask per security_id.
    Works over the timespan present in the input dataset (no start/end args required).
    """

    def __init__(self, data_path, results_dir, verbose: bool = False):
        self.data_path = Path(data_path).resolve()
        self.results_dir = Path(results_dir).resolve()
        self.verbose = bool(verbose)

    def _log(self, msg: str):
        if self.verbose:
            print(f"[INFO] {msg}")

    def load_data(self):
        self._log(f"Loading data from {self.data_path} ...")
        if not self.data_path.exists():
            raise FileNotFoundError(f"{self.data_path} not found")

        self.df = pd.read_parquet(self.data_path)
        required = {"snap_time", "security_id", "bid", "mid", "ask"}
        missing = required - set(self.df.columns)
        if missing:
            raise RuntimeError(f"Missing required columns in input: {missing}")

        self.df["snap_time"] = pd.to_datetime(self.df["snap_time"])
        # keep minimal columns & sort
        self.df = (
            self.df[["security_id", "snap_time", "bid", "mid", "ask"]]
            .sort_values(["security_id", "snap_time"])
            .reset_index(drop=True)
        )
        self._log(f"Loaded {len(self.df)} rows for {self.df['security_id'].nunique()} security_ids")
        self._log(f"Dataset span: {self.df['snap_time'].min()} -> {self.df['snap_time'].max()}")

        return self.df

    def compute_rolling_stdev(self, df, window_hours=20):
        """
        Compute rolling standard deviation per security_id over a full hourly range.
        Even missing snaps must have a value (computed using the most recent
        20 valid values before that time).

        Returns a DataFrame with snap_time, security_id, bid_stdev, mid_stdev, ask_stdev.
        """
        results = []
        tic = time.time()
        security_ids = df["security_id"].unique()
        self._log(f"Processing {len(security_ids)} security_ids")

        for sid in security_ids:
            grp = df[df["security_id"] == sid].set_index("snap_time").sort_index()

            # Create complete hourly timeline
            sec_min = grp.index.min()
            sec_max = grp.index.max()
            hourly_index = pd.date_range(start=sec_min, end=sec_max, freq="h", name="snap_time")

            grp_full = grp.reindex(hourly_index)[["bid", "mid", "ask"]]

            res = pd.DataFrame(index=hourly_index)
            for col in ["bid", "mid", "ask"]:
                values = grp_full[col].to_numpy()
                stdevs = np.full_like(values, np.nan, dtype=float)

                valid_idx = np.where(~np.isnan(values))[0]

                # For each hour, look back to find 20 valid values
                for i in range(len(values)):
                    # indices of valid prices <= i
                    valid_before = valid_idx[valid_idx <= i]
                    if len(valid_before) < window_hours:
                        continue
                    recent_20 = valid_before[-window_hours:]
                    stdevs[i] = np.std(values[recent_20], ddof=1)

                res[f"{col}_stdev"] = stdevs

            res["security_id"] = sid
            results.append(res.reset_index().rename(columns={"index": "snap_time"}))

        if results:
            df_out = pd.concat(results, ignore_index=True)
        else:
            df_out = pd.DataFrame(
                columns=["snap_time", "security_id", "bid_stdev", "mid_stdev", "ask_stdev"]
            )

        df_out = df_out.round({"bid_stdev": 3, "mid_stdev": 3, "ask_stdev": 3})

        self._log(f"Computed {len(df_out)} result rows in {(time.time() - tic)*1000:.0f} ms")
        return df_out

    def save_results(self, df_out, filename="stdev_results.csv"):
        self.results_dir.mkdir(parents=True, exist_ok=True)
        out_path = self.results_dir / filename
        df_out.to_csv(out_path, index=False)
        self._log(f"Saved results to {out_path}")
        return out_path

    # Run processing pipeline
    def run(self):
        try:
            df_in = self.load_data()
            df_out = self.compute_rolling_stdev(df_in, window_hours=20)
            out_path = self.save_results(df_out)
            print("Processing completed successfully!")
            if self.verbose:
                print(f"[INFO] Output rows: {len(df_out)}  file: {out_path}")
        except Exception as exc:
            print(f"[ERROR] Processing failed: {exc}")
            raise
