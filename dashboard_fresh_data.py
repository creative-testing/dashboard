#!/usr/bin/env python3
"""
Crée le dashboard avec le bon format (comme dashboard_v2.html) et les données fraîches
"""
import json
from datetime import datetime
from collections import defaultdict

def create_dashboard():
    # Charger les données hybrides complètes
    with open('hybrid_data_20250826_101309.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    ads = data['ads']
    
    # Filtrer les annonces avec spend > 3000 MXN
    significant_ads = [ad for ad in ads if ad['spend'] > 3000]
    significant_ads.sort(key=lambda x: x['roas'], reverse=True)
    
    # Top 10 par ROAS
    top_10_ads = significant_ads[:10]
    
    # Stats globales
    total_spend = sum(ad['spend'] for ad in ads)
    total_impressions = sum(ad['impressions'] for ad in ads)
    avg_roas = sum(ad['roas'] for ad in significant_ads) / len(significant_ads) if significant_ads else 0
    
    # Stats par format
    format_stats = defaultdict(lambda: {'count': 0, 'spend': 0})
    for ad in ads:
        fmt = ad['format']
        format_stats[fmt]['count'] += 1
        format_stats[fmt]['spend'] += ad['spend']
    
    # Stats par compte pour le graphique en barres
    account_spend = defaultdict(float)
    for ad in ads:
        account_spend[ad['account_name']] += ad['spend']
    
    # Top 5 comptes par spend
    top_accounts = sorted(account_spend.items(), key=lambda x: x[1], reverse=True)[:5]
    max_spend = top_accounts[0][1] if top_accounts else 1
    
    # Couleurs pour les graphiques
    colors = {
        'VIDEO': '#0066cc',
        'IMAGE': '#00a854',
        'UNKNOWN': '#86868b'
    }
    
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Creative Testing Agent - Dashboard</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: #f5f5f7;
            color: #1d1d1f;
            min-height: 100vh;
        }}
        
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px 20px;
            text-align: center;
        }}
        
        .header h1 {{
            font-size: 36px;
            margin-bottom: 10px;
        }}
        
        .header p {{
            opacity: 0.9;
            font-size: 18px;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: -40px 20px 40px;
            position: relative;
        }}
        
        .kpi-card {{
            background: white;
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.07);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        
        .kpi-icon {{
            width: 48px;
            height: 48px;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
        }}
        
        .kpi-icon.blue {{ background: #e6f2ff; color: #0066cc; }}
        .kpi-icon.green {{ background: #e6f9e6; color: #00a854; }}
        .kpi-icon.purple {{ background: #f3e6ff; color: #7928ca; }}
        .kpi-icon.yellow {{ background: #fff4e6; color: #ff9500; }}
        
        .kpi-content h3 {{
            font-size: 28px;
            margin-bottom: 4px;
        }}
        
        .kpi-content p {{
            color: #86868b;
            font-size: 14px;
        }}
        
        .main-table-card {{
            background: white;
            border-radius: 12px;
            padding: 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.07);
            margin-bottom: 40px;
        }}
        
        .main-table-card h2 {{
            font-size: 24px;
            margin-bottom: 8px;
        }}
        
        .main-table-card p {{
            color: #86868b;
            margin-bottom: 24px;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        
        thead th {{
            background: #f5f5f7;
            padding: 12px;
            text-align: left;
            font-weight: 600;
            font-size: 14px;
            color: #1d1d1f;
            border-bottom: 2px solid #e0e0e2;
        }}
        
        tbody td {{
            padding: 16px 12px;
            border-bottom: 1px solid #f0f0f2;
            font-size: 14px;
        }}
        
        tbody tr:hover {{
            background: #fafafa;
        }}
        
        .ad-name {{
            font-weight: 500;
            color: #1d1d1f;
        }}
        
        .metric {{
            font-weight: 600;
        }}
        
        .roas-high {{ color: #00a854; }}
        .roas-medium {{ color: #ff9500; }}
        .roas-low {{ color: #ff3b30; }}
        
        .format-badge {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
        }}
        
        .format-video {{ background: #e6f2ff; color: #0066cc; }}
        .format-image {{ background: #e6f9e6; color: #00a854; }}
        .format-unknown {{ background: #f0f0f2; color: #86868b; }}
        
        .media-link {{
            text-decoration: none;
            font-size: 18px;
            opacity: 0.8;
            transition: opacity 0.2s;
        }}
        
        .media-link:hover {{
            opacity: 1;
        }}
        
        .chart-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 40px;
        }}
        
        @media (max-width: 768px) {{
            .chart-grid {{
                grid-template-columns: 1fr;
            }}
        }}
        
        .chart-card {{
            background: white;
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.07);
            height: 400px;
        }}
        
        .chart-card h3 {{
            font-size: 18px;
            margin-bottom: 20px;
        }}
        
        .chart-container {{
            position: relative;
            height: 320px;
        }}
        
        /* Graphiques CSS purs */
        .bar-chart {{
            display: flex;
            align-items: flex-end;
            justify-content: space-around;
            height: 200px;
            padding: 20px;
            position: relative;
        }}
        
        .bar {{
            flex: 1;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            margin: 0 8px;
            border-radius: 8px 8px 0 0;
            position: relative;
            min-height: 20px;
            transition: all 0.3s ease;
        }}
        
        .bar:hover {{
            transform: translateY(-5px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.3);
        }}
        
        .bar-value {{
            position: absolute;
            top: -25px;
            left: 50%;
            transform: translateX(-50%);
            font-weight: 600;
            font-size: 14px;
            white-space: nowrap;
        }}
        
        .bar-label {{
            position: absolute;
            bottom: -25px;
            left: 50%;
            transform: translateX(-50%);
            font-size: 12px;
            color: #86868b;
            white-space: nowrap;
        }}
        
        .donut-chart {{
            position: relative;
            padding: 20px;
        }}
        
        .donut-svg {{
            width: 180px;
            height: 180px;
            margin: 0 auto;
            display: block;
        }}
        
        .legend {{
            margin-top: 20px;
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 15px;
        }}
        
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .legend-color {{
            width: 16px;
            height: 16px;
            border-radius: 4px;
        }}
        
        /* Coming Soon section */
        .coming-soon {{
            background: white;
            border-radius: 12px;
            padding: 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.07);
            margin-top: 40px;
            border: 2px dashed #e0e0e2;
        }}
        
        .coming-soon h2 {{
            font-size: 24px;
            margin-bottom: 10px;
            color: #1d1d1f;
        }}
        
        .coming-soon > p {{
            color: #86868b;
            margin-bottom: 24px;
        }}
        
        .coming-soon-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
        }}
        
        .coming-soon-item {{
            padding: 20px;
            background: #f5f5f7;
            border-radius: 8px;
        }}
        
        .coming-soon-item h3 {{
            font-size: 16px;
            margin-bottom: 8px;
            color: #1d1d1f;
        }}
        
        .coming-soon-item p {{
            font-size: 14px;
            color: #86868b;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🚀 Creative Testing Dashboard</h1>
        <p>Análisis de rendimiento creativo • Actualizado: {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
    </div>
    
    <div class="container">
        <div class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-content">
                    <h3>{len(ads)}</h3>
                    <p>Anuncios Activos</p>
                </div>
                <div class="kpi-icon blue">📊</div>
            </div>
            
            <div class="kpi-card">
                <div class="kpi-content">
                    <h3>${total_spend:,.0f}</h3>
                    <p>Inversión Total (MXN)</p>
                </div>
                <div class="kpi-icon green">💰</div>
            </div>
            
            <div class="kpi-card">
                <div class="kpi-content">
                    <h3>{avg_roas:.2f}</h3>
                    <p>ROAS Promedio</p>
                </div>
                <div class="kpi-icon purple">📈</div>
            </div>
            
            <div class="kpi-card">
                <div class="kpi-content">
                    <h3>{total_impressions:,.0f}</h3>
                    <p>Impresiones Totales</p>
                </div>
                <div class="kpi-icon yellow">👁️</div>
            </div>
        </div>
        
        <div class="chart-grid">
            <div class="chart-card">
                <h3>💰 Top 5 Cuentas por Inversión</h3>
                <div class="bar-chart">"""
    
    # Ajouter les barres pour top 5 comptes
    for account_name, spend in top_accounts:
        height_pct = (spend / max_spend) * 100
        html += f"""
                    <div class="bar" style="height: {height_pct}%">
                        <span class="bar-value">${spend/1000:.0f}k</span>
                        <span class="bar-label">{account_name[:10]}</span>
                    </div>"""
    
    html += """
                </div>
            </div>
            
            <div class="chart-card">
                <h3>📊 Distribución por Formato</h3>
                <div class="donut-chart">
                    <svg class="donut-svg" viewBox="0 0 180 180">"""
    
    # Calculer les segments du donut
    total_count = sum(format_stats[fmt]['count'] for fmt in format_stats)
    offset = 0
    donut_colors = {'VIDEO': '#667eea', 'IMAGE': '#00a854', 'UNKNOWN': '#86868b'}
    
    for fmt in format_stats:
        count = format_stats[fmt]['count']
        percentage = (count / total_count * 377) if total_count > 0 else 0
        color = donut_colors.get(fmt, '#ccc')
        html += f"""
                        <circle cx="90" cy="90" r="60" fill="none" stroke="{color}" 
                                stroke-width="30" stroke-dasharray="{percentage:.0f} 377" 
                                stroke-dashoffset="-{offset:.0f}" transform="rotate(-90 90 90)"></circle>"""
        offset += percentage
    
    html += """
                        <circle cx="90" cy="90" r="30" fill="white"></circle>
                    </svg>
                    <div class="legend">"""
    
    for fmt in format_stats:
        color = donut_colors.get(fmt, '#ccc')
        count = format_stats[fmt]['count']
        html += f"""
                        <div class="legend-item">
                            <div class="legend-color" style="background: {color}"></div>
                            <span>{fmt} ({count})</span>
                        </div>"""
    
    html += """
                    </div>
                </div>
            </div>
        </div>
        
        <div class="main-table-card">
            <h2>Top 10 Anuncios por ROAS</h2>
            <p>Solo anuncios con inversión mayor a $3,000 MXN</p>
            
            <table>
                <thead>
                    <tr>
                        <th>Anuncio</th>
                        <th>Cuenta</th>
                        <th>Formato</th>
                        <th>ROAS</th>
                        <th>Inversión</th>
                        <th>CTR</th>
                        <th>Ver</th>
                    </tr>
                </thead>
                <tbody>"""
    
    for i, ad in enumerate(top_10_ads):
        roas_class = 'roas-high' if ad['roas'] > 3 else 'roas-medium' if ad['roas'] > 1.5 else 'roas-low'
        format_class = f"format-{ad['format'].lower()}"
        
        if ad.get('media_url'):
            if ad['format'] == 'VIDEO':
                media_link = f'<a href="{ad["media_url"]}" target="_blank" class="media-link">🎬</a>'
            else:
                media_link = f'<a href="{ad["media_url"]}" target="_blank" class="media-link">🖼️</a>'
        else:
            media_link = '—'
        
        html += f"""
                    <tr>
                        <td class="ad-name">{ad['ad_name'][:40]}...</td>
                        <td>{ad['account_name'][:25]}</td>
                        <td><span class="format-badge {format_class}">{ad['format']}</span></td>
                        <td class="metric {roas_class}">{ad['roas']:.2f}</td>
                        <td class="metric">${ad['spend']:,.0f}</td>
                        <td>{ad['ctr']:.2f}%</td>
                        <td>{media_link}</td>
                    </tr>"""
    
    html += """
                </tbody>
            </table>
        </div>
    
    <div class="container">
        <div class="coming-soon">
            <h2>🚧 Próximamente (después del renombrado)</h2>
            <p>Una vez que los anuncios sigan la nomenclatura estándar, podrás ver:</p>
            <div class="coming-soon-grid">
                <div class="coming-soon-item">
                    <h3>📊 Análisis por Ángulo</h3>
                    <p>Inflamación, Energía, Digestión, Proteína</p>
                </div>
                <div class="coming-soon-item">
                    <h3>👥 Análisis por Creador</h3>
                    <p>Carlos (25, M), Ana (30, F), etc.</p>
                </div>
                <div class="coming-soon-item">
                    <h3>📈 Tabla Completa</h3>
                    <p>Como en tu documento de especificación</p>
                </div>
                <div class="coming-soon-item">
                    <h3>📱 Export Automático</h3>
                    <p>Google Sheets actualizado semanalmente</p>
                </div>
            </div>
        </div>
    </div>
</body>
</html>"""
    
    # Guardar
    filename = "dashboard_fresh.html"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"✅ Dashboard creado: {filename}")
    print(f"📊 Resumen:")
    print(f"  • {len(ads)} anuncios totales")
    print(f"  • {len(significant_ads)} con spend > $3K MXN")
    print(f"  • ${total_spend:,.0f} MXN inversión total")
    print(f"  • ROAS promedio: {avg_roas:.2f}")
    
    return filename

if __name__ == "__main__":
    dashboard = create_dashboard()