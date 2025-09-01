#!/usr/bin/env python3
"""
Script pour reconstruire le baseline depuis les données GitHub.
Utilisé par le workflow quand le cache est vide.
"""
import json
import os
import urllib.request
from datetime import datetime

def download_github_data():
    """Télécharge les données depuis GitHub Pages"""
    base_url = "https://fred1433.github.io/creative-testing-dashboard/data/optimized"
    
    try:
        # Télécharger meta et agg
        print("📥 Downloading data from GitHub...")
        
        with urllib.request.urlopen(f"{base_url}/meta_v1.json") as response:
            meta = json.loads(response.read().decode())
        
        with urllib.request.urlopen(f"{base_url}/agg_v1.json") as response:
            agg = json.loads(response.read().decode())
        
        print(f"✅ Downloaded {len(agg['ads'])} ads")
        return meta, agg
        
    except Exception as e:
        print(f"❌ Could not download GitHub data: {e}")
        return None, None

def reconstruct_baseline(meta, agg):
    """Reconstruit un baseline minimal depuis les données columnar"""
    
    if not meta or not agg:
        return None
    
    print("🔄 Reconstructing baseline...")
    
    # On crée un baseline avec juste les métadonnées essentielles
    # Le fetch va de toute façon refaire les données
    baseline = {
        "metadata": {
            "reconstructed_from": "github",
            "timestamp": datetime.now().isoformat(),
            "ads_count": len(agg['ads'])
        },
        "daily_ads": []  # Vide mais le script sait qu'il y a des données
    }
    
    # On pourrait reconstruire les daily_ads mais ce n'est pas nécessaire
    # Le script va fetch les données fraîches de toute façon
    
    return baseline

def main():
    # Télécharger depuis GitHub
    meta, agg = download_github_data()
    
    if meta and agg:
        # Créer un fichier de signalisation
        os.makedirs('data/current', exist_ok=True)
        
        # Écrire un fichier marqueur pour indiquer qu'on a des données
        marker = {
            "github_ads_count": len(agg['ads']),
            "should_bootstrap": len(agg['ads']) > 1000  # Si on a déjà des données
        }
        
        with open('data/current/github_marker.json', 'w') as f:
            json.dump(marker, f)
        
        print(f"✅ Marker created: {len(agg['ads'])} ads available on GitHub")
        return 0
    else:
        print("⚠️ No GitHub data, will start fresh")
        return 1

if __name__ == "__main__":
    exit(main())