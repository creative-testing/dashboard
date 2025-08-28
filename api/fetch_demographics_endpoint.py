#!/usr/bin/env python3
"""
API endpoint pour fetcher les démographies à la demande
Utilisation: python api/fetch_demographics_endpoint.py --account_id act_XXX --period 7
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
import sys

load_dotenv()

app = Flask(__name__)
CORS(app)  # Pour permettre les requêtes depuis le dashboard

def fetch_demographics(account_id, since_date, until_date):
    """Fetch demographics data for a specific account"""
    
    token = os.getenv("FACEBOOK_ACCESS_TOKEN")
    if not token:
        return {"error": "No token configured"}, 500
    
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
            return {"error": f"Facebook API error: {response.status_code}"}, 500
            
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
        
        return segments, 200
        
    except Exception as e:
        return {"error": str(e)}, 500

@app.route('/api/demographics', methods=['GET'])
def get_demographics():
    """
    Endpoint pour récupérer les démographies
    Params:
    - account_id: act_XXXXX
    - period: 3, 7, 14, 30, ou 90 (jours)
    """
    account_id = request.args.get('account_id')
    period = int(request.args.get('period', 7))
    
    if not account_id:
        return jsonify({"error": "account_id required"}), 400
    
    # Calculate date range
    until_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    since_date = (datetime.now() - timedelta(days=period)).strftime('%Y-%m-%d')
    
    segments, status = fetch_demographics(account_id, since_date, until_date)
    
    if status != 200:
        return jsonify(segments), status
    
    # Prepare response
    response = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "account_id": account_id,
            "period_days": period,
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
    
    return jsonify(response)

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

if __name__ == '__main__':
    port = int(os.getenv('DEMOGRAPHICS_API_PORT', 5000))
    print(f"🚀 Starting demographics API on port {port}")
    print(f"📍 Endpoint: http://localhost:{port}/api/demographics")
    print(f"📍 Health: http://localhost:{port}/api/health")
    app.run(host='0.0.0.0', port=port, debug=False)