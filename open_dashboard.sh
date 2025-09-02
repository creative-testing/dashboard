#!/bin/bash
# Script pour ouvrir le dashboard facilement

# Tuer les anciens serveurs sur le port 8080
lsof -ti:8080 | xargs kill -9 2>/dev/null

# Démarrer le serveur depuis le dossier docs
echo "🚀 Démarrage du serveur..."
cd docs && python3 -m http.server 8080 &
SERVER_PID=$!

# Attendre que le serveur démarre
sleep 2

# Ouvrir le dashboard
echo "📊 Ouverture du dashboard..."
open http://localhost:8080/index_full.html

echo "✅ Dashboard ouvert sur http://localhost:8080/index_full.html"
echo "   Pour arrêter le serveur: kill $SERVER_PID"