#!/usr/bin/env python3
"""
Fetch demographics data (age/gender breakdown) for a specific account
Pour éviter les timeouts, on fetch compte par compte
"""
import os
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
import sys

load_dotenv()

def fetch_demographics_for_account(account_id, account_name, since_date, until_date, token):
    """
    Récupère les données démographiques pour un compte spécifique
    Breakdown par age et gender
    """
    print(f"\n📊 Fetching demographics for {account_name}...")
    
    url = f"https://graph.facebook.com/v23.0/{account_id}/insights"
    
    params = {
        "access_token": token,
        "level": "account",  # Niveau compte pour avoir toutes les données agrégées
        "time_range": f'{{"since":"{since_date}","until":"{until_date}"}}',
        "fields": "impressions,spend,clicks,actions,action_values",
        "breakdowns": "age,gender",  # Le breakdown démographique
        "filtering": json.dumps([{"field": "impressions", "operator": "GREATER_THAN", "value": 0}]),
        "limit": 500
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ Error {response.status_code}: {response.text[:200]}")
            return None
            
        data = response.json()
        
        if "data" not in data:
            print(f"⚠️ No data in response")
            return None
            
        segments = []
        
        for row in data.get("data", []):
            # Extraire age et gender
            age = row.get("age", "unknown")
            gender = row.get("gender", "unknown")
            
            # Métriques
            spend = float(row.get("spend", 0))
            impressions = int(row.get("impressions", 0))
            clicks = int(row.get("clicks", 0))
            
            # Purchases (même logique que fetch_sans_demographie.py)
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
            
            # Calculer ROAS et CPA
            roas = purchase_value / spend if spend > 0 else 0
            cpa = spend / purchases if purchases > 0 else 0
            ctr = (clicks / impressions * 100) if impressions > 0 else 0
            
            segments.append({
                "age": age,
                "gender": gender,
                "segment": f"{age}_{gender}",
                "spend": spend,
                "impressions": impressions,
                "clicks": clicks,
                "purchases": purchases,
                "purchase_value": purchase_value,
                "roas": roas,
                "cpa": cpa,
                "ctr": ctr
            })
        
        # Trier par spend décroissant
        segments.sort(key=lambda x: x["spend"], reverse=True)
        
        print(f"✅ Found {len(segments)} demographic segments")
        
        # Afficher top 5
        print("\nTop 5 segments by spend:")
        for seg in segments[:5]:
            gender_label = "Mujer" if seg["gender"] == "female" else "Hombre" if seg["gender"] == "male" else seg["gender"]
            print(f"  {seg['age']:5} {gender_label:8} - ${seg['spend']:>8,.0f} - ROAS: {seg['roas']:.2f}")
        
        return segments
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return None

def main():
    """Test avec un compte spécifique"""
    
    token = os.getenv("FACEBOOK_ACCESS_TOKEN")
    if not token:
        print("❌ No token found")
        sys.exit(1)
    
    # Test avec Petcare 2 ou un autre compte
    test_account_id = "act_621212048277595"  # Petcare 2
    test_account_name = "Petcare 2"
    
    # Si un argument est passé, l'utiliser comme account_id
    if len(sys.argv) > 1:
        test_account_id = sys.argv[1]
        test_account_name = test_account_id
    
    # Derniers 7 jours
    until_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    since_date = (datetime.now() - timedelta(days=8)).strftime('%Y-%m-%d')
    
    print(f"📅 Period: {since_date} to {until_date}")
    print(f"🏢 Account: {test_account_name} ({test_account_id})")
    
    segments = fetch_demographics_for_account(
        test_account_id,
        test_account_name,
        since_date,
        until_date,
        token
    )
    
    if segments:
        # Sauvegarder pour test
        output = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "account_id": test_account_id,
                "account_name": test_account_name,
                "date_range": f"{since_date} to {until_date}",
                "total_segments": len(segments)
            },
            "segments": segments
        }
        
        os.makedirs("data/temp", exist_ok=True)
        output_file = f"data/temp/demographics_{test_account_id.replace('act_', '')}.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Saved to {output_file}")
        
        # Résumé
        total_spend = sum(s["spend"] for s in segments)
        print(f"\n📊 Summary:")
        print(f"  Total segments: {len(segments)}")
        print(f"  Total spend: ${total_spend:,.0f}")
        print(f"  Avg ROAS: {sum(s['roas'] for s in segments) / len(segments):.2f}")

if __name__ == "__main__":
    main()