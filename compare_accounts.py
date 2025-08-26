#!/usr/bin/env python3
import json
from collections import defaultdict

# Fast data (insights)
d = json.load(open('fast_data_20250825_202422.json'))
acc = defaultdict(float)
for ad in d['ads']:
    acc[ad['account_name']] += ad['spend']
print('Fast data (1630 ads - via /insights):')
for name, spend in sorted(acc.items(), key=lambda x:x[1], reverse=True)[:5]:
    print(f'  {name[:25]:25} ${spend:8,.0f} MXN')

print()

# Real formats data (ads)  
d2 = json.load(open('real_formats_data_20250825_202841.json'))
acc2 = defaultdict(float)
for ad in d2['ads']:
    acc2[ad['account_name']] += ad['spend']
print('Real formats (459 ads - via /ads):')
for name, spend in sorted(acc2.items(), key=lambda x:x[1], reverse=True)[:5]:
    print(f'  {name[:25]:25} ${spend:8,.0f} MXN')

# Chercher Chabacano
print('\nRecherche de Chabacano:')
for name, spend in acc.items():
    if 'Chabacano' in name or 'chabacano' in name:
        print(f'  Dans fast_data: {name} -> ${spend:,.0f}')
        
for name, spend in acc2.items():
    if 'Chabacano' in name or 'chabacano' in name:
        print(f'  Dans real_formats: {name} -> ${spend:,.0f}')