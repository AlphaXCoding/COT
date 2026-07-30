import pandas as pd
import requests
import json
from datetime import datetime, timedelta

# 1. IMPORTANT: Paste your real Nasdaq Data Link API key inside the quotes below
API_KEY = 'yGgfHiAWbn4QmWXduWCP'

# 2. FIXED URL: Added the missing _L_ for the Legacy Gold Dataset
URL = f"https://data.nasdaq.com/api/v3/datasets/CFTC/088691_F_L_ALL.json?api_key={API_KEY}"

def fetch_and_update_data():
    try:
        print("Connecting to Nasdaq Data Link...")
        response = requests.get(URL)
        
        # This will print the exact error in your GitHub logs if it fails again
        if response.status_code != 200:
            print(f"API Error {response.status_code}: {response.text}")
            exit(1)
            
        data = response.json()
        
        dataset = data['dataset']
        columns = dataset['column_names']
        rows = dataset['data']
        
        df = pd.DataFrame(rows, columns=columns)
        df['Date'] = pd.to_datetime(df['Date'])
        
        # Filter for the last 2 years
        two_years_ago = datetime.now() - timedelta(days=730)
        df = df[df['Date'] >= two_years_ago]
        
        # Sort by date ascending for the chart
        df = df.sort_values(by='Date', ascending=True)
        
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
        print("Premium COT data updated successfully!")
        
    except Exception as e:
        print(f"Error fetching data: {e}")
        exit(1)

if __name__ == "__main__":
    fetch_and_update_data()
