#!/usr/bin/env python3
"""
Récupère les VRAIS formats depuis l'API Meta, pas depuis les noms !
"""

import requests
import json
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from collections import Counter

load_dotenv()

FB_TOKEN = os.getenv('FB_TOKEN')

def get_real_formats():
    """Récupère les vrais formats des annonces depuis l'API."""
    
    # Obtenir les comptes
    accounts_url = "https://graph.facebook.com/v23.0/me/adaccounts"
    accounts_params = {
        "access_token": FB_TOKEN,
        "fields": "name,account_id",
        "limit": 100
    }
    
    response = requests.get(accounts_url, params=accounts_params)
    accounts = response.json().get("data", [])
    
    print(f"📊 Analyse de {len(accounts)} comptes...")
    
    # Collecter les formats
    format_counts = Counter()
    format_examples = {}
    total_ads = 0
    ads_with_creative = 0
    
    since_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    
    for account in accounts:
        account_id = account['account_id']
        
        # Récupérer les ads actives
        ads_url = f"https://graph.facebook.com/v23.0/{account_id}/ads"
        ads_params = {
            "access_token": FB_TOKEN,
            "fields": "id,name,creative{id,object_type,video_id,image_url,carousel_ads_child_link,object_story_spec}",
            "time_range": f"{{'since':'{since_date}','until':'today'}}",
            "limit": 100,
            "effective_status": "['ACTIVE']"
        }
        
        try:
            response = requests.get(ads_url, params=ads_params)
            ads = response.json().get("data", [])
            
            for ad in ads:
                total_ads += 1
                ad_name = ad.get('name', 'Sans nom')
                
                if 'creative' in ad:
                    ads_with_creative += 1
                    creative = ad['creative']
                    
                    # Déterminer le format RÉEL
                    format_type = None
                    
                    # Méthode 1: object_type
                    object_type = creative.get('object_type', '').upper()
                    if object_type:
                        format_type = object_type
                    
                    # Méthode 2: Vérifier les champs spécifiques
                    if not format_type:
                        if creative.get('video_id'):
                            format_type = 'VIDEO'
                        elif creative.get('carousel_ads_child_link'):
                            format_type = 'CAROUSEL'
                        elif creative.get('image_url'):
                            format_type = 'IMAGE'
                        elif creative.get('object_story_spec'):
                            spec = creative['object_story_spec']
                            if spec.get('video_data'):
                                format_type = 'VIDEO'
                            elif spec.get('link_data'):
                                link_data = spec['link_data']
                                if link_data.get('child_attachments'):
                                    format_type = 'CAROUSEL'
                                elif link_data.get('image_hash') or link_data.get('picture'):
                                    format_type = 'IMAGE'
                    
                    if not format_type:
                        format_type = 'UNKNOWN'
                    
                    format_counts[format_type] += 1
                    
                    # Garder quelques exemples
                    if format_type not in format_examples:
                        format_examples[format_type] = []
                    if len(format_examples[format_type]) < 5:
                        format_examples[format_type].append(ad_name)
                        
        except Exception as e:
            print(f"  ❌ Erreur pour {account['name']}: {e}")
            continue
    
    print("\n" + "=" * 80)
    print(f"✅ {total_ads} annonces analysées")
    print(f"✅ {ads_with_creative} avec données créatives")
    
    print("\n📊 DISTRIBUTION DES VRAIS FORMATS (depuis l'API):")
    print("-" * 40)
    
    total = sum(format_counts.values())
    for format_type, count in format_counts.most_common():
        percentage = (count / total * 100) if total > 0 else 0
        print(f"  {format_type:15} : {count:5} annonces ({percentage:.1f}%)")
    
    print("\n📝 EXEMPLES PAR FORMAT:")
    print("-" * 40)
    for format_type, examples in format_examples.items():
        print(f"\n{format_type}:")
        for i, example in enumerate(examples, 1):
            print(f"  {i}. {example[:60]}...")
    
    return format_counts

if __name__ == "__main__":
    print("🚀 Récupération des VRAIS formats depuis l'API Meta...")
    print("=" * 80)
    
    formats = get_real_formats()
    
    # Sauvegarder les résultats
    output = {
        'timestamp': datetime.now().isoformat(),
        'formats': dict(formats)
    }
    
    with open('real_formats_distribution.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print("\n📁 Résultats sauvegardés dans real_formats_distribution.json")