#!/usr/bin/env python3
"""
Test de l'analyse intelligente avec de vraies données Meta
"""
from meta_insights import MetaInsightsFetcher
from smart_analyzer import SmartAnalyzer
import json

def test_with_real_data():
    print("🚀 RÉCUPÉRATION ET ANALYSE INTELLIGENTE DES DONNÉES")
    print("=" * 80)
    
    # 1. Récupérer les vraies données
    print("\n📥 Récupération des données Meta...")
    fetcher = MetaInsightsFetcher()
    raw_data = fetcher.fetch_insights(filtering="no_filter", limit=10)
    
    if not raw_data:
        print("❌ Aucune donnée récupérée")
        return
    
    print(f"✅ {len(raw_data)} annonces récupérées")
    
    # 2. Analyser avec l'analyseur intelligent
    print("\n🧠 Analyse intelligente des annonces...")
    analyzer = SmartAnalyzer()
    
    all_insights = []
    
    for i, ad_data in enumerate(raw_data[:5], 1):  # Analyser les 5 premières
        print(f"\n{'='*60}")
        print(f"📊 ANNONCE {i}: {ad_data.get('ad_name', 'N/A')}")
        print(f"{'='*60}")
        
        insights = analyzer.analyze_ad(ad_data)
        all_insights.append(insights)
        
        # Afficher les résultats
        print(f"\n💰 MÉTRIQUES DE BASE:")
        print(f"  • Dépense: ${insights.spend:,.2f}")
        print(f"  • Impressions: {insights.impressions:,}")
        print(f"  • CTR: {insights.ctr:.2f}%")
        print(f"  • CPM: ${insights.cpm:.2f}")
        print(f"  • ROAS: {insights.roas:.2f}")
        
        print(f"\n🔍 INSIGHTS CACHÉS (ce que Pablo ne sait pas qu'il veut):")
        print(f"  • Fatigue créative: {insights.fatigue_status} (Score: {insights.fatigue_score:.0f}/100)")
        print(f"  • Qualité Meta: {insights.quality_status} (Score: {insights.meta_quality_score:.0f}/100)")
        print(f"  • Engagement authentique: {insights.real_engagement_rate:.2f}%")
        print(f"  • Ratio multi-clics: {insights.multi_click_ratio:.2f}x {'(Intérêt élevé!)' if insights.multi_click_ratio > 1.5 else ''}")
        
        if insights.video_retention_curve:
            print(f"\n🎥 PERFORMANCE VIDÉO:")
            print(f"  • Force du hook (3s→25%): {insights.video_hook_strength:.1f}%")
            print(f"  • Plus grosse chute: {insights.video_drop_point}")
            
            # Mini graphique de rétention
            print("  • Courbe de rétention:")
            for point, value in list(insights.video_retention_curve.items())[:5]:
                bar = "█" * int(value/5)
                print(f"    {point:>4}: {bar:<20} {value:.1f}%")
        
        if insights.funnel_scores:
            print(f"\n🔄 ANALYSE DU FUNNEL:")
            for step, score in insights.funnel_scores.items():
                indicator = "✅" if score > 10 else "⚠️" if score > 5 else "❌"
                print(f"  {indicator} {step}: {score:.2f}%")
            print(f"  • Point faible: {insights.biggest_drop}")
        
        print(f"\n💡 RECOMMANDATIONS AUTOMATIQUES:")
        if insights.recommendations:
            for rec in insights.recommendations[:3]:  # Top 3 recommandations
                print(f"  {rec}")
        else:
            print("  ✅ Performance optimale")
    
    # 3. Résumé global
    print(f"\n{'='*80}")
    print("📈 RÉSUMÉ GLOBAL DE L'ANALYSE")
    print(f"{'='*80}")
    
    # Identifier les patterns
    avg_fatigue = sum(i.fatigue_score for i in all_insights) / len(all_insights)
    avg_quality = sum(i.meta_quality_score for i in all_insights) / len(all_insights)
    
    print(f"\n🎯 INSIGHTS GLOBAUX:")
    print(f"  • Fatigue moyenne: {avg_fatigue:.0f}/100 {'⚠️ Rafraîchir créatifs' if avg_fatigue > 40 else '✅'}")
    print(f"  • Qualité Meta moyenne: {avg_quality:.0f}/100 {'⚠️ Améliorer qualité' if avg_quality < 50 else '✅'}")
    
    # Top performers
    best_roas = max(all_insights, key=lambda x: x.roas)
    print(f"\n🏆 MEILLEUR ROAS: {best_roas.ad_name} ({best_roas.roas:.2f})")
    
    best_quality = max(all_insights, key=lambda x: x.meta_quality_score)
    print(f"⭐ MEILLEURE QUALITÉ: {best_quality.ad_name} (Score: {best_quality.meta_quality_score:.0f})")
    
    # Sauvegarder le rapport
    report = {
        "date": fetcher.fetch_insights.__name__,
        "total_ads_analyzed": len(all_insights),
        "insights": [
            {
                "ad_name": i.ad_name,
                "spend": i.spend,
                "roas": i.roas,
                "fatigue_score": i.fatigue_score,
                "meta_quality_score": i.meta_quality_score,
                "recommendations": i.recommendations
            }
            for i in all_insights
        ]
    }
    
    with open("smart_insights_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print("\n📁 Rapport sauvegardé dans smart_insights_report.json")

if __name__ == "__main__":
    test_with_real_data()