import argparse
import os
from pathlib import Path
from rates_processor import RatesProcessor


def main():
    parser = argparse.ArgumentParser(description="Run rates processing pipeline.")
    current_path = os.path.dirname(__file__)

    parser.add_argument(
        "--data-dir",
        type=str,
        default=os.path.join(current_path, "..", "data"),
        help="Path to the input data directory (default: ../data)",
    )
    parser.add_argument(
        "--results-dir",
        type=str,
        default=os.path.join(current_path, "..", "results"),
        help="Path to the output results directory (default: ../results)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose mode for detailed logs and debug output.",
    )

    args = parser.parse_args()

    try:
        processor = RatesProcessor(
            data_dir=args.data_dir,
            results_dir=args.results_dir
        )
        processor.verbose = args.verbose
        processor.run()
        print("Processing completed successfully!")
    except Exception as e:
        print(f"Processing failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
