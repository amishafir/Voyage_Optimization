#!/bin/bash
# Run local test and verify output
# Usage: ./run_local_test.sh

set -e  # Exit on error

echo "=========================================="
echo "Local Test: Current and Wave Height Forecasting"
echo "=========================================="
echo ""

# Step 1: Check/Install dependencies
echo "Step 1: Checking dependencies..."
if python3 -c "import openmeteo_requests, pandas, requests_cache, retry_requests, openpyxl" 2>/dev/null; then
    echo "✓ All dependencies are installed"
else
    echo "Installing dependencies..."
    pip3 install --break-system-packages -r requirements_marine.txt || {
        echo "Trying with --user flag..."
        pip3 install --user -r requirements_marine.txt || {
            echo "Creating virtual environment..."
            python3 -m venv venv_test
            source venv_test/bin/activate
            pip install -r requirements_marine.txt
            PYTHON_CMD="venv_test/bin/python3"
        }
    }
    echo "✓ Dependencies installed"
fi
echo ""

# Step 2: Run test
echo "Step 2: Running test script (1-minute intervals, 3 runs)..."
echo "This will take approximately 2-3 minutes..."
echo ""

# Use venv Python if it exists, otherwise use system Python
if [ -f "venv_test/bin/python3" ]; then
    PYTHON_CMD="venv_test/bin/python3"
else
    PYTHON_CMD="python3"
fi

$PYTHON_CMD test_forecasting.py
echo ""

# Step 3: Verify output
echo "Step 3: Verifying output file..."
if [ ! -f "test_wave_forecast.xlsx" ]; then
    echo "❌ Error: test_wave_forecast.xlsx not found"
    exit 1
fi

echo "✓ Output file created: test_wave_forecast.xlsx"
echo ""

# Step 4: Check Excel structure
echo "Step 4: Checking Excel file structure..."
$PYTHON_CMD << 'VERIFY_SCRIPT'
import pandas as pd
import sys

try:
    excel_file = "test_wave_forecast.xlsx"
    xls = pd.ExcelFile(excel_file)
    
    print(f"✓ Sheets found: {xls.sheet_names}")
    
    # Check daily_forecast sheet
    if 'daily_forecast' not in xls.sheet_names:
        print("❌ Error: 'daily_forecast' sheet not found")
        sys.exit(1)
    
    # Check hourly_forecast sheet
    if 'hourly_forecast' not in xls.sheet_names:
        print("❌ Error: 'hourly_forecast' sheet not found")
        sys.exit(1)
    
    # Read daily_forecast
    df_daily = pd.read_excel(excel_file, sheet_name='daily_forecast', skiprows=3)
    print(f"✓ daily_forecast: {len(df_daily)} data rows")
    
    # Check required columns
    required_cols = ['time', 'ocean_current_velocity (km/h)', 'ocean_current_direction (°)', 'wave_height (m)', 'sample_time']
    missing_cols = [col for col in required_cols if col not in df_daily.columns]
    if missing_cols:
        print(f"❌ Error: Missing columns in daily_forecast: {missing_cols}")
        sys.exit(1)
    print("✓ daily_forecast has all required columns")
    
    # Read hourly_forecast
    df_hourly = pd.read_excel(excel_file, sheet_name='hourly_forecast')
    print(f"✓ hourly_forecast: {len(df_hourly)} rows")
    
    # Check required columns
    required_cols_hourly = ['sample time', 'wave_height (m)', 'ocean_current_velocity (km/h)', 'ocean_current_direction (°)']
    missing_cols_hourly = [col for col in required_cols_hourly if col not in df_hourly.columns]
    if missing_cols_hourly:
        print(f"❌ Error: Missing columns in hourly_forecast: {missing_cols_hourly}")
        sys.exit(1)
    print("✓ hourly_forecast has all required columns")
    
    # Check sample_time consistency
    if len(df_hourly) > 0:
        unique_sample_times = df_hourly['sample time'].nunique()
        print(f"✓ Found {unique_sample_times} unique sample times in hourly_forecast")
        print(f"  Expected: 3 (one per run)")
    
    print("")
    print("==========================================")
    print("✓ VERIFICATION SUCCESSFUL!")
    print("==========================================")
    print("")
    print("Sample data preview:")
    print("\n=== DAILY_FORECAST (first 3 rows) ===")
    print(df_daily.head(3).to_string())
    print("\n=== HOURLY_FORECAST ===")
    print(df_hourly.to_string())
    
except Exception as e:
    print(f"❌ Verification failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
VERIFY_SCRIPT

echo ""
echo "=========================================="
echo "Test completed successfully!"
echo "Output file: test_wave_forecast.xlsx"
echo "=========================================="
