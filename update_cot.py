import pandas as pd
import requests
from io import BytesIO
from zipfile import ZipFile
import json
from datetime import datetime, timedelta

def get_cftc_data(year):
    print(f"Downloading official US Government CFTC data for {year}...")
    url = f"https://www.cftc.gov/files/dea/history/deacot{year}.zip"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
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
        current_year = datetime.now().year
        prev_year = current_year - 1
        
        df = pd.concat([get_cftc_data(current_year), get_cftc_data(prev_year)], ignore_index=True)
        
        # Standardize columns
        df.columns = [col.lower().strip().replace(' ', '_').replace('-', '_') for col in df.columns]
        
        market_col = next((col for col in df.columns if 'market_and_exchange' in col), df.columns[0])
        date_col = next((col for col in df.columns if 'report_date' in col or 'as_of_date' in col or 'date' in col), None)

        # Filter specifically for Gold
        df = df[df[market_col].astype(str).str.contains('GOLD', case=False, na=False)]
        
        # Parse dates robustly
        df['Date'] = pd.to_datetime(df[date_col], errors='coerce')
        df = df.dropna(subset=['Date'])
        
        long_col = next(col for col in df.columns if ('noncomm' in col or 'noncommercial' in col) and 'long' in col)
        short_col = next(col for col in df.columns if ('noncomm' in col or 'noncommercial' in col) and 'short' in col)
        
        df['Noncommercial Long'] = pd.to_numeric(df[long_col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df['Noncommercial Short'] = pd.to_numeric(df[short_col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        
        # Group duplicates on the same date
        df = df.groupby('Date').agg({
            'Noncommercial Long': 'sum',
            'Noncommercial Short': 'sum'
        }).reset_index()
        
        # Sort chronologically
        df = df.sort_values(by='Date', ascending=True)
        
        # Take the last 22 weeks (~5 months) cleanly without throwing empty dataframe errors
        df = df.tail(22)
        
        if df.empty:
            print("Error: DataFrame is empty.")
            exit(1)
        
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
        print("Cleaned 5-month COT data successfully exported!")
        
    except Exception as e:
        print(f"Error processing data: {e}")
        exit(1)

if __name__ == "__main__":
    fetch_and_update_data()
