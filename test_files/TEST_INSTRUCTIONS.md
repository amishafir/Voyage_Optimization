# Testing Instructions

## Step 1: Install Dependencies

First, install the required Python packages:

```bash
pip3 install -r requirements_marine.txt --user
```

Or if you prefer a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements_marine.txt
```

## Step 2: Run Local Test

Run the test script with 1-minute intervals (3 runs total):

```bash
python3 test_forecasting.py
```

This will:
- Run 3 times with 1-minute intervals
- Create `test_wave_forecast.xlsx` in the same directory
- Take approximately 2-3 minutes to complete

## Step 3: Verify Output

After the test completes, check the Excel file:

```bash
# Open the file or check its structure
python3 -c "import pandas as pd; xls = pd.ExcelFile('test_wave_forecast.xlsx'); print('Sheets:', xls.sheet_names); df1 = pd.read_excel('test_wave_forecast.xlsx', sheet_name='daily_forecast', nrows=5); df2 = pd.read_excel('test_wave_forecast.xlsx', sheet_name='hourly_forecast'); print('\n=== DAILY_FORECAST (first 5 rows) ==='); print(df1.to_string()); print('\n=== HOURLY_FORECAST ==='); print(df2.to_string())"
```

Verify:
- ✅ Two sheets: `daily_forecast` and `hourly_forecast`
- ✅ `daily_forecast` has metadata rows (latitude, longitude, etc.)
- ✅ `daily_forecast` has data rows with `sample_time` column
- ✅ `hourly_forecast` has 3 rows (one per run)
- ✅ Data structure matches `output_example.xlsx`

## Step 4: Deploy to Server

Once local test is successful, deploy to the remote server using the scripts in `remote_server_scripts/` folder.
