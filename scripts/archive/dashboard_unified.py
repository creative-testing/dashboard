#!/usr/bin/env python3
"""
Dashboard UNIFIÉ avec sélecteur de période et preview fake
"""
import json
from datetime import datetime
from collections import defaultdict

def create_unified_dashboard():
    """Crée le dashboard unifié avec toutes les fonctionnalités"""
    
    # Précharger les données des 3 périodes
    periods_data = {}
    for days in [7, 30, 90]:
        try:
            with open(f'hybrid_data_{days}d.json', 'r', encoding='utf-8') as f:
                periods_data[days] = json.load(f)
        except FileNotFoundError:
            print(f"⚠️  Fichier hybrid_data_{days}d.json manquant")
    
    if not periods_data:
        print("❌ Aucune donnée disponible")
        return
    
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Creative Testing Dashboard - Análisis Completo</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
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
        
        .period-selector {{
            display: flex;
            justify-content: center;
            gap: 15px;
            margin: -20px 0 20px;
        }}
        
        .period-btn {{
            background: rgba(255,255,255,0.2);
            border: 2px solid rgba(255,255,255,0.3);
            color: white;
            padding: 12px 24px;
            border-radius: 25px;
            cursor: pointer;
            transition: all 0.3s ease;
            font-weight: 600;
        }}
        
        .period-btn.active, .period-btn:hover {{
            background: white;
            color: #667eea;
            border-color: white;
        }}
        
        .loading {{
            opacity: 0.5;
            pointer-events: none;
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
        
        /* Graphiques CSS */
        .chart-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 40px;
        }}
        
        .chart-card {{
            background: white;
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.07);
            height: 350px;
        }}
        
        .chart-card h3 {{
            font-size: 18px;
            margin-bottom: 20px;
        }}
        
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
        
        /* Table principale */
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
        .format-instagram {{ background: #f3e6ff; color: #7928ca; }}
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
        
        /* Section Preview Fake */
        .preview-section {{
            margin-bottom: 40px;
        }}
        
        .preview-card {{
            background: white;
            border-radius: 12px;
            padding: 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.07);
            position: relative;
            opacity: 0.7;
            border: 2px dashed #e0e0e2;
        }}
        
        .preview-badge {{
            position: absolute;
            top: 20px;
            right: 20px;
            background: #ff9500;
            color: white;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
        }}
        
        .preview-content {{
            filter: blur(1px);
            pointer-events: none;
        }}
        
        .unlock-message {{
            text-align: center;
            margin-top: 20px;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 8px;
        }}
        
        .unlock-btn {{
            background: #667eea;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 25px;
            font-weight: 600;
            cursor: pointer;
            margin-top: 10px;
        }}
        
        /* Coming Soon */
        .coming-soon {{
            background: white;
            border-radius: 12px;
            padding: 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.07);
            border: 2px dashed #e0e0e2;
        }}
        
        .coming-soon-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }}
        
        .coming-soon-item {{
            padding: 20px;
            background: #f5f5f7;
            border-radius: 8px;
        }}
        
        @media (max-width: 768px) {{
            .chart-grid {{
                grid-template-columns: 1fr;
            }}
            .kpi-grid {{
                grid-template-columns: 1fr;
            }}
            .period-selector {{
                flex-direction: column;
                align-items: center;
            }}
        }}
        
        .hidden {{
            display: none;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🚀 Creative Testing Dashboard</h1>
        <p>Análisis completo de rendimiento creativo</p>
        
        <div class="period-selector">
            <button class="period-btn active" onclick="switchPeriod(7)">7 días</button>
            <button class="period-btn" onclick="switchPeriod(30)">30 días</button>
            <button class="period-btn" onclick="switchPeriod(90)">90 días</button>
        </div>
    </div>
    
    <div class="container">
        <!-- KPIs dynamiques -->
        <div class="kpi-grid" id="kpi-grid">
            <!-- Sera rempli par JavaScript -->
        </div>
        
        <!-- Graphiques CSS -->
        <div class="chart-grid" id="chart-grid">
            <!-- Sera rempli par JavaScript -->
        </div>
        
        <!-- Table principale -->
        <div class="main-table-card">
            <h2 id="table-title">Top 10 Anuncios por ROAS</h2>
            <p id="table-subtitle">Solo anuncios con inversión mayor a $3,000 MXN</p>
            
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
                <tbody id="ads-table">
                    <!-- Sera rempli par JavaScript -->
                </tbody>
            </table>
        </div>
        
        <!-- Section Preview Fake -->
        <div class="preview-section">
            <div class="preview-card">
                <div class="preview-badge">PREVIEW</div>
                <h2>🔮 Análisis Avanzado</h2>
                
                <div class="preview-content">
                    <div class="chart-grid">
                        <div class="chart-card">
                            <h3>📊 Performance por Ángulo</h3>
                            <div class="bar-chart">
                                <div class="bar" style="height: 100%">
                                    <span class="bar-value">ROAS 4.2</span>
                                    <span class="bar-label">Inflamación</span>
                                </div>
                                <div class="bar" style="height: 75%">
                                    <span class="bar-value">ROAS 3.8</span>
                                    <span class="bar-label">Energía</span>
                                </div>
                                <div class="bar" style="height: 60%">
                                    <span class="bar-value">ROAS 3.1</span>
                                    <span class="bar-label">Digestión</span>
                                </div>
                                <div class="bar" style="height: 45%">
                                    <span class="bar-value">ROAS 2.7</span>
                                    <span class="bar-label">Proteína</span>
                                </div>
                            </div>
                        </div>
                        
                        <div class="chart-card">
                            <h3>👥 Performance por Creador</h3>
                            <div class="bar-chart">
                                <div class="bar" style="height: 90%">
                                    <span class="bar-value">ROAS 4.1</span>
                                    <span class="bar-label">Carlos 30M</span>
                                </div>
                                <div class="bar" style="height: 70%">
                                    <span class="bar-value">ROAS 3.5</span>
                                    <span class="bar-label">Ana 25F</span>
                                </div>
                                <div class="bar" style="height: 50%">
                                    <span class="bar-value">ROAS 2.9</span>
                                    <span class="bar-label">Luis 35M</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="unlock-message">
                    <h3>🔓 Desbloquear Análisis Completo</h3>
                    <p>Para ver el análisis por ángulo y creador, los anuncios deben seguir la nomenclatura estándar:</p>
                    <p><strong>FORMATO | ÁNGULO | HOOK | CREADOR | VERSION</strong></p>
                    <button class="unlock-btn" onclick="alert('Funcionalidad disponible después del renombrado automático')">
                        Aplicar Nomenclatura Automática
                    </button>
                </div>
            </div>
        </div>
        
        <!-- Coming Soon -->
        <div class="coming-soon">
            <h2>🚧 Próximamente</h2>
            <p>Funcionalidades que se activarán próximamente:</p>
            <div class="coming-soon-grid">
                <div class="coming-soon-item">
                    <h3>📱 Export Automático</h3>
                    <p>Google Sheets actualizado semanalmente</p>
                </div>
                <div class="coming-soon-item">
                    <h3>⚙️ Actualización Auto</h3>
                    <p>Dashboard actualizado cada lunes</p>
                </div>
                <div class="coming-soon-item">
                    <h3>📊 Más Métricas</h3>
                    <p>CPA, LTV, análisis de cohortes</p>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // Datos precargados
        const periodsData = """ + json.dumps(periods_data) + """;
        let currentPeriod = 7;
        
        function switchPeriod(days) {{
            currentPeriod = days;
            
            // Actualizar boutons
            document.querySelectorAll('.period-btn').forEach(btn => {{
                btn.classList.remove('active');
            }});
            event.target.classList.add('active');
            
            // Actualiser le contenu
            updateDashboard(days);
        }}
        
        function updateDashboard(days) {{
            const data = periodsData[days];
            if (!data) {{
                console.error(`No data for ${{days}} days`);
                return;
            }}
            
            updateKPIs(data);
            updateCharts(data);
            updateTable(data);
        }}
        
        function updateKPIs(data) {{
            const ads = data.ads;
            const totalSpend = ads.reduce((sum, ad) => sum + ad.spend, 0);
            const totalImpressions = ads.reduce((sum, ad) => sum + ad.impressions, 0);
            const significantAds = ads.filter(ad => ad.spend > 3000);
            const avgRoas = significantAds.length > 0 ? 
                significantAds.reduce((sum, ad) => sum + ad.roas, 0) / significantAds.length : 0;
            
            const kpiGrid = document.getElementById('kpi-grid');
            kpiGrid.innerHTML = `
                <div class="kpi-card">
                    <div class="kpi-content">
                        <h3>${{ads.length.toLocaleString()}}</h3>
                        <p>Anuncios Activos</p>
                    </div>
                    <div class="kpi-icon blue">📊</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-content">
                        <h3>$$${{totalSpend.toLocaleString(undefined, {{maximumFractionDigits: 0}})}}</h3>
                        <p>Inversión Total (MXN)</p>
                    </div>
                    <div class="kpi-icon green">💰</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-content">
                        <h3>${{avgRoas.toFixed(2)}}</h3>
                        <p>ROAS Promedio</p>
                    </div>
                    <div class="kpi-icon purple">📈</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-content">
                        <h3>${{totalImpressions.toLocaleString()}}</h3>
                        <p>Impresiones Totales</p>
                    </div>
                    <div class="kpi-icon yellow">👁️</div>
                </div>
            `;
        }}
        
        function updateCharts(data) {{
            const ads = data.ads;
            
            // Top 5 comptes par spend
            const accountSpend = {{}};
            ads.forEach(ad => {{
                if (!accountSpend[ad.account_name]) accountSpend[ad.account_name] = 0;
                accountSpend[ad.account_name] += ad.spend;
            }});
            
            const topAccounts = Object.entries(accountSpend)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 5);
            
            const maxSpend = topAccounts[0] ? topAccounts[0][1] : 1;
            
            // Formats distribution  
            const formatStats = data.format_distribution || {{}};
            const totalAds = Object.values(formatStats).reduce((sum, count) => sum + count, 0);
            
            const chartGrid = document.getElementById('chart-grid');
            chartGrid.innerHTML = `
                <div class="chart-card">
                    <h3>💰 Top 5 Cuentas por Inversión</h3>
                    <div class="bar-chart">
                        ${{topAccounts.map(([name, spend]) => `
                            <div class="bar" style="height: ${{(spend/maxSpend*100)}}%">
                                <span class="bar-value">$$$${{Math.round(spend/1000)}}k</span>
                                <span class="bar-label">${{name.substring(0, 10)}}</span>
                            </div>
                        `).join('')}}
                    </div>
                </div>
                <div class="chart-card">
                    <h3>📊 Distribución por Formato</h3>
                    <div class="legend">
                        ${{Object.entries(formatStats).map(([fmt, count]) => `
                            <div class="legend-item">
                                <div class="legend-color" style="background: ${{getFormatColor(fmt)}}"></div>
                                <span>${{fmt}} (${{count}})</span>
                            </div>
                        `).join('')}}
                    </div>
                </div>
            `;
        }}
        
        function getFormatColor(format) {{
            const colors = {{
                'VIDEO': '#667eea',
                'IMAGE': '#00a854', 
                'INSTAGRAM': '#7928ca',
                'UNKNOWN': '#86868b',
                'CAROUSEL': '#ff9500'
            }};
            return colors[format] || '#ccc';
        }}
        
        function updateTable(data) {{
            const ads = data.ads;
            const significantAds = ads.filter(ad => ad.spend > 3000);
            significantAds.sort((a, b) => b.roas - a.roas);
            const topAds = significantAds.slice(0, 10);
            
            const tableTitle = document.getElementById('table-title');
            const tableSubtitle = document.getElementById('table-subtitle');
            
            tableTitle.textContent = `Top 10 Anuncios por ROAS (${{currentPeriod}} días)`;
            tableSubtitle.textContent = `${{topAds.length}} de ${{ads.length}} anuncios con inversión > $3,000 MXN`;
            
            const tableBody = document.getElementById('ads-table');
            tableBody.innerHTML = topAds.map(ad => {{
                const roasClass = ad.roas > 3 ? 'roas-high' : ad.roas > 1.5 ? 'roas-medium' : 'roas-low';
                const formatClass = `format-${{ad.format.toLowerCase()}}`;
                
                let mediaLink = '—';
                if (ad.media_url) {{
                    const icon = ad.format === 'VIDEO' ? '🎬' : '🖼️';
                    mediaLink = `<a href="${{ad.media_url}}" target="_blank" class="media-link">${{icon}}</a>`;
                }}
                
                return `
                    <tr>
                        <td class="ad-name">${{ad.ad_name.substring(0, 40)}}...</td>
                        <td>${{ad.account_name.substring(0, 25)}}</td>
                        <td><span class="format-badge ${{formatClass}}">${{ad.format}}</span></td>
                        <td class="metric ${{roasClass}}">${{ad.roas.toFixed(2)}}</td>
                        <td class="metric">$$$${{ad.spend.toLocaleString(undefined, {{maximumFractionDigits: 0}})}}</td>
                        <td>${{ad.ctr.toFixed(2)}}%</td>
                        <td>${{mediaLink}}</td>
                    </tr>
                `;
            }}).join('');
        }}
        
        // Initialiser avec 7 jours
        document.addEventListener('DOMContentLoaded', () => {{
            updateDashboard(7);
        }});
    </script>
</body>
</html>"""
    
    # Sauvegarder
    filename = "dashboard_unified.html"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"✅ Dashboard unifié créé: {filename}")
    print(f"📊 Périodes disponibles: {list(periods_data.keys())} jours")
    
    return filename

if __name__ == "__main__":
    print("🚀 Création du Dashboard Unifié")
    print("• Sélecteur de période 7/30/90 jours")
    print("• Section réelle + preview fake") 
    print("• Graphiques CSS + données dynamiques")
    print()
    
    dashboard_file = create_unified_dashboard()
    if dashboard_file:
        print(f"\n🎯 Ouvrir: {dashboard_file}")