#!/usr/bin/env python3
"""
Weekly Pulse - SaaS Activity Report
====================================
Envoie un email hebdomadaire aux fondateurs avec les stats des deux SaaS:
- Agente Creativo (Supabase)
- Creative Testing (PostgreSQL VPS)

Usage:
    python weekly_pulse.py              # Envoie l'email
    python weekly_pulse.py --dry-run    # Affiche le rapport sans envoyer
    python weekly_pulse.py --slack      # Envoie sur Slack au lieu d'email

Cron (lundi 8h):
    0 8 * * 1 /usr/bin/python3 /root/scripts/weekly_pulse.py >> /var/log/weekly_pulse.log 2>&1
"""

import os
import sys
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Dict, List, Any

# --- CONFIGURATION ---
# Agente Creativo (Supabase)
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

# Creative Testing (PostgreSQL - même DB que l'API)
CT_DATABASE_URL = os.getenv("DATABASE_URL", "")

# Email Config
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
EMAIL_RECIPIENTS = os.getenv("EMAIL_RECIPIENTS", "").split(",")

# Slack Config (alternative)
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")

# Période d'analyse
DAYS_LOOKBACK = 7


def get_agente_stats() -> Dict[str, Any]:
    """
    Récupère les stats d'Agente Creativo via l'API Supabase.

    Tables utilisées:
    - profiles: utilisateurs (email, full_name)
    - analyses: analyses lancées (owner_id, status, created_at, company_name)
    """
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        return {"error": "Supabase non configuré", "total_users": 0, "analyses_7d": 0, "active_users": []}

    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json"
    }

    start_date = (datetime.now() - timedelta(days=DAYS_LOOKBACK)).isoformat()

    try:
        # 1. Total utilisateurs
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/profiles?select=count",
            headers={**headers, "Prefer": "count=exact"},
        )
        total_users = int(resp.headers.get("content-range", "0-0/0").split("/")[1])

        # 2. Analyses des 7 derniers jours
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/analyses?select=id,owner_id,status,company_name,created_at&created_at=gte.{start_date}&order=created_at.desc",
            headers=headers
        )
        analyses = resp.json() if resp.status_code == 200 else []

        # 3. Récupérer les emails des utilisateurs actifs
        active_owner_ids = list(set(a["owner_id"] for a in analyses if a.get("owner_id")))
        active_users = []

        if active_owner_ids:
            # Récupérer les profils
            ids_filter = ",".join(f'"{uid}"' for uid in active_owner_ids)
            resp = requests.get(
                f"{SUPABASE_URL}/rest/v1/profiles?select=id,email,full_name&id=in.({ids_filter})",
                headers=headers
            )
            if resp.status_code == 200:
                profiles = {p["id"]: p for p in resp.json()}

                # Compter analyses par utilisateur
                user_counts = {}
                for a in analyses:
                    uid = a.get("owner_id")
                    if uid:
                        user_counts[uid] = user_counts.get(uid, 0) + 1

                for uid, count in sorted(user_counts.items(), key=lambda x: -x[1]):
                    profile = profiles.get(uid, {})
                    active_users.append({
                        "email": profile.get("email", "?"),
                        "name": profile.get("full_name", ""),
                        "analyses_count": count
                    })

        # Stats par statut
        status_counts = {}
        for a in analyses:
            status = a.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "total_users": total_users,
            "analyses_7d": len(analyses),
            "analyses_completed": status_counts.get("completed", 0),
            "analyses_failed": status_counts.get("failed", 0),
            "active_users": active_users
        }

    except Exception as e:
        return {"error": str(e), "total_users": 0, "analyses_7d": 0, "active_users": []}


def get_ct_stats() -> Dict[str, Any]:
    """
    Récupère les stats de Creative Testing via SQL direct.

    Tables utilisées:
    - tenants: organisations (name)
    - users: utilisateurs (email, tenant_id)
    - refresh_jobs: jobs de refresh (tenant_id, status, created_at)
    - ad_accounts: comptes publicitaires connectés
    """
    if not CT_DATABASE_URL:
        return {"error": "DATABASE_URL non configuré", "total_tenants": 0, "refreshes_7d": 0, "active_tenants": []}

    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(CT_DATABASE_URL)

        with engine.connect() as conn:
            # 1. Total tenants
            result = conn.execute(text("SELECT COUNT(*) FROM tenants"))
            total_tenants = result.scalar()

            # 2. Total comptes connectés
            result = conn.execute(text("SELECT COUNT(*) FROM ad_accounts WHERE is_disabled = false"))
            total_accounts = result.scalar()

            # 3. Refreshes OK des 7 derniers jours (status = 'OK' en majuscule)
            result = conn.execute(text("""
                SELECT COUNT(*) FROM refresh_jobs
                WHERE UPPER(status::text) = 'OK'
                AND created_at > NOW() - INTERVAL '7 days'
            """))
            refreshes_ok = result.scalar()

            # 4. Refreshes failed des 7 derniers jours (status = 'ERROR')
            result = conn.execute(text("""
                SELECT COUNT(*) FROM refresh_jobs
                WHERE UPPER(status::text) = 'ERROR'
                AND created_at > NOW() - INTERVAL '7 days'
            """))
            refreshes_failed = result.scalar()

            # 5. Tenants actifs (avec refresh OK cette semaine)
            result = conn.execute(text("""
                SELECT DISTINCT t.name, COUNT(r.id) as refresh_count
                FROM refresh_jobs r
                JOIN tenants t ON r.tenant_id = t.id
                WHERE UPPER(r.status::text) = 'OK'
                AND r.created_at > NOW() - INTERVAL '7 days'
                GROUP BY t.name
                ORDER BY refresh_count DESC
            """))
            active_tenants = [{"name": row[0], "refresh_count": row[1]} for row in result.fetchall()]

        return {
            "total_tenants": total_tenants,
            "total_accounts": total_accounts,
            "refreshes_ok_7d": refreshes_ok,
            "refreshes_failed_7d": refreshes_failed,
            "active_tenants": active_tenants
        }

    except Exception as e:
        return {"error": str(e), "total_tenants": 0, "refreshes_7d": 0, "active_tenants": []}


def generate_html_report(agente: Dict, ct: Dict) -> str:
    """Génère le rapport HTML."""

    date_str = datetime.now().strftime("%d/%m/%Y")

    # Section Agente Creativo
    agente_users_html = ""
    if agente.get("active_users"):
        for u in agente["active_users"]:
            name = f" ({u['name']})" if u.get("name") else ""
            agente_users_html += f"<li>✅ {u['email']}{name} — {u['analyses_count']} analyses</li>"
    else:
        agente_users_html = "<li><em>Aucun utilisateur actif cette semaine</em></li>"

    # Section Creative Testing
    ct_tenants_html = ""
    if ct.get("active_tenants"):
        for t in ct["active_tenants"]:
            ct_tenants_html += f"<li>✅ {t['name']} — {t['refresh_count']} refreshes</li>"
    else:
        ct_tenants_html = "<li><em>Aucun tenant actif cette semaine</em></li>"

    html = f"""
    <html>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h1 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px;">
            📊 Weekly Pulse — {date_str}
        </h1>

        <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
            <h2 style="color: #e74c3c; margin-top: 0;">🤖 Agente Creativo</h2>

            <table style="width: 100%; margin-bottom: 15px;">
                <tr>
                    <td style="padding: 8px; background: #fff; border-radius: 4px; text-align: center;">
                        <div style="font-size: 24px; font-weight: bold; color: #3498db;">{agente.get('total_users', 0)}</div>
                        <div style="font-size: 12px; color: #7f8c8d;">Usuarios totales</div>
                    </td>
                    <td style="padding: 8px; background: #fff; border-radius: 4px; text-align: center;">
                        <div style="font-size: 24px; font-weight: bold; color: #27ae60;">{agente.get('analyses_7d', 0)}</div>
                        <div style="font-size: 12px; color: #7f8c8d;">Análisis (7d)</div>
                    </td>
                    <td style="padding: 8px; background: #fff; border-radius: 4px; text-align: center;">
                        <div style="font-size: 24px; font-weight: bold; color: #9b59b6;">{len(agente.get('active_users', []))}</div>
                        <div style="font-size: 12px; color: #7f8c8d;">Activos (7d)</div>
                    </td>
                </tr>
            </table>

            <p style="margin-bottom: 5px;"><strong>Usuarios activos esta semana:</strong></p>
            <ul style="margin: 0; padding-left: 20px;">
                {agente_users_html}
            </ul>

            {f'<p style="color: #e74c3c; font-size: 12px; margin-top: 10px;">⚠️ {agente.get("analyses_failed", 0)} análisis fallidos</p>' if agente.get("analyses_failed", 0) > 0 else ''}
        </div>

        <div style="background: #f8f9fa; padding: 20px; border-radius: 8px;">
            <h2 style="color: #9b59b6; margin-top: 0;">🧪 Creative Testing</h2>

            <table style="width: 100%; margin-bottom: 15px;">
                <tr>
                    <td style="padding: 8px; background: #fff; border-radius: 4px; text-align: center;">
                        <div style="font-size: 24px; font-weight: bold; color: #3498db;">{ct.get('total_tenants', 0)}</div>
                        <div style="font-size: 12px; color: #7f8c8d;">Tenants totales</div>
                    </td>
                    <td style="padding: 8px; background: #fff; border-radius: 4px; text-align: center;">
                        <div style="font-size: 24px; font-weight: bold; color: #27ae60;">{ct.get('total_accounts', 0)}</div>
                        <div style="font-size: 12px; color: #7f8c8d;">Cuentas Meta</div>
                    </td>
                    <td style="padding: 8px; background: #fff; border-radius: 4px; text-align: center;">
                        <div style="font-size: 24px; font-weight: bold; color: #9b59b6;">{ct.get('refreshes_ok_7d', 0)}</div>
                        <div style="font-size: 12px; color: #7f8c8d;">Refreshes (7d)</div>
                    </td>
                </tr>
            </table>

            <p style="margin-bottom: 5px;"><strong>Tenants activos esta semana:</strong></p>
            <ul style="margin: 0; padding-left: 20px;">
                {ct_tenants_html}
            </ul>

            {f'<p style="color: #e74c3c; font-size: 12px; margin-top: 10px;">⚠️ {ct.get("refreshes_failed_7d", 0)} refreshes fallidos</p>' if ct.get("refreshes_failed_7d", 0) > 0 else ''}
        </div>

        <p style="color: #95a5a6; font-size: 11px; margin-top: 20px; text-align: center;">
            Generado automáticamente — {datetime.now().strftime("%Y-%m-%d %H:%M")}
        </p>
    </body>
    </html>
    """

    return html


def generate_slack_message(agente: Dict, ct: Dict) -> str:
    """Génère le message Slack (format Markdown)."""

    date_str = datetime.now().strftime("%d/%m/%Y")

    # Active users list
    agente_users = "\n".join([
        f"  • {u['email']} — {u['analyses_count']} análisis"
        for u in agente.get("active_users", [])
    ]) or "  _Ninguno_"

    # Active tenants list
    ct_tenants = "\n".join([
        f"  • {t['name']} — {t['refresh_count']} refreshes"
        for t in ct.get("active_tenants", [])
    ]) or "  _Ninguno_"

    msg = f"""📊 *Weekly Pulse — {date_str}*

*🤖 Agente Creativo*
• Usuarios totales: *{agente.get('total_users', 0)}*
• Análisis (7d): *{agente.get('analyses_7d', 0)}* ({agente.get('analyses_failed', 0)} fallidos)
• Usuarios activos:
{agente_users}

*🧪 Creative Testing*
• Tenants totales: *{ct.get('total_tenants', 0)}*
• Cuentas Meta: *{ct.get('total_accounts', 0)}*
• Refreshes OK (7d): *{ct.get('refreshes_ok_7d', 0)}* ({ct.get('refreshes_failed_7d', 0)} fallidos)
• Tenants activos:
{ct_tenants}
"""
    return msg


def send_email(html_content: str):
    """Envoie l'email via SMTP."""
    if not SMTP_USER or not SMTP_PASS or not EMAIL_RECIPIENTS:
        print("❌ Email non configuré (SMTP_USER, SMTP_PASS, EMAIL_RECIPIENTS)")
        return False

    msg = MIMEMultipart("alternative")
    msg["From"] = SMTP_USER
    msg["To"] = ", ".join(EMAIL_RECIPIENTS)
    msg["Subject"] = f"📊 SaaS Weekly Pulse — {datetime.now().strftime('%d/%m/%Y')}"

    msg.attach(MIMEText(html_content, "html"))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
        server.quit()
        print(f"✅ Email envoyé à {', '.join(EMAIL_RECIPIENTS)}")
        return True
    except Exception as e:
        print(f"❌ Erreur envoi email: {e}")
        return False


def send_slack(message: str):
    """Envoie sur Slack via webhook."""
    if not SLACK_WEBHOOK_URL:
        print("❌ Slack non configuré (SLACK_WEBHOOK_URL)")
        return False

    try:
        resp = requests.post(SLACK_WEBHOOK_URL, json={"text": message})
        if resp.status_code == 200:
            print("✅ Message Slack envoyé")
            return True
        else:
            print(f"❌ Erreur Slack: {resp.status_code}")
            return False
    except Exception as e:
        print(f"❌ Erreur Slack: {e}")
        return False


def main():
    dry_run = "--dry-run" in sys.argv
    use_slack = "--slack" in sys.argv

    print(f"{'='*50}")
    print(f"Weekly Pulse — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}")

    # Collecter les stats
    print("\n📊 Collecte des données Agente Creativo...")
    agente_stats = get_agente_stats()
    if agente_stats.get("error"):
        print(f"  ⚠️ Erreur: {agente_stats['error']}")
    else:
        print(f"  ✅ {agente_stats['total_users']} users, {agente_stats['analyses_7d']} analyses (7d)")

    print("\n📊 Collecte des données Creative Testing...")
    ct_stats = get_ct_stats()
    if ct_stats.get("error"):
        print(f"  ⚠️ Erreur: {ct_stats['error']}")
    else:
        print(f"  ✅ {ct_stats['total_tenants']} tenants, {ct_stats['refreshes_ok_7d']} refreshes (7d)")

    # Générer le rapport
    if use_slack:
        report = generate_slack_message(agente_stats, ct_stats)
    else:
        report = generate_html_report(agente_stats, ct_stats)

    # Afficher ou envoyer
    if dry_run:
        print("\n" + "="*50)
        print("MODE DRY-RUN — Rapport généré (non envoyé):")
        print("="*50)
        if use_slack:
            print(report)
        else:
            # Afficher une version texte pour le terminal
            print(f"""
Agente Creativo:
  - Usuarios totales: {agente_stats.get('total_users', 0)}
  - Análisis (7d): {agente_stats.get('analyses_7d', 0)}
  - Activos: {[u['email'] for u in agente_stats.get('active_users', [])]}

Creative Testing:
  - Tenants totales: {ct_stats.get('total_tenants', 0)}
  - Cuentas Meta: {ct_stats.get('total_accounts', 0)}
  - Refreshes OK (7d): {ct_stats.get('refreshes_ok_7d', 0)}
  - Activos: {[t['name'] for t in ct_stats.get('active_tenants', [])]}
""")
    else:
        print("\n📤 Envoi du rapport...")
        if use_slack:
            send_slack(report)
        else:
            send_email(report)

    print("\n✅ Terminé")


if __name__ == "__main__":
    main()
