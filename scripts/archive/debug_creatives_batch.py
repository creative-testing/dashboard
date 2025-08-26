#!/usr/bin/env python3
"""
Debug du problème batch creatives
"""
import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

def debug_batch_creatives():
    """Debug du batch pour comprendre le problème"""
    
    token = os.getenv("FB_TOKEN")
    
    # Test avec juste 3 ad_ids connus
    test_ad_ids = ["6875039415940", "6873015543740", "6867984162740"]
    
    print("🔍 DEBUG BATCH CREATIVES")
    print("=" * 50)
    print(f"Test avec {len(test_ad_ids)} ad_ids")
    
    # Créer la requête batch
    batch_requests = []
    for ad_id in test_ad_ids:
        batch_requests.append({
            "method": "GET",
            "relative_url": f"{ad_id}?fields=creative{{video_id,image_url,instagram_permalink_url}}"
        })
    
    print(f"\n📋 Batch request:")
    print(json.dumps(batch_requests, indent=2))
    
    # Exécuter
    try:
        batch_url = "https://graph.facebook.com/v23.0/"
        batch_params = {
            "access_token": token,
            "batch": json.dumps(batch_requests)
        }
        
        print(f"\n📡 Envoi requête batch...")
        response = requests.post(batch_url, data=batch_params)
        
        print(f"Status: {response.status_code}")
        
        # Debug de la réponse
        raw_response = response.text
        print(f"\n📄 Raw response:")
        print(raw_response[:500] + "..." if len(raw_response) > 500 else raw_response)
        
        # Parser JSON
        try:
            batch_results = response.json()
            print(f"\n📊 Type de batch_results: {type(batch_results)}")
            print(f"Longueur: {len(batch_results) if hasattr(batch_results, '__len__') else 'N/A'}")
            
            if isinstance(batch_results, list):
                print(f"\n🔍 Analyse des éléments:")
                for i, result in enumerate(batch_results):
                    print(f"  Element {i}: type={type(result)}")
                    
                    if isinstance(result, dict):
                        print(f"    Keys: {list(result.keys())}")
                        print(f"    Code: {result.get('code', 'N/A')}")
                        
                        if result.get("code") == 200 and "body" in result:
                            try:
                                body = json.loads(result["body"])
                                print(f"    Body type: {type(body)}")
                                if isinstance(body, dict):
                                    print(f"    Body keys: {list(body.keys())}")
                            except:
                                print(f"    Body: {result['body'][:100]}...")
                    else:
                        print(f"    Content: {str(result)[:100]}...")
                        
            elif isinstance(batch_results, dict):
                print(f"Dict keys: {list(batch_results.keys())}")
                if "error" in batch_results:
                    print(f"❌ Erreur API: {batch_results['error']}")
            else:
                print(f"Type inattendu: {type(batch_results)}")
                
        except json.JSONDecodeError as e:
            print(f"❌ Erreur JSON decode: {e}")
            print(f"Raw response: {raw_response}")
            
    except Exception as e:
        print(f"❌ Erreur requête: {e}")

if __name__ == "__main__":
    debug_batch_creatives()