#!/bin/bash
# Script pour démarrer le serveur MCP local avec le bon token

echo "🚀 Démarrage du serveur MCP local..."

# Charger les variables d'environnement
source .env

# Vérifier que le token existe
if [ -z "$FACEBOOK_ACCESS_TOKEN" ]; then
    echo "❌ Erreur: FACEBOOK_ACCESS_TOKEN non trouvé dans .env"
    exit 1
fi

# Exporter le token pour le serveur MCP
export META_ACCESS_TOKEN=$FACEBOOK_ACCESS_TOKEN
export PIPEBOARD_API_TOKEN="local-mode"

echo "✅ Token configuré (commence par: ${FACEBOOK_ACCESS_TOKEN:0:20}...)"

# Activer l'environnement virtuel si disponible
if [ -d "mcp_env" ]; then
    source mcp_env/bin/activate
    echo "✅ Environnement virtuel activé"
fi

# Lancer le serveur MCP
echo "📡 Lancement du serveur MCP..."
python -m meta_ads_mcp