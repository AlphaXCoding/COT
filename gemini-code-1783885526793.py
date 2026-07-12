import pandas as pd
import requests
import json
from datetime import datetime, timedelta

# You can get a free API key from Nasdaq Data Link (Quandl)
API_KEY = 'YOUR_QUANDL_API_KEY'
# CFTC Gold (Commodity Exchange Inc) - Futures Only
# Code: CFTC/088691_F_L_ALL (Legacy) or choose Disaggregated
URL = f"https://data.nasdaq.com/api/v3/datasets/CFTC/088691_F_ALL.json?api_key={API_KEY}"

def fetch_and_update_data():
    response = requests.get(URL)
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
    
    # Calculate Net Non-Commercial Positions (Long - Short)
    # Note: Column names depend on the exact dataset, standardizing here:
    df['Net_NonComm'] = df['Noncommercial Long'] - df['Noncommercial Short']
    
    # Format for the frontend
    export_data = {
        "dates": df['Date'].dt.strftime('%Y-%m-%d').tolist(),
        "net_positions": df['Net_NonComm'].tolist(),
        "longs": df['Noncommercial Long'].tolist(),
        "shorts": df['Noncommercial Short'].tolist(),
        "last_updated": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    with open('cot_data.json', 'w') as f:
        json.dump(export_data, f)
    print("COT data updated successfully!")

if __name__ == "__main__":
    fetch_and_update_data()