import pandas as pd
import requests
from io import BytesIO
from zipfile import ZipFile
import json
from datetime import datetime

def fetch_and_update_data():
    try:
        year = datetime.now().year
        url = f"https://www.cftc.gov/files/dea/history/deacot{year}.zip"
        
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            print(f"Failed to download data. Status: {response.status_code}")
            exit(1)
            
        zip_file = ZipFile(BytesIO(response.content))
        df = pd.DataFrame()
        
        for filename in zip_file.namelist():
            if filename.endswith('.txt') or filename.endswith('.csv'):
                df = pd.read_csv(zip_file.open(filename), low_memory=False)
                break
                
        if df.empty:
            print("Error: Empty archive.")
            exit(1)

        # Standardize columns
        df.columns = [col.lower().strip().replace(' ', '_') for col in df.columns]
        
        market_col = next((col for col in df.columns if 'market_and_exchange_names' in col or 'market' in col), df.columns[0])
        date_col = next((col for col in df.columns if 'report_date_as_yyyy_mm_dd' in col or 'date' in col), df.columns[1])
        
        # Filter for Gold (COMEX)
        df = df[df[market_col].astype(str).str.contains('GOLD', case=False, na=False)]
        df = df[df[market_col].astype(str).str.contains('COMEX', case=False, na=False)]
        
        if df.empty:
            print("Error: Could not isolate Gold COMEX contract.")
            exit(1)

        # Parse dates accurately
        df['Date'] = pd.to_datetime(df[date_col], errors='coerce')
        df = df.dropna(subset=['Date'])
        
        # Correct CFTC legacy non-commercial columns
        long_col = next((col for col in df.columns if 'noncomm_positions_long' in col), None)
        short_col = next((col for col in df.columns if 'noncomm_positions_short' in col), None)
        
        if not long_col or not short_col:
            raise Exception("Could not locate Non-Commercial long/short columns.")

        df['Noncommercial Long'] = pd.to_numeric(df[long_col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df['Noncommercial Short'] = pd.to_numeric(df[short_col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        
        # Group and sort
        df = df.groupby('Date').agg({
            'Noncommercial Long': 'sum',
            'Noncommercial Short': 'sum'
        }).reset_index()
        
        df = df.sort_values(by='Date', ascending=True).tail(22)
        
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
            
        print("Accurate Gold COT data successfully exported!")
        
    except Exception as e:
        print(f"Error: {e}")
        exit(1)

if __name__ == "__main__":
    fetch_and_update_data()
