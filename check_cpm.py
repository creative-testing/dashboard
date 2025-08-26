import json

data = json.load(open('hybrid_data_7d.json'))
ads_with_cpm = [ad for ad in data['ads'] if ad.get('cpm', 0) > 0][:10]
print('Exemples CPM (7 jours):')
for ad in ads_with_cpm:
    cpm = ad['cpm']
    spend = ad['spend']
    impressions = ad['impressions']
    # CPM = (spend / impressions) * 1000
    calculated_cpm = (spend / impressions * 1000) if impressions > 0 else 0
    print(f'{ad["ad_name"][:25]:25} CPM: ${cpm:.2f} (calculé: ${calculated_cpm:.2f})')