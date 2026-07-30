import pandas as pd
import requests
from io import BytesIO
from zipfile import ZipFile
import json
from datetime import datetime

def fetch_and_update_data():
    try:
        # Use the exact URL format for CFTC legacy reports (e.g., 2026)
        year = datetime.now().year
        url = f"https://www.cftc.gov/files/dea/history/deacot{year}.zip"
        
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            print(f"Failed to download data for {year}. Status: {response.status_code}")
            exit(1)
            
        zip_file = ZipFile(BytesIO(response.content))
        df = pd.DataFrame()
        
        for filename in zip_file.namelist():
            if filename.endswith('.txt') or filename.endswith('.csv'):
                df = pd.read_csv(zip_file.open(filename), low_memory=False)
                break
                
        if df.empty:
            print("Error: No valid file found inside the zip archive.")
            exit(1)

        # Standardize column names to lowercase and strip whitespace
        df.columns = [col.lower().strip().replace(' ', '_') for col in df.columns]
        
        # Identify key columns safely based on CFTC legacy layout headers
        market_col = next((col for col in df.columns if 'market_and_exchange' in col), df.columns[0])
        date_col = next((col for col in df.columns if 'report_date' in col or 'as_of_date' in col), df.columns[1])
        
        # Filter strictly for Gold on COMEX (Commodity Exchange Inc.)
        df = df[df[market_col].astype(str).str.contains('GOLD', case=False, na=False)]
        df = df[df[market_col].astype(str).str.contains('COMMODITY', case=False, na=False)]
        
        if df.empty:
            print("Error: Gold market rows could not be isolated.")
            exit(1)

        # Clean dates properly
        df['Date'] = pd.to_datetime(df[date_col], errors='coerce')
        df = df.dropna(subset=['Date'])
        
        # Extract Non-Commercial (Speculator) columns from legacy format
        # In CFTC legacy reports: noncomm_positions_long_all & noncomm_positions_short_all
        long_col = next((col for col in df.columns if 'noncomm' in col and 'long' in col), None)
        short_col = next((col for col in df.columns if 'noncomm' in col and 'short' in col), None)
        
        if not long_col or not short_col:
            raise Exception("Could not find Non-Commercial position columns in the CFTC file.")

        df['Noncommercial Long'] = pd.to_numeric(df[long_col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df['Noncommercial Short'] = pd.to_numeric(df[short_col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        
        # Group by date to combine any duplicates
        df = df.groupby('Date').agg({
            'Noncommercial Long': 'sum',
            'Noncommercial Short': 'sum'
        }).reset_index()
        
        # Sort chronologically
        df = df.sort_values(by='Date', ascending=True)
        
        # Take the most recent 22 weeks (~5 months)
        df = df.tail(22)
        
        # Calculate metrics
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
            
        print("COT data successfully parsed and exported!")
        
    except Exception as e:
        print(f"Error processing script: {e}")
        exit(1)

if __name__ == "__main__":
    fetch_and_update_data()
