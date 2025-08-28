#!/bin/bash
# Script pour démarrer l'API des démographies

echo "🚀 Démarrage de l'API démographiques..."
echo "📍 L'API sera disponible sur http://localhost:5000"
echo ""

# Installer Flask si nécessaire
pip install flask flask-cors requests python-dotenv 2>/dev/null

# Démarrer l'API
python api/fetch_demographics_endpoint.py