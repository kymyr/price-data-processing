import argparse
import os
import sys
from stdev_processor import StdevProcessor

def main():
    parser = argparse.ArgumentParser(description="Compute 20-hour rolling stdev per security.")
    current_path = os.path.dirname(__file__)
    default_data = os.path.join(current_path, "..", "data", "stdev_price_data.parq.gzip")
    default_results = os.path.join(current_path, "..", "results")

    parser.add_argument("--data-path", type=str, default=default_data, help="Path to stdev_price_data.parq.gzip")
    parser.add_argument("--results-dir", type=str, default=default_results, help="Directory for output CSV")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    processor = StdevProcessor(data_path=args.data_path, results_dir=args.results_dir, verbose=args.verbose)

    try:
        processor.run()
    except Exception:
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
