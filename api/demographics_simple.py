#!/usr/bin/env python3
"""
Version simplifiée sans Flask - génère un fichier JSON
Usage: python api/demographics_simple.py act_XXX 7
"""
import sys
import os
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

def fetch_and_save_demographics(account_id, period_days):
    """Fetch demographics and save to JSON file"""
    
    token = os.getenv("FACEBOOK_ACCESS_TOKEN")
    if not token:
        print("❌ No token found")
        return False
    
    until_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    since_date = (datetime.now() - timedelta(days=period_days)).strftime('%Y-%m-%d')
    
    print(f"📊 Fetching demographics for {account_id}...")
    print(f"📅 Period: {since_date} to {until_date}")
    
    url = f"https://graph.facebook.com/v23.0/{account_id}/insights"
    
    params = {
        "access_token": token,
        "level": "account",
        "time_range": f'{{"since":"{since_date}","until":"{until_date}"}}',
        "fields": "impressions,spend,clicks,actions,action_values",
        "breakdowns": "age,gender",
        "filtering": json.dumps([{"field": "spend", "operator": "GREATER_THAN", "value": 10}]),
        "limit": 500
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ Error {response.status_code}")
            return False
            
        data = response.json()
        segments = []
        
        for row in data.get("data", []):
            age = row.get("age", "unknown")
            gender = row.get("gender", "unknown")
            
            spend = float(row.get("spend", 0))
            impressions = int(row.get("impressions", 0))
            clicks = int(row.get("clicks", 0))
            
            # Extract purchases
            purchases = 0
            purchase_value = 0
            
            for action in row.get("actions", []):
                if "purchase" in action.get("action_type", ""):
                    purchases = int(action.get("value", 0))
                    break
                    
            for action_value in row.get("action_values", []):
                if "purchase" in action_value.get("action_type", ""):
                    purchase_value = float(action_value.get("value", 0))
                    break
            
            # Calculate metrics
            roas = purchase_value / spend if spend > 0 else 0
            cpa = spend / purchases if purchases > 0 else 0
            ctr = (clicks / impressions * 100) if impressions > 0 else 0
            
            # Format gender for display
            gender_display = "Mujer" if gender == "female" else "Hombre" if gender == "male" else gender
            
            segments.append({
                "segment": f"{age}_{gender_display}",
                "age": age,
                "gender": gender_display,
                "spend": round(spend, 2),
                "impressions": impressions,
                "clicks": clicks,
                "purchases": purchases,
                "purchase_value": round(purchase_value, 2),
                "roas": round(roas, 2),
                "cpa": round(cpa, 2) if cpa < 999999 else 0,
                "ctr": round(ctr, 2)
            })
        
        # Sort by spend descending
        segments.sort(key=lambda x: x["spend"], reverse=True)
        
        # Prepare output
        output = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "account_id": account_id,
                "period_days": period_days,
                "date_range": f"{since_date} to {until_date}",
                "total_segments": len(segments)
            },
            "segments": segments,
            "summary": {
                "total_spend": sum(s["spend"] for s in segments),
                "total_purchases": sum(s["purchases"] for s in segments),
                "avg_roas": sum(s["roas"] for s in segments) / len(segments) if segments else 0
            }
        }
        
        # Save to file
        output_file = "data/temp/current_demographics.json"
        os.makedirs("data/temp", exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Saved {len(segments)} segments to {output_file}")
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python api/demographics_simple.py <account_id> <period_days>")
        sys.exit(1)
    
    account_id = sys.argv[1]
    period_days = int(sys.argv[2])
    
    success = fetch_and_save_demographics(account_id, period_days)
    sys.exit(0 if success else 1)