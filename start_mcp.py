#!/usr/bin/env python3
import os
from dotenv import load_dotenv
import sys

# Charger le token depuis .env
load_dotenv()
token = os.getenv('FACEBOOK_ACCESS_TOKEN')

if not token:
    print("❌ Erreur: FACEBOOK_ACCESS_TOKEN non trouvé dans .env")
    sys.exit(1)

# Configurer pour meta-ads-mcp
os.environ['META_ACCESS_TOKEN'] = token
os.environ['PIPEBOARD_API_TOKEN'] = 'local-mode'  # Mode local

print(f"✅ Token configuré (commence par: {token[:20]}...)")
print("Démarrage du serveur MCP local...")

# Lancer le serveur
os.system('mcp_env/bin/python -m meta_ads_mcp')
