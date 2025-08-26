#!/usr/bin/env python3
"""
Analyse les 456 annonces non classifiées pour trouver des patterns.
"""

import pandas as pd
import re
from collections import Counter

# Lire le CSV exporté
df = pd.read_csv('ad_names_export_20250821_194658.csv')

# Fonction pour classifier les formats
def classify_format(name):
    name_lower = name.lower()
    
    # Patterns existants
    if any(x in name_lower for x in ['video', 'vid', 'vídeo']):
        return 'VIDEO'
    elif any(x in name_lower for x in ['hook', 'h1', 'h2', 'h3', 'h4', 'h5']):
        return 'HOOK'
    elif any(x in name_lower for x in ['image', 'img', 'imagen', 'banner']):
        return 'IMAGE'
    else:
        return 'UNKNOWN'

# Classifier
df['format'] = df['ad_name'].apply(classify_format)

# Filtrer les UNKNOWN
unknown_ads = df[df['format'] == 'UNKNOWN']
print(f"📊 Total d'annonces UNKNOWN: {len(unknown_ads)}")
print("=" * 80)

# Analyser les patterns dans les noms UNKNOWN
print("\n🔍 ANALYSE DES PATTERNS DANS LES NOMS UNKNOWN:")
print("-" * 40)

# Extraire des mots/patterns communs
all_words = []
patterns_found = {
    'carousel': [],
    'carrusel': [],
    'copy': [],
    'test': [],
    'prueba': [],
    'demo': [],
    'story': [],
    'stories': [],
    'reel': [],
    'reels': [],
    'feed': [],
    'collection': [],
    'catalog': [],
    'catálogo': [],
    'slide': [],
    'ugc': [],
    'testimonial': [],
    'review': [],
    'promo': [],
    'sale': [],
    'descuento': [],
    'oferta': [],
    'black': [],
    'friday': [],
    'navidad': [],
    'christmas': [],
    'nuevo': [],
    'new': [],
    'lanzamiento': [],
    'launch': [],
}

for name in unknown_ads['ad_name']:
    name_lower = name.lower()
    words = re.findall(r'\b\w+\b', name_lower)
    all_words.extend(words)
    
    # Chercher des patterns spécifiques
    for pattern, matches in patterns_found.items():
        if pattern in name_lower:
            matches.append(name)

# Afficher les patterns trouvés
print("\n📌 PATTERNS IDENTIFIÉS:")
for pattern, matches in patterns_found.items():
    if matches:
        print(f"\n'{pattern.upper()}' trouvé dans {len(matches)} annonces:")
        for i, match in enumerate(matches[:5], 1):  # Montrer max 5 exemples
            print(f"  {i}. {match[:60]}...")
        if len(matches) > 5:
            print(f"  ... et {len(matches)-5} autres")

# Compter les mots les plus fréquents
word_counts = Counter(all_words)
print("\n📊 TOP 30 MOTS LES PLUS FRÉQUENTS (dans les UNKNOWN):")
print("-" * 40)
for word, count in word_counts.most_common(30):
    if len(word) > 2:  # Ignorer les mots très courts
        print(f"{word:20} : {count:4} occurrences")

# Analyser les formats potentiels
print("\n🎯 NOUVEAUX FORMATS SUGGÉRÉS:")
print("-" * 40)

new_classifications = {
    'CAROUSEL': 0,
    'STORIES': 0,
    'REELS': 0,
    'CATALOG': 0,
    'UGC': 0,
    'PROMO': 0,
    'TEST': 0,
}

for name in unknown_ads['ad_name']:
    name_lower = name.lower()
    if any(x in name_lower for x in ['carousel', 'carrusel']):
        new_classifications['CAROUSEL'] += 1
    elif any(x in name_lower for x in ['story', 'stories']):
        new_classifications['STORIES'] += 1
    elif any(x in name_lower for x in ['reel', 'reels']):
        new_classifications['REELS'] += 1
    elif any(x in name_lower for x in ['catalog', 'catálogo', 'collection']):
        new_classifications['CATALOG'] += 1
    elif 'ugc' in name_lower:
        new_classifications['UGC'] += 1
    elif any(x in name_lower for x in ['promo', 'sale', 'descuento', 'oferta', 'black', 'friday']):
        new_classifications['PROMO'] += 1
    elif any(x in name_lower for x in ['test', 'prueba', 'copy']):
        new_classifications['TEST'] += 1

print("\nSi on appliquait ces nouveaux patterns:")
for format_type, count in sorted(new_classifications.items(), key=lambda x: x[1], reverse=True):
    if count > 0:
        print(f"  {format_type:12} : {count:4} annonces")

remaining = len(unknown_ads) - sum(new_classifications.values())
print(f"  {'STILL_UNKNOWN':12} : {remaining:4} annonces")

# Montrer quelques exemples d'annonces qui resteraient UNKNOWN
print("\n❓ EXEMPLES D'ANNONCES QUI RESTERAIENT NON CLASSIFIÉES:")
print("-" * 40)
still_unknown = []
for name in unknown_ads['ad_name']:
    name_lower = name.lower()
    if not any([
        any(x in name_lower for x in ['carousel', 'carrusel']),
        any(x in name_lower for x in ['story', 'stories']),
        any(x in name_lower for x in ['reel', 'reels']),
        any(x in name_lower for x in ['catalog', 'catálogo', 'collection']),
        'ugc' in name_lower,
        any(x in name_lower for x in ['promo', 'sale', 'descuento', 'oferta', 'black', 'friday']),
        any(x in name_lower for x in ['test', 'prueba', 'copy'])
    ]):
        still_unknown.append(name)

for i, name in enumerate(still_unknown[:20], 1):
    print(f"{i:2}. {name[:70]}...")

print(f"\nTotal qui resterait UNKNOWN: {len(still_unknown)}")