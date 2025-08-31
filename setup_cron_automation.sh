#!/bin/bash

# Script pour configurer l'automatisation avec cron
# Exécute les refresh de données automatiquement

echo "🤖 Configuration de l'automatisation des refresh de données"
echo "=" * 60

# Obtenir le chemin absolu du projet
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "📁 Répertoire du projet: $PROJECT_DIR"

# Créer le répertoire de logs s'il n'existe pas
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"
echo "📝 Logs seront dans: $LOG_DIR"

# Backup du crontab actuel
echo ""
echo "💾 Sauvegarde du crontab actuel..."
crontab -l > "$LOG_DIR/crontab_backup_$(date +%Y%m%d_%H%M%S).txt" 2>/dev/null

# Créer les entrées cron
echo ""
echo "📋 Configuration des tâches planifiées:"
echo ""
echo "1. TAIL REFRESH (rapide, 3-4 min)"
echo "   - Fréquence: Toutes les 2 heures (6h, 8h, 10h, 12h, 14h, 16h, 18h, 20h, 22h)"
echo "   - Récupère: 3 derniers jours"
echo "   - Buffer: 2 heures"
echo ""
echo "2. BASELINE REFRESH (complet, 30-45 min)"
echo "   - Fréquence: Une fois par nuit à 3h du matin"
echo "   - Récupère: 90 derniers jours"
echo "   - Buffer: 2 heures"
echo ""

# Demander confirmation
read -p "Voulez-vous installer ces tâches automatiques? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Installation annulée"
    exit 1
fi

# Créer le nouveau crontab
CRON_FILE="$LOG_DIR/new_crontab.txt"

# Copier le crontab existant (sans nos lignes si elles existent déjà)
crontab -l 2>/dev/null | grep -v "run_tail_refresh.sh" | grep -v "run_baseline_full.sh" > "$CRON_FILE" 2>/dev/null || true

# Ajouter nos nouvelles lignes
cat >> "$CRON_FILE" << EOF

# ========================================
# Creative Testing Agent - Auto Refresh
# ========================================

# Tail refresh toutes les 2 heures - Données des 3 derniers jours (avec git push)
0 6,8,10,12,14,16,18,20,22 * * * cd $PROJECT_DIR && ./run_tail_refresh_with_git.sh >> $LOG_DIR/tail_refresh.log 2>&1

# Baseline complet une fois par nuit à 3h - Données des 90 derniers jours (avec git push)
0 3 * * * cd $PROJECT_DIR && ./run_baseline_full_with_git.sh >> $LOG_DIR/baseline_refresh.log 2>&1

# Nettoyage des logs de plus de 30 jours (dimanche à 4h)
0 4 * * 0 find $LOG_DIR -name "*.log" -mtime +30 -delete

EOF

# Installer le nouveau crontab
echo ""
echo "📥 Installation du crontab..."
crontab "$CRON_FILE"

if [ $? -eq 0 ]; then
    echo "✅ Crontab installé avec succès!"
    echo ""
    echo "📋 Vérification des tâches installées:"
    echo "----------------------------------------"
    crontab -l | grep -A 4 "Creative Testing Agent"
    echo ""
    echo "🎉 Automatisation configurée!"
    echo ""
    echo "📊 Prochaines exécutions:"
    echo "  - Prochain tail refresh: $(date -v+1H '+%Y-%m-%d %H:00')"
    echo "  - Prochain baseline: demain à 03:00"
    echo ""
    echo "📝 Pour voir les logs:"
    echo "  tail -f $LOG_DIR/tail_refresh.log"
    echo "  tail -f $LOG_DIR/baseline_refresh.log"
    echo ""
    echo "🔧 Pour désactiver:"
    echo "  crontab -e  # et supprimer les lignes Creative Testing Agent"
else
    echo "❌ Erreur lors de l'installation du crontab"
    exit 1
fi