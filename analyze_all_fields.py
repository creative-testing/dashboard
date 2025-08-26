#!/usr/bin/env python3
"""
Analyser TOUTES les données qu'on récupère réellement
"""
import json
from meta_insights import MetaInsightsFetcher
from collections import defaultdict

def analyze_all_available_data():
    print("📊 ANALYSE COMPLÈTE DES DONNÉES RÉCUPÉRÉES (7 DERNIERS JOURS)")
    print("=" * 80)
    
    # Récupérer les données
    fetcher = MetaInsightsFetcher()
    raw_data = fetcher.fetch_insights(filtering="no_filter", limit=200)
    processed_data = fetcher.process_insights(raw_data)
    
    print(f"\n✅ {len(raw_data)} annonces récupérées")
    
    # 1. ANALYSER LES CHAMPS BRUTS
    print("\n📋 CHAMPS DISPONIBLES DANS LES DONNÉES BRUTES:")
    print("-" * 40)
    
    if raw_data:
        sample = raw_data[0]
        for key in sorted(sample.keys()):
            value = sample[key]
            if value is not None:
                if isinstance(value, list):
                    print(f"  • {key}: Liste avec {len(value)} éléments")
                    if value and len(value) > 0:
                        # Montrer la structure
                        if isinstance(value[0], dict):
                            print(f"    Structure: {list(value[0].keys())}")
                elif isinstance(value, (int, float)):
                    print(f"  • {key}: {value}")
                else:
                    print(f"  • {key}: {str(value)[:50]}...")
    
    # 2. ANALYSER LES ACTIONS DISPONIBLES
    print("\n📌 TYPES D'ACTIONS/CONVERSIONS DISPONIBLES:")
    print("-" * 40)
    
    action_types = defaultdict(int)
    action_values = defaultdict(float)
    
    for ad in raw_data:
        if "actions" in ad and ad["actions"]:
            for action in ad["actions"]:
                action_type = action.get("action_type", "unknown")
                value = float(action.get("value", 0))
                action_types[action_type] += value
        
        if "action_values" in ad and ad["action_values"]:
            for action in ad["action_values"]:
                action_type = action.get("action_type", "unknown")
                value = float(action.get("value", 0))
                action_values[action_type] += value
    
    print("\n🎯 Actions (comptage):")
    for action_type, count in sorted(action_types.items(), key=lambda x: x[1], reverse=True)[:15]:
        print(f"  • {action_type}: {count:.0f}")
    
    print("\n💰 Valeurs des actions:")
    for action_type, value in sorted(action_values.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  • {action_type}: ${value:,.2f}")
    
    # 3. ANALYSER LES MÉTRIQUES VIDÉO
    print("\n🎥 MÉTRIQUES VIDÉO DISPONIBLES:")
    print("-" * 40)
    
    video_metrics = {
        "Avec vues 3s": 0,
        "Avec vues complètes": 0,
        "Avec thruplay": 0,
        "Sans métriques vidéo": 0
    }
    
    for ad in raw_data:
        has_video = False
        
        if "video_play_actions" in ad and ad["video_play_actions"]:
            video_metrics["Avec vues 3s"] += 1
            has_video = True
        
        if "video_p100_watched_actions" in ad and ad["video_p100_watched_actions"]:
            video_metrics["Avec vues complètes"] += 1
            has_video = True
            
        if "video_thruplay_watched_actions" in ad and ad["video_thruplay_watched_actions"]:
            video_metrics["Avec thruplay"] += 1
            has_video = True
        
        if not has_video:
            video_metrics["Sans métriques vidéo"] += 1
    
    for metric, count in video_metrics.items():
        print(f"  • {metric}: {count} annonces")
    
    # 4. ANALYSER LES DONNÉES PROCESSÉES
    print("\n📊 DONNÉES APRÈS TRAITEMENT:")
    print("-" * 40)
    
    if processed_data:
        sample_processed = processed_data[0]
        print("\nChamps enrichis disponibles:")
        
        for key in sorted(sample_processed.keys()):
            value = sample_processed[key]
            if value is not None:
                if isinstance(value, float):
                    print(f"  • {key}: {value:.2f}")
                elif isinstance(value, int):
                    print(f"  • {key}: {value}")
                else:
                    print(f"  • {key}: {type(value).__name__}")
    
    # 5. STATISTIQUES GLOBALES
    print("\n📈 STATISTIQUES GLOBALES:")
    print("-" * 40)
    
    total_spend = sum(float(ad.get("spend", 0)) for ad in raw_data)
    total_impressions = sum(int(ad.get("impressions", 0)) for ad in raw_data)
    total_reach = sum(int(ad.get("reach", 0)) for ad in raw_data)
    total_clicks = sum(int(ad.get("clicks", 0)) for ad in raw_data)
    
    # Compter les achats
    total_purchases = 0
    total_purchase_value = 0
    
    for ad in raw_data:
        if "actions" in ad:
            for action in ad["actions"]:
                if action["action_type"] in ["purchase", "omni_purchase"]:
                    total_purchases += int(action["value"])
        
        if "action_values" in ad:
            for action in ad["action_values"]:
                if action["action_type"] in ["purchase", "omni_purchase"]:
                    total_purchase_value += float(action["value"])
    
    print(f"  💰 Dépense totale: ${total_spend:,.2f}")
    print(f"  👁️ Impressions: {total_impressions:,}")
    print(f"  🎯 Portée: {total_reach:,}")
    print(f"  👆 Clics: {total_clicks:,}")
    print(f"  🛒 Achats: {total_purchases}")
    print(f"  💵 Valeur des achats: ${total_purchase_value:,.2f}")
    print(f"  📊 ROAS global: {total_purchase_value/total_spend if total_spend > 0 else 0:.2f}")
    print(f"  📱 CTR moyen: {(total_clicks/total_impressions*100) if total_impressions > 0 else 0:.2f}%")
    
    # 6. IDENTIFIER LES DONNÉES MANQUANTES
    print("\n⚠️ DONNÉES NON RÉCUPÉRÉES (mais potentiellement disponibles):")
    print("-" * 40)
    
    missing_fields = [
        "creative details (titre, body, image_url, video_id)",
        "audience demographics (age, gender breakdowns)",
        "placement details (facebook, instagram, etc.)",
        "device breakdown",
        "hourly performance",
        "geographic breakdown",
        "custom conversions details",
        "landing page views",
        "add to cart events",
        "initiate checkout events"
    ]
    
    for field in missing_fields:
        print(f"  ❌ {field}")
    
    # 7. SAUVEGARDER UN RAPPORT DÉTAILLÉ
    report = {
        "summary": {
            "total_ads": len(raw_data),
            "total_spend": total_spend,
            "total_purchases": total_purchases,
            "total_value": total_purchase_value,
            "roas": total_purchase_value/total_spend if total_spend > 0 else 0
        },
        "available_fields": list(sample.keys()) if raw_data else [],
        "action_types": dict(action_types),
        "action_values": dict(action_values),
        "sample_raw_ad": raw_data[0] if raw_data else {},
        "sample_processed_ad": processed_data[0] if processed_data else {}
    }
    
    with open("data_analysis_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print("\n✅ Rapport détaillé sauvegardé dans data_analysis_report.json")
    
    print("\n" + "=" * 80)
    print("📋 RÉSUMÉ: CE QU'ON RÉCUPÈRE ACTUELLEMENT")
    print("-" * 40)
    print("✅ Identifiants (ad_id, campaign_id, etc.)")
    print("✅ Métriques de base (spend, impressions, reach, CTR, CPM)")
    print("✅ Clics (tous types)")
    print("✅ Conversions et achats")
    print("✅ ROAS")
    print("✅ Métriques vidéo (vues 3s, complètes)")
    print("✅ Dates de la période")
    print("\n❌ PAS ENCORE: Créatifs détaillés, breakdowns démographiques, placements")

if __name__ == "__main__":
    analyze_all_available_data()