import pandas as pd
import requests
from io import BytesIO
from zipfile import ZipFile
import json
from datetime import datetime

def get_cftc_data(year):
    print(f"Downloading official US Government CFTC data for {year}...")
    url = f"https://www.cftc.gov/files/dea/history/deacot{year}.zip"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return pd.DataFrame()
        
    zip_file = ZipFile(BytesIO(response.content))
    for filename in zip_file.namelist():
        if filename.endswith('.txt') or filename.endswith('.csv'):
            return pd.read_csv(zip_file.open(filename), low_memory=False)
            
    return pd.DataFrame()

def fetch_and_update_data():
    try:
        year = datetime.now().year
        df = get_cftc_data(year)
        
        if df.empty:
            df = get_cftc_data(year - 1)

        if df.empty:
            print("Error: Could not retrieve COT data zip archive.")
            exit(1)

        # Standardize columns to lowercase
        df.columns = [col.lower().strip().replace(' ', '_') for col in df.columns]
        
        market_col = next((col for col in df.columns if 'market' in col or 'exchange' in col), df.columns[0])
        
        # DYNAMIC DATE FIX: Explicitly target the formatted date column, not the raw YYMMDD integer column
        date_col = next((col for col in df.columns if 'yyyy_mm_dd' in col or 'mm_dd_yyyy' in col), None)
        if not date_col:
            date_col = next((col for col in df.columns if 'date' in col), df.columns[1])
        
        # Filter strictly for Gold COMEX Futures and COPY to avoid SettingWithCopyWarning
        gold_df = df[df[market_col].astype(str).str.contains('GOLD', case=False, na=False)].copy()
        strict_df = gold_df[gold_df[market_col].astype(str).str.contains('COMMODITY EXCHANGE INC', case=False, na=False)].copy()
        
        if not strict_df.empty:
            df = strict_df.copy()
        else:
            # Fallback filter if specific exchange name string differs slightly
            df = gold_df.copy()

        if df.empty:
            print("Error: Gold market rows could not be isolated.")
            exit(1)

        print(f"Detected Market Column: {market_col}")
        print(f"Detected Date Column: {date_col}")

        # Parse dates robustly
        df['Date'] = pd.to_datetime(df[date_col], errors='coerce')
        df = df.dropna(subset=['Date'])
        
        # Keep valid recent calendar dates
        df = df[(df['Date'] >= '2025-01-01') & (df['Date'] <= datetime.now())]
        
        if df.empty:
            print("Error: DataFrame is empty after filtering dates. Check CFTC date formats.")
            exit(1)

        # Use exact Futures-only Non-Commercial columns matching the official CFTC layout
        long_col = next((col for col in df.columns if 'noncomm_positions_long' in col), None)
        short_col = next((col for col in df.columns if 'noncomm_positions_short' in col), None)
        
        if not long_col or not short_col:
            raise Exception(f"Could not locate Non-Commercial columns. Available columns: {list(df.columns)}")

        df['Noncommercial Long'] = pd.to_numeric(df[long_col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df['Noncommercial Short'] = pd.to_numeric(df[short_col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        
        # Group duplicates on the same date and sort chronologically
        df = df.groupby('Date').agg({
            'Noncommercial Long': 'sum',
            'Noncommercial Short': 'sum'
        }).reset_index()
        
        df = df.sort_values(by='Date', ascending=True).tail(22)
        
        # Calculations
        df['Net_NonComm'] = df['Noncommercial Long'] - df['Noncommercial Short']
        df['Total_Positions'] = df['Noncommercial Long'] + df['Noncommercial Short']
        df['Long_Pct'] = (df['Noncommercial Long'] / df['Total_Positions'] * 100).fillna(0).round(1)
        df['Short_Pct'] = (df['Noncommercial Short'] / df['Total_Positions'] * 100).fillna(0).round(1)
        
        export_data = {
            "dates": df['Date'].dt.strftime('%Y-%m-%d').tolist(),
            "net_positions": df['Net_NonComm'].tolist(),
            "longs": df['Noncommercial Long'].tolist(),
            "shorts": df['Noncommercial Short'].tolist(),
            "long_pct": df['Long_Pct'].tolist(),
            "short_pct": df['Short_Pct'].tolist(),
            "last_updated": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        with open('cot_data.json', 'w') as f:
            json.dump(export_data, f)
            
        print("Cleaned 5-Month Gold COT data successfully exported!")
        
    except Exception as e:
        print(f"Error processing script: {e}")
        exit(1)

if __name__ == "__main__":
    fetch_and_update_data()
