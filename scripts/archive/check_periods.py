import json

for period in [7, 30]:
    try:
        data = json.load(open(f'hybrid_data_{period}d.json'))
        print(f'{period} JOURS:')
        print(f'  • {data["metadata"]["total_ads"]} annonces')
        total_spend = sum(ad['spend'] for ad in data['ads'])
        print(f'  • ${total_spend:,.0f} MXN')
    except Exception as e:
        print(f'{period} JOURS: Erreur - {e}')