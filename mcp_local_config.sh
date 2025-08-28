#!/bin/bash
# Script pour lancer le serveur MCP local avec le token client

# Charger le token depuis .env
source .env

# Exporter pour le serveur MCP
export FACEBOOK_ACCESS_TOKEN=$FACEBOOK_ACCESS_TOKEN

# Activer l'environnement virtuel
source mcp_env/bin/activate

# Lancer le serveur MCP local
echo "Démarrage du serveur MCP local avec le token client..."
python -m meta_ads_mcp