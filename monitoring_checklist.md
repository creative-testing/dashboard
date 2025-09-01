# 📋 Checklist de surveillance

## À vérifier après le prochain run (dans ~1h)

### Sur GitHub Actions:
1. Aller sur : https://github.com/fred1433/creative-testing-dashboard/actions
2. Cliquer sur le dernier run
3. Vérifier que :
   - [ ] Step "Restore baseline cache" = vert (même si "cache miss" au début)
   - [ ] Step "Run Daily Refresh" = vert
   - [ ] Step "Save baseline to cache" = vert
   - [ ] Pas d'erreur de concurrency

### Sur le dashboard:
4. Aller sur : https://fred1433.github.io/creative-testing-dashboard/index_full.html
5. Vérifier que :
   - [ ] Les données sont à jour (check la date/heure)
   - [ ] Les 5 comptes sont visibles
   - [ ] Le switch de période fonctionne

## Si problème au premier run:

### Erreur "baseline not found":
```bash
# Solution : lancer un baseline manuel depuis local
cd /Users/frederic/Documents/ProjetsDev/creative-testing-agent
RUN_BASELINE=1 FETCH_DAYS=90 python3 scripts/production/fetch_with_smart_limits.py
```

### Erreur de cache:
- C'est pas grave, le cache se créera au run suivant
- Les données restent dans `docs/data/optimized/` donc le dashboard marche

## Points positifs actuels:
- ✅ Données locales OK (381MB, 7k ads)
- ✅ Dashboard fonctionnel
- ✅ Workflow amélioré (cache + concurrency)
- ✅ Git clean, tout commité

## Pronostic:
**85% de chances que tout marche du premier coup**
**15% qu'on doive faire un ajustement mineur**

Mais dans tous les cas, on a les données locales donc pas de perte!