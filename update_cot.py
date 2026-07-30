import pandas as pd
import json
import subprocess
import sys
from datetime import datetime, timedelta

# Auto-install official Nasdaq package to bypass the firewall
try:
    import nasdaqdatalink
except ImportError:
    print("Installing official Nasdaq Data Link library...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "nasdaq-data-link"])
    import nasdaqdatalink

# 1. IMPORTANT: Paste your real Nasdaq Data Link API key inside the quotes below
API_KEY = 'yGgfHiAWbn4QmWXduWCP'

def fetch_and_update_data():
    try:
        print("Connecting to Nasdaq Data Link via Official SDK...")
        
        # Authenticate with the official SDK to bypass Incapsula WAF
        nasdaqdatalink.ApiConfig.api_key = API_KEY
        
        # Fetch data directly into a pandas dataframe automatically!
        df = nasdaqdatalink.get("CFTC/088691_F_L_ALL")
        
        # The API returns Date as the index. Move it to a standard column.
        df = df.reset_index()
        
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
