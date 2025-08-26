#!/usr/bin/env python3
"""
Crée le dashboard HTML avec les données réelles fetched
"""
import json
from datetime import datetime
from collections import defaultdict

def create_dashboard():
    # Charger les données
    with open('real_formats_data_20250825_202841.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    ads = data['ads']
    
    # Filtrer les annonces avec spend > 3000 MXN
    significant_ads = [ad for ad in ads if ad['spend'] > 3000]
    
    # Trier par ROAS décroissant
    significant_ads.sort(key=lambda x: x['roas'], reverse=True)
    
    # Top 10 par ROAS
    top_10_ads = significant_ads[:10]
    
    # Statistiques par format
    format_stats = defaultdict(lambda: {'count': 0, 'spend': 0, 'roas_sum': 0})
    for ad in significant_ads:
        fmt = ad['format']
        format_stats[fmt]['count'] += 1
        format_stats[fmt]['spend'] += ad['spend']
        format_stats[fmt]['roas_sum'] += ad['roas']
    
    # Calculer ROAS moyen par format
    for fmt in format_stats:
        count = format_stats[fmt]['count']
        if count > 0:
            format_stats[fmt]['avg_roas'] = format_stats[fmt]['roas_sum'] / count
    
    # Générer le HTML
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard Creativo - Datos Reales {datetime.now().strftime('%d/%m/%Y')}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        
        .header {{
            text-align: center;
            color: white;
            margin-bottom: 30px;
        }}
        
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }}
        
        .header .subtitle {{
            font-size: 1.2em;
            opacity: 0.95;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        
        .stat-card {{
            background: white;
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }}
        
        .stat-card .label {{
            font-size: 0.9em;
            color: #666;
            margin-bottom: 5px;
        }}
        
        .stat-card .value {{
            font-size: 2em;
            font-weight: bold;
            color: #333;
        }}
        
        .stat-card .detail {{
            font-size: 0.85em;
            color: #999;
            margin-top: 5px;
        }}
        
        .main-table-card {{
            background: white;
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }}
        
        .main-table-card h2 {{
            color: #333;
            margin-bottom: 20px;
            font-size: 1.8em;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        
        th {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }}
        
        td {{
            padding: 12px;
            border-bottom: 1px solid #eee;
        }}
        
        tr:hover {{
            background: #f8f8f8;
        }}
        
        .roas-high {{ color: #22c55e; font-weight: bold; }}
        .roas-medium {{ color: #eab308; font-weight: bold; }}
        .roas-low {{ color: #ef4444; font-weight: bold; }}
        
        .format-video {{ 
            background: #3b82f6; 
            color: white; 
            padding: 3px 8px; 
            border-radius: 4px; 
            font-size: 0.85em;
        }}
        .format-image {{ 
            background: #10b981; 
            color: white; 
            padding: 3px 8px; 
            border-radius: 4px; 
            font-size: 0.85em;
        }}
        .format-unknown {{ 
            background: #6b7280; 
            color: white; 
            padding: 3px 8px; 
            border-radius: 4px; 
            font-size: 0.85em;
        }}
        
        .media-link {{
            text-decoration: none;
            font-size: 1.2em;
        }}
        
        .chart-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 30px;
        }}
        
        .chart-card {{
            background: white;
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            height: 350px;
            position: relative;
        }}
        
        .chart-card h3 {{
            color: #333;
            margin-bottom: 15px;
        }}
        
        .chart-container {{
            position: relative;
            height: 280px;
        }}
        
        @media (max-width: 768px) {{
            .chart-grid {{
                grid-template-columns: 1fr;
            }}
            .stats-grid {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Dashboard de Creative Testing</h1>
            <div class="subtitle">Datos actualizados: {datetime.now().strftime('%d/%m/%Y %H:%M')} | {len(significant_ads)} anuncios con spend > $3,000 MXN</div>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="label">Total Anuncios</div>
                <div class="value">{len(ads)}</div>
                <div class="detail">Últimos 7 días</div>
            </div>
            <div class="stat-card">
                <div class="label">Inversión Total</div>
                <div class="value">${sum(ad['spend'] for ad in ads):,.0f}</div>
                <div class="detail">MXN</div>
            </div>
            <div class="stat-card">
                <div class="label">ROAS Promedio</div>
                <div class="value">{sum(ad['roas'] for ad in significant_ads)/len(significant_ads) if significant_ads else 0:.2f}</div>
                <div class="detail">Solo anuncios > $3K</div>
            </div>
            <div class="stat-card">
                <div class="label">Mejor ROAS</div>
                <div class="value">{max(ad['roas'] for ad in significant_ads) if significant_ads else 0:.2f}</div>
                <div class="detail">{top_10_ads[0]['ad_name'][:20] if top_10_ads else 'N/A'}...</div>
            </div>
        </div>
        
        <div class="chart-grid">
            <div class="chart-card">
                <h3>📊 Distribución por Formato</h3>
                <div class="chart-container">
                    <canvas id="formatChart"></canvas>
                </div>
            </div>
            <div class="chart-card">
                <h3>💰 ROAS Promedio por Formato</h3>
                <div class="chart-container">
                    <canvas id="roasChart"></canvas>
                </div>
            </div>
        </div>
        
        <div class="main-table-card">
            <h2>🏆 Top 10 Anuncios por ROAS (Solo con spend > $3,000 MXN)</h2>
            <table>
                <thead>
                    <tr>
                        <th>Nombre</th>
                        <th>Cuenta</th>
                        <th>Formato</th>
                        <th>ROAS</th>
                        <th>Spend</th>
                        <th>CTR</th>
                        <th>CPM</th>
                        <th>Ver</th>
                    </tr>
                </thead>
                <tbody>"""
    
    # Agregar las filas de la tabla
    for ad in top_10_ads:
        roas_class = 'roas-high' if ad['roas'] > 3 else 'roas-medium' if ad['roas'] > 1.5 else 'roas-low'
        format_class = f"format-{ad['format'].lower()}"
        
        # Icono para el link
        if ad['media_url']:
            if ad['format'] == 'VIDEO':
                link_icon = '🎬'
            else:
                link_icon = '🖼️'
            media_link = f'<a href="{ad["media_url"]}" target="_blank" class="media-link" title="Ver creativo">{link_icon}</a>'
        else:
            media_link = '—'
        
        html += f"""
                    <tr>
                        <td>{ad['ad_name'][:50]}...</td>
                        <td>{ad['account_name'][:30]}</td>
                        <td><span class="{format_class}">{ad['format']}</span></td>
                        <td class="{roas_class}">{ad['roas']:.2f}</td>
                        <td>${ad['spend']:,.0f}</td>
                        <td>{ad['ctr']:.2f}%</td>
                        <td>${ad['cpm']:.0f}</td>
                        <td>{media_link}</td>
                    </tr>"""
    
    html += """
                </tbody>
            </table>
        </div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script>
        // Gráfico de distribución por formato
        const formatCtx = document.getElementById('formatChart').getContext('2d');
        new Chart(formatCtx, {
            type: 'doughnut',
            data: {
                labels: """ + json.dumps(list(format_stats.keys())) + """,
                datasets: [{
                    data: """ + json.dumps([format_stats[fmt]['count'] for fmt in format_stats]) + """,
                    backgroundColor: ['#3b82f6', '#10b981', '#6b7280']
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
        
        // Gráfico de ROAS por formato
        const roasCtx = document.getElementById('roasChart').getContext('2d');
        new Chart(roasCtx, {
            type: 'bar',
            data: {
                labels: """ + json.dumps(list(format_stats.keys())) + """,
                datasets: [{
                    label: 'ROAS Promedio',
                    data: """ + json.dumps([format_stats[fmt]['avg_roas'] for fmt in format_stats]) + """,
                    backgroundColor: 'rgba(102, 126, 234, 0.8)'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
    </script>
</body>
</html>"""
    
    # Guardar el archivo
    filename = f"dashboard_real_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"✅ Dashboard creado: {filename}")
    print(f"📊 Resumen:")
    print(f"  • Total anuncios: {len(ads)}")
    print(f"  • Anuncios significativos (>$3K): {len(significant_ads)}")
    print(f"  • Inversión total: ${sum(ad['spend'] for ad in ads):,.0f} MXN")
    print(f"  • ROAS promedio: {sum(ad['roas'] for ad in significant_ads)/len(significant_ads) if significant_ads else 0:.2f}")
    
    return filename

if __name__ == "__main__":
    dashboard_file = create_dashboard()
    print(f"\n🎯 Abre el archivo: {dashboard_file}")