#!/usr/bin/env python3
"""
Script pour récupérer toutes les données et les sauvegarder
"""
import json
import csv
from meta_insights import MetaInsightsFetcher
from parser import AdNameParser

def main():
    print("🚀 Récupération des données Meta Ads...")
    
    # 1. Récupérer les données
    fetcher = MetaInsightsFetcher()
    raw_insights = fetcher.fetch_insights(
        lookback_days=7,
        limit=100,  # Récupérer plus de données
        filtering="no_filter"
    )
    
    if not raw_insights:
        print("❌ Aucune donnée récupérée")
        return
    
    print(f"✅ {len(raw_insights)} annonces récupérées")
    
    # 2. Traiter les données
    processed = fetcher.process_insights(raw_insights)
    
    # 3. Sauvegarder en JSON pour analyse
    with open("raw_data.json", "w", encoding="utf-8") as f:
        json.dump(processed, f, indent=2, ensure_ascii=False)
    print("📁 Données sauvegardées dans raw_data.json")
    
    # 4. Sauvegarder en CSV
    if processed:
        keys = processed[0].keys()
        with open("ads_data.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(processed)
        print("📁 Données sauvegardées dans ads_data.csv")
    
    # 5. Analyser les noms d'annonces
    print("\n📊 Analyse des noms d'annonces:")
    print("-" * 60)
    
    parser = AdNameParser()
    parsing_results = []
    
    for ad in processed[:10]:  # Analyser les 10 premières
        ad_name = ad.get("ad_name", "")
        parsed = parser.parse(ad_name)
        
        print(f"\n📝 {ad_name}")
        print(f"   Angle: {parsed.angle or '❌'}")
        print(f"   Créateur: {parsed.creator_gender or '?'}{parsed.creator_age or ''}")
        print(f"   Format: {parsed.format_type or '❌'}")
        print(f"   Source: {parsed.parse_source} ({parsed.confidence:.0%})")
        print(f"   Spend: ${ad.get('spend', 0):.2f} | ROAS: {ad.get('roas', 0):.2f}")
        
        # Ajouter au résultat
        parsing_results.append({
            "ad_id": ad.get("ad_id"),
            "ad_name": ad_name,
            "angle": parsed.angle,
            "creator_gender": parsed.creator_gender,
            "creator_age": parsed.creator_age,
            "format": parsed.format_type,
            "parse_source": parsed.parse_source,
            "confidence": parsed.confidence,
            "ambiguity": parsed.ambiguity_reason,
            "spend": ad.get("spend"),
            "roas": ad.get("roas"),
            "purchases": ad.get("purchases")
        })
    
    # 6. Sauvegarder les résultats de parsing
    with open("parsed_ads.csv", "w", newline="", encoding="utf-8") as f:
        if parsing_results:
            writer = csv.DictWriter(f, fieldnames=parsing_results[0].keys())
            writer.writeheader()
            writer.writerows(parsing_results)
    print("\n📁 Résultats de parsing sauvegardés dans parsed_ads.csv")
    
    # 7. Statistiques globales
    print("\n📈 Statistiques globales:")
    print("-" * 60)
    total_spend = sum(ad.get("spend", 0) for ad in processed)
    total_purchases = sum(ad.get("purchases", 0) for ad in processed)
    total_value = sum(ad.get("purchase_value", 0) for ad in processed)
    
    print(f"Total dépensé: ${total_spend:,.2f}")
    print(f"Total achats: {total_purchases}")
    print(f"Valeur totale: ${total_value:,.2f}")
    print(f"ROAS global: {total_value/total_spend if total_spend > 0 else 0:.2f}")
    
    # Compter les formats détectés
    video_count = sum(1 for ad in processed if ad.get("video_3s_views") is not None)
    print(f"\nFormats détectés:")
    print(f"  Vidéos: {video_count}")
    print(f"  Images: {len(processed) - video_count}")

if __name__ == "__main__":
    main()