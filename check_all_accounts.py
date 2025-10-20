#!/usr/bin/env python3
"""
Script pour vérifier l'état du refresh des 70 comptes de production
"""
import requests
import json

TENANT_ID = "c0c595ab-3903-4256-b8d7-cb9709ac9206"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIzNDhjMjY2NS1jNTNmLTQ1N2QtYTAzNi1lYWMyYWNhYTQxZTQiLCJ0aWQiOiJjMGM1OTVhYi0zOTAzLTQyNTYtYjhkNy1jYjk3MDlhYzkyMDYiLCJhdWQiOiJhcGkiLCJpc3MiOiJjcmVhdGl2ZS10ZXN0aW5nLWFwaSIsImlhdCI6MTc2MDgyMTUzMywiZXhwIjoxNzYxNDI2MzMzfQ.Ae03c67lqpYZJNCMhRz6V2-2z7KJQ1jHf4NO87vw_iI"

# Liste des 70 comptes (extraite de la réponse du refresh-all)
ACCOUNTS = [
    ("act_10937948", "KRAPEL CUENTA PUBLICITARIA"),
    ("act_28755295", "28755295"),
    ("act_18856533", "18856533"),
    ("act_217777970", "217777970"),
    ("act_186473512", "Essentiasl Mx"),
    ("act_13235155", "CULTO APPAREL"),
    ("act_10157817450730790", "Publicidad Ahal BUENA"),
    ("act_621212048277595", "Aretina"),
    ("act_268044333900549", "S & S GOURMET"),
    ("act_339383383575224", "Ana Sol Carrera"),
    ("act_340205496905562", "Anuncios MEETIK"),
    ("act_483103779157625", "Arua Joyería"),
    ("act_606969153369621", "GRUPO PRESLOW/ROCKHAMPTON"),
    ("act_424343231745924", "VARDO OFICIAL"),
    ("act_269481294089046", "Acapella Apparel Ad Account"),
    ("act_296822174896400", "Kocare Beauty"),
    ("act_3501188146641743", "Chabacano 1"),
    ("act_3816311378380297", "Ads-Alchemy"),
    ("act_348729573129816", "Pautas Citlali Joyas"),
    ("act_2610539099239496", "VITDAYMX"),
    ("act_705913680340025", "shopify"),
    ("act_1531191393746034", "La horma mx"),
    ("act_3625928541013770", "FITFAM APP"),
    ("act_7111965392190767", "SANTA_PHIA_1"),
    ("act_235623597993209", "PUBLICIDAD PERFUMARA"),
    ("act_1048910062308622", "Reset A&F"),
    ("act_1220340971806734", "Rose&Mimosas"),
    ("act_950816465856773", "Cero Degrees North Ad Account"),
    ("act_458990299051040", "WU"),
    ("act_701159007690556", "Zanetti"),
    ("act_954628458749162", "GB Nueva Cuenta"),
    ("act_640579220761612", "ApiGreen Cuenta Publicitaria"),
    ("act_3189193134676120", "Piu Pieza Unica"),
    ("act_3372190019772184", "Regula"),
    ("act_369756272038113", "Multiblue Shopify Only"),
    ("act_1164188034501535", "Lactana cuenta publicitaria LFS"),
    ("act_518864073478981", "Kyra Gold"),
    ("act_834887760925832", "SEPUA"),
    ("act_1179624066248016", "Charm Factory - Kosette Beltran"),
    ("act_3453418304892764", "Charm Factory - Ads Alchemy"),
    ("act_167642466054617", "Smellers MX"),
    ("act_909067916968172", "Cuenta Comercial 2"),
    ("act_245656211380454", "Olimpo Backup"),
    ("act_658415425809774", "APOLO 1.0"),
    ("act_1530776461009181", "YEKE ADS"),
    ("act_1077444223398785", "VARDO RESPALDO"),
    ("act_298100049815376", "Mandala"),
    ("act_941995250763642", "Swappp Energy"),
    ("act_2791771454334484", "Koro Beauty"),
    ("act_462130843128933", "Shorbull's ad account"),
    ("act_1733006760567787", "Moscca Fine Fragrance"),
    ("act_533931465698976", "Aromaespejo portafolio"),
    ("act_1037663391078565", "Botanical Doctor"),
    ("act_499946842833887", "origoshoes.mexico"),
    ("act_3656788454467002", "Blue Banana Brand México"),
    ("act_1514208369457788", "Oaxacapsx"),
    ("act_505650941803538", "Naturale 2024"),
    ("act_1571195200455755", "Gorilla Pump CUENTA"),
    ("act_1818198352335065", "koneli.mx"),
    ("act_627000756526718", "JerseyEra's ad account"),
    ("act_934085132010297", "MUUD chocolate"),
    ("act_1010816117056390", "CP-SOHOCOLOR"),
    ("act_297112083495970", "Petcare 2"),
    ("act_1177108000799963", "popmartmexico.shop's ad account"),
    ("act_4051320321853005", "Cloe Time Shopify"),
    ("act_4166368596943604", "Nanah.mx"),
    ("act_670108326011892", "SCENTICA"),
    ("act_569725406184566", "LeanTravel"),
    ("act_631636869569722", "AHAL BIO"),
    ("act_752780900723881", "BIANCA-CUENTA P"),
]

headers = {"Authorization": f"Bearer {TOKEN}"}
api_url = "https://creative-testing-api.onrender.com"

print(f"🔍 Vérification de {len(ACCOUNTS)} comptes...\n")

total_ads = 0
active_accounts = 0
inactive_accounts = 0

for account_id, account_name in ACCOUNTS:
    try:
        url = f"{api_url}/api/data/files/{account_id}/agg_v1.json?tenant_id={TENANT_ID}"
        resp = requests.get(url, headers=headers, timeout=5)

        if resp.status_code == 200:
            data = resp.json()
            ads_count = len(data.get('ads', []))
            total_ads += ads_count

            if ads_count > 0:
                active_accounts += 1
                print(f"✅ {account_name:40s} {ads_count:4d} ads")
            else:
                inactive_accounts += 1
                print(f"⚠️  {account_name:40s}    0 ads (inactif)")
        else:
            print(f"❌ {account_name:40s} ERROR {resp.status_code}")

    except Exception as e:
        print(f"❌ {account_name:40s} ERROR: {e}")

print(f"\n{'='*60}")
print(f"📊 RÉSUMÉ GLOBAL:")
print(f"{'='*60}")
print(f"Total comptes testés:     {len(ACCOUNTS)}")
print(f"✅ Comptes actifs:        {active_accounts} ({active_accounts/len(ACCOUNTS)*100:.1f}%)")
print(f"⚠️  Comptes inactifs:      {inactive_accounts}")
print(f"🎨 Total ads récupérées:  {total_ads:,} ads")
print(f"📈 Moyenne par compte:     {total_ads/active_accounts:.1f} ads" if active_accounts > 0 else "N/A")
