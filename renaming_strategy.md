# File Renaming Strategy

## Current Situation
- File: `data/current/baseline_90d_daily.json`
- Problem: Name suggests "90 days baseline" but actually contains ALL daily data
- Size: ~380MB with 96,306 records

## Proposed New Name
`data/current/all_daily_data.json`

## Why This Name?
- **Accurate**: Reflects that it contains all daily ad data
- **Clear**: No confusion about "baseline" or "90d" 
- **Simple**: Easy to understand its purpose

## Migration Plan

### Option 1: Safe Migration (Recommended)
```bash
# 1. Create symlink for compatibility
ln -s all_daily_data.json baseline_90d_daily.json

# 2. Update scripts gradually
# 3. Remove symlink after testing
```

### Option 2: Direct Rename (Risky)
```bash
# 1. Rename file
mv baseline_90d_daily.json all_daily_data.json

# 2. Update all scripts immediately
```

## Files That Need Updates

1. **scripts/production/fetch_with_smart_limits.py**
   - Line 566: `baseline_file = 'data/current/baseline_90d_daily.json'`

2. **scripts/transform_to_columnar.py**
   - Line 31: `baseline_path = os.path.join(input_dir, 'baseline_90d_daily.json')`

3. **scripts/production/build_baseline_from_hybrid.py**
   - Line 239: `output_path = 'data/current/baseline_90d_daily.json'`

4. **Any diagnostic scripts** that reference the file

## Recommendation

**WAIT** for now because:
1. System just became stable after fixes
2. Other assistant reviewing architecture
3. Automated workflow runs every 2 hours
4. Risk of breaking production dashboard

**AFTER** system proves stable (1-2 days):
1. Use symlink approach for safety
2. Test locally first
3. Update one script at a time
4. Monitor automated runs

## Alternative: Keep Current Name

Document clearly that despite the name, this file contains:
- ALL daily data (not just 90 days)
- Gets updated with new data via merge
- Is the source of truth for all periods