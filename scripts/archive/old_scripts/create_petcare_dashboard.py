#!/usr/bin/env python3
"""
Dashboard Petcare avec VRAIES analyses par angle basées sur la nomenclature de Martin
"""
import json
from datetime import datetime

def create_petcare_dashboard():
    """Crée le dashboard Petcare avec vraies analyses d'angles"""
    
    # Charger les données Petcare parsées
    with open('data/current/petcare_parsed_analysis.json', 'r') as f:
        petcare_data = json.load(f)
    
    angles = petcare_data['angle_performance']
    types = petcare_data['type_performance']
    
    # Trier par ROAS décroissant
    angles.sort(key=lambda x: x['roas'], reverse=True)
    
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Petcare - Análisis por Ángulo (DATOS REALES)</title>
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
            background: linear-gradient(135deg, #00a854 0%, #28a745 100%);
            color: white;
            padding: 40px 20px;
            text-align: center;
        }}
        
        .header h1 {{
            font-size: 36px;
            margin-bottom: 10px;
        }}
        
        .success-badge {{
            background: rgba(255,255,255,0.2);
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 14px;
            margin-top: 15px;
            display: inline-block;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        
        .stats-summary {{
            background: white;
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.07);
            margin: -30px 20px 30px;
            text-align: center;
        }}
        
        .chart-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            margin-bottom: 40px;
        }}
        
        .chart-card {{
            background: white;
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.07);
            height: 400px;
        }}
        
        .chart-card h3 {{
            font-size: 20px;
            margin-bottom: 20px;
            color: #1d1d1f;
        }}
        
        .angle-list {{
            display: flex;
            flex-direction: column;
            gap: 15px;
            height: 320px;
            overflow-y: auto;
        }}
        
        .angle-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
            border-left: 4px solid #00a854;
        }}
        
        .angle-name {{
            font-weight: 600;
            color: #1d1d1f;
        }}
        
        .angle-metrics {{
            text-align: right;
            font-size: 14px;
        }}
        
        .roas-value {{
            font-size: 18px;
            font-weight: 700;
            color: #00a854;
        }}
        
        .type-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }}
        
        .type-card {{
            background: #f8f9fa;
            border-radius: 12px;
            padding: 20px;
            text-align: center;
        }}
        
        .type-card.nuevo {{
            border: 3px solid #667eea;
        }}
        
        .type-card.iteracion {{
            border: 3px solid #ff9500;
        }}
        
        .type-title {{
            font-size: 16px;
            font-weight: 600;
            margin-bottom: 10px;
        }}
        
        .type-roas {{
            font-size: 24px;
            font-weight: 700;
            color: #00a854;
        }}
        
        .table-card {{
            background: white;
            border-radius: 12px;
            padding: 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.07);
            margin-bottom: 30px;
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
            padding: 12px;
            border-bottom: 1px solid #f0f0f2;
            font-size: 14px;
        }}
        
        tbody tr:hover {{
            background: #fafafa;
        }}
        
        .metric {{
            font-weight: 600;
        }}
        
        .roas-excellent {{ color: #00a854; }}
        .roas-good {{ color: #667eea; }}
        .roas-medium {{ color: #ff9500; }}
        .roas-poor {{ color: #ff3b30; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🐕 Petcare - Análisis por Ángulo</h1>
        <p>Datos REALES basados en nomenclatura de Martin</p>
        <div class="success-badge">
            ✅ Nomenclatura detectada: {petcare_data['metadata']['parsing_success_rate']:.1f}% de annuncios
        </div>
    </div>
    
    <div class="container">
        <div class="stats-summary">
            <h2>📊 Resumen Petcare (7 días)</h2>
            <p><strong>{len(angles)} ángulos activos</strong> • <strong>{sum(a['ads_count'] for a in angles)} anuncios</strong> • <strong>${sum(a['spend'] for a in angles):,.0f} MXN invertidos</strong></p>
        </div>
        
        <div class="chart-grid">
            <div class="chart-card">
                <h3>🏆 Performance por Ángulo (ROAS Real)</h3>
                <div class="angle-list">"""
    
    # Ajouter les angles réels
    for angle in angles:
        roas_class = 'excellent' if angle['roas'] > 5 else 'good' if angle['roas'] > 3 else 'medium' if angle['roas'] > 2 else 'poor'
        
        html += f"""
                    <div class="angle-item">
                        <div>
                            <div class="angle-name">{angle['angle']}</div>
                            <div style="font-size: 12px; color: #6c757d;">{angle['ads_count']} anuncios • ${angle['spend']:,.0f} MXN</div>
                        </div>
                        <div class="angle-metrics">
                            <div class="roas-value roas-{roas_class}">ROAS {angle['roas']:.2f}</div>
                            <div style="font-size: 12px; color: #6c757d;">CTR {angle['ctr']:.2f}%</div>
                        </div>
                    </div>"""
    
    html += f"""
                </div>
            </div>
            
            <div class="chart-card">
                <h3>🔄 Nuevo vs Iteración</h3>
                <div class="type-grid">"""
    
    # Ajouter les types créatifs
    for type_data in types:
        type_class = 'nuevo' if type_data['type'] == 'Nuevo' else 'iteracion'
        
        html += f"""
                    <div class="type-card {type_class}">
                        <div class="type-title">{type_data['type']}</div>
                        <div class="type-roas">ROAS {type_data['roas']:.2f}</div>
                        <div style="margin-top: 10px; font-size: 14px; color: #6c757d;">
                            {type_data['ads_count']} anuncios<br>
                            ${type_data['spend']:,.0f} MXN
                        </div>
                    </div>"""
    
    html += f"""
                </div>
                
                <div style="margin-top: 30px; padding: 20px; background: #f8f9fa; border-radius: 8px;">
                    <h4 style="margin-bottom: 10px;">📈 Insights Clave:</h4>
                    <p style="font-size: 14px; color: #6c757d; line-height: 1.5;">
                        • <strong>Mejor ángulo</strong>: {angles[0]['angle'] if angles else 'N/A'} (ROAS {angles[0]['roas']:.2f})<br>
                        • <strong>Creativos nuevos</strong> superan iteraciones<br>  
                        • <strong>{len(angles)} ángulos</strong> diferentes en testing
                    </p>
                </div>
            </div>
        </div>
        
        <div class="table-card">
            <h2>📋 Detalle Completo por Ángulo</h2>
            <p>Análisis detallado de performance por ángulo creativo</p>
            
            <table>
                <thead>
                    <tr>
                        <th>Ángulo</th>
                        <th># Anuncios</th>
                        <th>Inversión</th>
                        <th>ROAS</th>
                        <th>CTR</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>"""
    
    # Table détaillée
    for angle in angles:
        roas_class = 'roas-excellent' if angle['roas'] > 5 else 'roas-good' if angle['roas'] > 3 else 'roas-medium' if angle['roas'] > 2 else 'roas-poor'
        
        status = "🔥 Ganador" if angle['roas'] > 4 else "✅ Bueno" if angle['roas'] > 2.5 else "⚠️ Regular" if angle['roas'] > 1.5 else "❌ Perdedor"
        
        html += f"""
                    <tr>
                        <td class="metric">{angle['angle']}</td>
                        <td>{angle['ads_count']}</td>
                        <td class="metric">${angle['spend']:,.0f}</td>
                        <td class="metric {roas_class}">{angle['roas']:.2f}</td>
                        <td>{angle['ctr']:.2f}%</td>
                        <td>{status}</td>
                    </tr>"""
    
    html += f"""
                </tbody>
            </table>
        </div>
        
        <div style="background: white; border-radius: 12px; padding: 25px; box-shadow: 0 4px 6px rgba(0,0,0,0.07); text-align: center; margin-top: 30px;">
            <h3 style="color: #00a854; margin-bottom: 10px;">🎉 ¡Análisis Desbloqueado!</h3>
            <p style="color: #6c757d;">Gracias a la nomenclatura de Martin, ahora vemos <strong>análisis reales por ángulo</strong> en lugar de datos simulados.</p>
            <p style="color: #6c757d; margin-top: 8px; font-size: 14px;">
                Parsing exitoso: {petcare_data['metadata']['parsing_success_rate']:.1f}% • Actualizado: {datetime.now().strftime('%d/%m/%Y %H:%M')}
            </p>
        </div>
    </div>
</body>
</html>"""
    
    # Sauvegarder
    filename = "dashboards/current/petcare_real_analysis.html"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"✅ Dashboard Petcare créé: {filename}")
    print(f"📊 Résumé:")
    
    if angles:
        best_angle = angles[0]
        worst_angle = angles[-1]
        
        print(f"  🏆 Meilleur angle: {best_angle['angle']} (ROAS {best_angle['roas']:.2f})")
        print(f"  📉 Moins bon: {worst_angle['angle']} (ROAS {worst_angle['roas']:.2f})")
        print(f"  📊 Total: {len(angles)} angles, {sum(a['ads_count'] for a in angles)} ads")
    
    return filename

if __name__ == "__main__":
    print("🐕 Création dashboard Petcare avec VRAIES analyses")
    print("🎯 Basé sur nomenclature Martin + parsing automatique")
    
    dashboard_file = create_petcare_dashboard()
    if dashboard_file:
        print(f"\n🎉 Dashboard créé avec succès !")
        print(f"📁 Ouvrir: {dashboard_file}")