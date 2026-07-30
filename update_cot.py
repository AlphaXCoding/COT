import pandas as pd
import requests
from io import BytesIO
from zipfile import ZipFile
import json
from datetime import datetime, timedelta

# WE ARE DITCHING NASDAQ!
# No more API Keys. No more Firewalls.
# We will download the data directly from the official US Government CFTC servers.

def get_cftc_data(year):
    print(f"Downloading official US Government CFTC data for {year}...")
    url = f"https://www.cftc.gov/files/dea/history/deacot{year}.zip"
    
    # Use a browser header so the government site doesn't block the request
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        print(f"Failed to download {year} data. Status: {response.status_code}")
        return pd.DataFrame()
        
    zip_file = ZipFile(BytesIO(response.content))
    
    # Read the data directly from the zip file in memory
    for filename in zip_file.namelist():
        if filename.endswith('.txt') or filename.endswith('.csv'):
            return pd.read_csv(zip_file.open(filename), low_memory=False)
            
    return pd.DataFrame()

def fetch_and_update_data():
    try:
        current_year = datetime.now().year
        prev_year = current_year - 1
        
        # Fetch this year and last year directly from the CFTC
        df_current = get_cftc_data(current_year)
        df_prev = get_cftc_data(prev_year)
        
        # Combine them
        df = pd.concat([df_current, df_prev], ignore_index=True)
        
        if df.empty:
            print("Error: No data was downloaded.")
            exit(1)

        # FIX: Standardize columns to lowercase AND replace spaces with underscores
        df.columns = [col.lower().strip().replace(' ', '_') for col in df.columns]
        
        # DYNAMIC FINDER: Finds the correct columns even if the CFTC changes their names slightly
        market_col = next((col for col in df.columns if 'market_and_exchange' in col), df.columns[0])
        date_col = next(col for col in df.columns if 'report_date' in col or 'as_of_date' in col)
        
        # Filter specifically for Gold (XAUUSD) 
        df = df[df[market_col].str.contains('GOLD', case=False, na=False)]
        df = df[df[market_col].str.contains('COMMODITY EXCHANGE', case=False, na=False)]
        
        # Standardize the date column
        df['Date'] = pd.to_datetime(df[date_col])
        
        # Filter for exactly the last 2 years
        two_years_ago = datetime.now() - timedelta(days=730)
        df = df[df['Date'] >= two_years_ago]
        
        # Sort chronologically for the chart
        df = df.sort_values(by='Date', ascending=True)
        
        # DYNAMIC FINDER: Finds the Long and Short columns regardless of how the CFTC spells them
        long_col = next(col for col in df.columns if ('noncomm' in col or 'noncommercial' in col) and 'long' in col)
        short_col = next(col for col in df.columns if ('noncomm' in col or 'noncommercial' in col) and 'short' in col)
        
        # Ensure the positions are numbers (also cleans out any accidental commas from the government data)
        df['Noncommercial Long'] = pd.to_numeric(df[long_col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df['Noncommercial Short'] = pd.to_numeric(df[short_col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        
        # Advanced Calculations
        df['Net_NonComm'] = df['Noncommercial Long'] - df['Noncommercial Short']
        df['Total_Positions'] = df['Noncommercial Long'] + df['Noncommercial Short']
        
        # Sentiment Ratios (Prevent division by zero)
        df['Long_Pct'] = (df['Noncommercial Long'] / df['Total_Positions'] * 100).fillna(0).round(1)
        df['Short_Pct'] = (df['Noncommercial Short'] / df['Total_Positions'] * 100).fillna(0).round(1)
        
        # Format for the frontend
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
        print("US Government CFTC data downloaded and formatted successfully!")
        
    except Exception as e:
        print(f"Error processing data: {e}")
        exit(1)

if __name__ == "__main__":
    fetch_and_update_data()
