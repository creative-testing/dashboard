#!/usr/bin/env python3
"""
Parser pour la nomenclature de Martin
Format détecté : TYPE/ANGLE /FIELD3/ FIELD4/FIELD5/FORMAT /VERSION
"""
import re
from typing import Dict, Optional

def parse_martin_nomenclature(ad_name: str) -> Dict[str, str]:
    """
    Parse le nom d'annonce selon la nomenclature de Martin
    
    Exemple: "Nuevo/Olor a chetos  /NA/ NA/NA/IMG /V3"
    Retourne: {
        'type': 'Nuevo',
        'angle': 'Olor a chetos', 
        'format': 'IMG',
        'version': 'V3',
        'is_nomenclature': True
    }
    """
    
    # Nettoyer le nom
    name = ad_name.strip()
    
    # Vérifier si ça ressemble à la nomenclature de Martin
    if '/' not in name or name.count('/') < 3:
        return {
            'type': 'UNKNOWN',
            'angle': 'UNKNOWN', 
            'format': 'UNKNOWN',
            'version': 'UNKNOWN',
            'is_nomenclature': False,
            'original_name': name
        }
    
    try:
        # Split par /
        parts = [part.strip() for part in name.split('/')]
        
        if len(parts) < 6:  # Au moins TYPE/ANGLE/.../FORMAT/VERSION
            return {
                'type': 'UNKNOWN',
                'angle': 'UNKNOWN', 
                'format': 'UNKNOWN',
                'version': 'UNKNOWN',
                'is_nomenclature': False,
                'original_name': name
            }
        
        # Extraire les parties importantes
        type_creative = parts[0]  # "Nuevo" ou "It"
        angle = parts[1]          # "Olor a chetos", "Problemas digestivos"
        format_part = parts[-2]   # "IMG", "VID", etc.
        version = parts[-1]       # "V1", "V2", "V3"
        
        # Normaliser les valeurs
        if type_creative.lower() in ['it', 'iteracion']:
            type_creative = 'Iteración'
        elif type_creative.lower() in ['nuevo', 'new']:
            type_creative = 'Nuevo'
        
        # Normaliser format
        format_normalized = format_part.upper()
        if format_normalized in ['IMG', 'IMAGE', 'IMAGEN']:
            format_normalized = 'IMAGE'
        elif format_normalized in ['VID', 'VIDEO']:
            format_normalized = 'VIDEO'
        elif format_normalized in ['CAR', 'CAROUSEL', 'CARRUSEL']:
            format_normalized = 'CAROUSEL'
        
        # Normaliser angle (capitaliser première lettre)
        angle_normalized = angle.title() if angle != 'NA' else 'UNKNOWN'
        
        return {
            'type': type_creative,
            'angle': angle_normalized,
            'format': format_normalized, 
            'version': version,
            'is_nomenclature': True,
            'original_name': name,
            'confidence': 'high'
        }
        
    except Exception as e:
        return {
            'type': 'UNKNOWN',
            'angle': 'UNKNOWN', 
            'format': 'UNKNOWN',
            'version': 'UNKNOWN',
            'is_nomenclature': False,
            'original_name': name,
            'error': str(e)
        }

def analyze_petcare_nomenclature():
    """Analyse des annonces Petcare avec le parser"""
    
    # Exemples des noms qu'on a trouvés
    sample_names = [
        "Nuevo/Olor a chetos  /NA/ NA/NA/IMG /V3",
        "It/Olor a chetos  /NA/ NA/NA/IMG /V1", 
        "Nuevo/Problemas digestivos  /NA/ NA/NA/IMG /V1",
        "Nuevo/Lamido de patas /NA/ NA/NA/IMG /V2",
        "Nuevo/Problemas Digestivos/NA/ NA/NA/IMG /V1"
    ]
    
    print("🧪 TEST DU PARSER SUR ÉCHANTILLON PETCARE")
    print("=" * 60)
    
    angles_found = set()
    types_found = set()
    formats_found = set()
    
    for name in sample_names:
        parsed = parse_martin_nomenclature(name)
        
        print(f"\n📝 Nom: {name[:50]:50}")
        print(f"   ✅ Type: {parsed['type']}")
        print(f"   ✅ Angle: {parsed['angle']}") 
        print(f"   ✅ Format: {parsed['format']}")
        print(f"   ✅ Version: {parsed['version']}")
        print(f"   📊 Nomenclature: {'✅ Oui' if parsed['is_nomenclature'] else '❌ Non'}")
        
        if parsed['is_nomenclature']:
            angles_found.add(parsed['angle'])
            types_found.add(parsed['type'])
            formats_found.add(parsed['format'])
    
    print(f"\n🎯 RÉSULTATS DU PARSING:")
    print(f"  • Angles trouvés: {sorted(angles_found)}")
    print(f"  • Types trouvés: {sorted(types_found)}")  
    print(f"  • Formats trouvés: {sorted(formats_found)}")
    
    print(f"\n✅ PARSER FONCTIONNE ! On peut débloquer les analyses !")

if __name__ == "__main__":
    analyze_petcare_nomenclature()