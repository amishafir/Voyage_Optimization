#!/usr/bin/env python3
"""
Test script for Current and Wave Height Forecasting
Runs with 1-minute intervals for 3 runs (quick test)
"""

import sys
import os

# Import the main script
import current_wave_forecasting as main_script

# Override configuration for testing
main_script.INTERVAL_MINUTES = 1  # 1 minute instead of 15
main_script.TOTAL_RUNS = 3  # 3 runs instead of 12
main_script.OUTPUT_FILENAME = "test_wave_forecast.xlsx"  # Different filename for testing
main_script.OUTPUT_PATH = main_script.SCRIPT_DIR / main_script.OUTPUT_FILENAME

if __name__ == "__main__":
    print("=" * 70)
    print("TEST MODE: Quick test with 1-minute intervals (3 runs)")
    print("=" * 70)
    print(f"Output file: {main_script.OUTPUT_PATH}")
    print("=" * 70)
    print()
    
    # Run the main function
    try:
        main_script.main()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        print(f"Test output saved to: {main_script.OUTPUT_PATH}")
        sys.exit(0)
    except Exception as e:
        print(f"\n\nTest failed: {e}")
        sys.exit(1)
