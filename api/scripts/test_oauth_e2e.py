#!/usr/bin/env python3
"""
Script Flask minimal pour tester le flux OAuth Facebook end-to-end

Ce script prouve que l'OAuth fonctionne VRAIMENT pour de futurs clients.
Après validation, le code sera porté dans FastAPI.

Prérequis:
    pip install flask requests

Usage:
    1. Configurer le redirect URI dans Facebook (voir instructions)
    2. python test_oauth_e2e.py
    3. Ouvrir http://localhost:5000
    4. Cliquer "Login with Facebook"
    5. Autoriser l'app
    6. Voir vos ad accounts s'afficher automatiquement
"""
from flask import Flask, request, redirect, session, render_template_string
import requests
import secrets
import hmac
import hashlib
from urllib.parse import urlencode

# ===== CONFIGURATION =====
# Credentials de TON app Facebook
FACEBOOK_APP_ID = "1187229696581219"
FACEBOOK_APP_SECRET = "bc2caa39ddc1bf2da1f7223936e060cb"
FACEBOOK_API_VERSION = "v23.0"
FACEBOOK_REDIRECT_URI = "https://1046436aeac1.ngrok-free.app/auth/facebook/callback"

# Clé secrète pour Flask session (générée aléatoirement)
FLASK_SECRET_KEY = secrets.token_hex(32)

app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY


# ===== HELPERS =====

def generate_appsecret_proof(access_token: str) -> str:
    """
    Génère appsecret_proof pour sécuriser les appels Meta API
    Requis par les best practices Facebook
    """
    return hmac.new(
        key=FACEBOOK_APP_SECRET.encode("utf-8"),
        msg=access_token.encode("utf-8"),
        digestmod=hashlib.sha256
    ).hexdigest()


def exchange_code_for_token(code: str) -> dict:
    """
    Échange le code OAuth contre un access token
    Puis échange pour un long-lived token (60 jours)
    """
    # Étape 1: Code → Short-lived token
    token_url = f"https://graph.facebook.com/{FACEBOOK_API_VERSION}/oauth/access_token"
    response = requests.get(token_url, params={
        "client_id": FACEBOOK_APP_ID,
        "client_secret": FACEBOOK_APP_SECRET,
        "redirect_uri": FACEBOOK_REDIRECT_URI,
        "code": code,
    }, timeout=10)
    response.raise_for_status()
    short_token_data = response.json()
    short_token = short_token_data["access_token"]

    # Étape 2: Short-lived → Long-lived token (60 jours)
    response = requests.get(token_url, params={
        "grant_type": "fb_exchange_token",
        "client_id": FACEBOOK_APP_ID,
        "client_secret": FACEBOOK_APP_SECRET,
        "fb_exchange_token": short_token,
    }, timeout=10)
    response.raise_for_status()
    long_token_data = response.json()

    return {
        "access_token": long_token_data["access_token"],
        "token_type": long_token_data.get("token_type", "bearer"),
        "expires_in": long_token_data.get("expires_in"),  # ~5184000 sec (60 jours)
    }


def debug_token(access_token: str) -> dict:
    """
    Appelle /debug_token pour récupérer metadata du token
    (user_id, scopes, expiration, etc.)
    """
    app_token = f"{FACEBOOK_APP_ID}|{FACEBOOK_APP_SECRET}"
    debug_url = f"https://graph.facebook.com/{FACEBOOK_API_VERSION}/debug_token"
    response = requests.get(debug_url, params={
        "input_token": access_token,
        "access_token": app_token,
    }, timeout=10)
    response.raise_for_status()
    return response.json()["data"]


def fetch_ad_accounts(access_token: str) -> list:
    """
    Récupère les ad accounts de l'utilisateur connecté
    Avec appsecret_proof pour la sécurité
    """
    proof = generate_appsecret_proof(access_token)
    url = f"https://graph.facebook.com/{FACEBOOK_API_VERSION}/me/adaccounts"
    response = requests.get(url, params={
        "fields": "id,name,currency,timezone_name,account_status",
        "access_token": access_token,
        "appsecret_proof": proof,
    }, timeout=10)
    response.raise_for_status()
    return response.json().get("data", [])


# ===== ROUTES =====

@app.route("/")
def home():
    """Page d'accueil avec bouton Login with Facebook"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test OAuth Facebook - Creative Testing SaaS</title>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                max-width: 800px;
                margin: 50px auto;
                padding: 20px;
                background: #f5f5f5;
            }
            .card {
                background: white;
                border-radius: 8px;
                padding: 40px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            }
            h1 {
                color: #1877f2;
                margin-bottom: 10px;
            }
            .subtitle {
                color: #666;
                margin-bottom: 30px;
            }
            .btn {
                display: inline-block;
                padding: 12px 24px;
                background: #1877f2;
                color: white;
                text-decoration: none;
                border-radius: 6px;
                font-weight: 600;
                transition: background 0.3s;
            }
            .btn:hover {
                background: #166fe5;
            }
            .info {
                margin-top: 30px;
                padding: 20px;
                background: #e7f3ff;
                border-left: 4px solid #1877f2;
                border-radius: 4px;
            }
            .info h3 {
                margin-top: 0;
                color: #1877f2;
            }
            .check {
                color: #28a745;
                margin-right: 8px;
            }
            code {
                background: #f0f0f0;
                padding: 2px 6px;
                border-radius: 3px;
                font-size: 0.9em;
            }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>🧪 Test OAuth Facebook</h1>
            <p class="subtitle">Proof of Concept - Creative Testing SaaS</p>

            <a href="/auth/facebook/login" class="btn">
                🔐 Login with Facebook
            </a>

            <div class="info">
                <h3>📋 Ce que ce test va démontrer :</h3>
                <p><span class="check">✓</span> Un client clique sur "Login with Facebook"</p>
                <p><span class="check">✓</span> Facebook demande l'autorisation</p>
                <p><span class="check">✓</span> Le backend récupère automatiquement le token</p>
                <p><span class="check">✓</span> Les ad accounts du client s'affichent</p>
                <p><span class="check">✓</span> <strong>Le client ne voit JAMAIS de token</strong></p>
            </div>

            <div class="info" style="background: #fff3cd; border-color: #ffc107;">
                <h3>⚠️ Prérequis</h3>
                <p>Le Redirect URI doit être configuré dans Facebook :</p>
                <p><code>{{ redirect_uri }}</code></p>
                <p>Voir instructions dans le README ou demander à Pablo.</p>
            </div>
        </div>
    </body>
    </html>
    """
    return render_template_string(html, redirect_uri=FACEBOOK_REDIRECT_URI)


@app.route("/auth/facebook/login")
def facebook_login():
    """
    Redirige l'utilisateur vers Facebook pour autoriser l'app
    Génère un state sécurisé pour prévenir CSRF
    """
    # Générer state aléatoire et le stocker en session
    state = secrets.token_urlsafe(32)
    session["oauth_state"] = state

    # Construire l'URL de redirection Facebook
    params = {
        "client_id": FACEBOOK_APP_ID,
        "redirect_uri": FACEBOOK_REDIRECT_URI,
        "response_type": "code",
        "scope": "ads_read",  # Minimal scope (ChatGPT-5 recommandation)
        "state": state,
    }
    auth_url = f"https://www.facebook.com/{FACEBOOK_API_VERSION}/dialog/oauth?{urlencode(params)}"

    return redirect(auth_url)


@app.route("/auth/facebook/callback")
def facebook_callback():
    """
    Callback OAuth - Facebook redirige ici après autorisation
    Échange le code contre un token et récupère les ad accounts
    """
    # Récupérer les paramètres
    code = request.args.get("code")
    state = request.args.get("state")
    error = request.args.get("error")
    error_description = request.args.get("error_description")

    # Gestion des erreurs
    if error:
        return render_error(f"Erreur OAuth: {error}", error_description)

    # Vérifier le state (sécurité CSRF)
    if not state or state != session.get("oauth_state"):
        return render_error("Erreur de sécurité", "State invalide (possible attaque CSRF)")

    if not code:
        return render_error("Erreur OAuth", "Code manquant")

    try:
        # Étape 1: Échanger code → long-lived token
        token_data = exchange_code_for_token(code)
        access_token = token_data["access_token"]
        expires_in = token_data.get("expires_in")

        # Étape 2: Debug token pour récupérer metadata
        token_info = debug_token(access_token)
        user_id = token_info.get("user_id")
        scopes = token_info.get("scopes", [])
        expires_at = token_info.get("expires_at")

        # Étape 3: Récupérer les ad accounts
        accounts = fetch_ad_accounts(access_token)

        # Afficher les résultats
        return render_success(
            access_token=access_token,
            expires_in=expires_in,
            user_id=user_id,
            scopes=scopes,
            accounts=accounts,
        )

    except requests.exceptions.RequestException as e:
        error_msg = str(e)
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                error_msg = error_data.get("error", {}).get("message", error_msg)
            except:
                pass
        return render_error("Erreur API Facebook", error_msg)


def render_error(title: str, message: str):
    """Affiche une page d'erreur"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Erreur - Test OAuth</title>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                max-width: 800px;
                margin: 50px auto;
                padding: 20px;
                background: #f5f5f5;
            }
            .card {
                background: white;
                border-radius: 8px;
                padding: 40px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            }
            .error {
                color: #dc3545;
            }
            .btn {
                display: inline-block;
                margin-top: 20px;
                padding: 12px 24px;
                background: #1877f2;
                color: white;
                text-decoration: none;
                border-radius: 6px;
            }
        </style>
    </head>
    <body>
        <div class="card">
            <h1 class="error">❌ {{ title }}</h1>
            <p>{{ message }}</p>
            <a href="/" class="btn">← Retour</a>
        </div>
    </body>
    </html>
    """
    return render_template_string(html, title=title, message=message)


def render_success(access_token: str, expires_in: int, user_id: str, scopes: list, accounts: list):
    """Affiche les résultats du test OAuth"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>✅ OAuth Réussi - Test E2E</title>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                max-width: 1000px;
                margin: 50px auto;
                padding: 20px;
                background: #f5f5f5;
            }
            .card {
                background: white;
                border-radius: 8px;
                padding: 40px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                margin-bottom: 20px;
            }
            h1 {
                color: #28a745;
            }
            .success {
                background: #d4edda;
                border-left: 4px solid #28a745;
                padding: 20px;
                border-radius: 4px;
                margin: 20px 0;
            }
            .info-grid {
                display: grid;
                grid-template-columns: 200px 1fr;
                gap: 10px;
                margin: 20px 0;
            }
            .label {
                font-weight: 600;
                color: #666;
            }
            .token {
                font-family: monospace;
                background: #f0f0f0;
                padding: 10px;
                border-radius: 4px;
                word-break: break-all;
                font-size: 0.85em;
            }
            .account {
                background: #f8f9fa;
                padding: 15px;
                margin: 10px 0;
                border-radius: 6px;
                border-left: 4px solid #1877f2;
            }
            .account h3 {
                margin: 0 0 10px 0;
                color: #1877f2;
            }
            .badge {
                display: inline-block;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 0.85em;
                font-weight: 600;
            }
            .badge-success {
                background: #d4edda;
                color: #155724;
            }
            .badge-warning {
                background: #fff3cd;
                color: #856404;
            }
            .btn {
                display: inline-block;
                margin-top: 20px;
                padding: 12px 24px;
                background: #1877f2;
                color: white;
                text-decoration: none;
                border-radius: 6px;
            }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>✅ SUCCÈS COMPLET - OAuth Facebook fonctionne !</h1>

            <div class="success">
                <h2>🎯 Ce test prouve que :</h2>
                <p>✓ Le flux OAuth fonctionne avec les credentials de Pablo</p>
                <p>✓ On peut récupérer automatiquement les ad accounts d'un utilisateur</p>
                <p>✓ Le SaaS peut fonctionner pour de VRAIS clients sans leur demander de token</p>
                <p>✓ On a toutes les permissions nécessaires (ads_read)</p>
            </div>

            <h2>📊 Informations du token</h2>
            <div class="info-grid">
                <div class="label">User ID:</div>
                <div>{{ user_id }}</div>

                <div class="label">Scopes accordés:</div>
                <div>
                    {% for scope in scopes %}
                        <span class="badge badge-success">{{ scope }}</span>
                    {% endfor %}
                </div>

                <div class="label">Expiration:</div>
                <div>
                    {% if expires_in %}
                        Dans {{ (expires_in / 86400) | int }} jours ({{ expires_in }} secondes)
                    {% else %}
                        Long-lived token (~60 jours)
                    {% endif %}
                </div>

                <div class="label">Access Token:</div>
                <div class="token">{{ access_token[:30] }}...{{ access_token[-10:] }}</div>
            </div>

            <h2>💼 Ad Accounts trouvés ({{ accounts|length }})</h2>
            {% for account in accounts[:10] %}
                <div class="account">
                    <h3>{{ account.name }}</h3>
                    <div class="info-grid">
                        <div class="label">Account ID:</div>
                        <div>{{ account.id }}</div>

                        <div class="label">Currency:</div>
                        <div>{{ account.currency }}</div>

                        <div class="label">Timezone:</div>
                        <div>{{ account.timezone_name }}</div>

                        <div class="label">Status:</div>
                        <div>
                            {% if account.account_status == 1 %}
                                <span class="badge badge-success">Active</span>
                            {% else %}
                                <span class="badge badge-warning">Status {{ account.account_status }}</span>
                            {% endif %}
                        </div>
                    </div>
                </div>
            {% endfor %}
            {% if accounts|length > 10 %}
                <p style="text-align: center; color: #666;">... et {{ accounts|length - 10 }} autres comptes</p>
            {% endif %}

            <a href="/" class="btn">← Refaire le test</a>
        </div>

        <div class="card">
            <h2>📋 Prochaines étapes</h2>
            <ol>
                <li>✅ Screenshot de cette page pour montrer à Pablo</li>
                <li>Porter ce code dans FastAPI (<code>api/app/routers/auth.py</code>)</li>
                <li>Stocker le token chiffré dans PostgreSQL</li>
                <li>Implémenter le refresh automatique des données</li>
                <li>App Review Facebook pour passer en mode Live</li>
            </ol>
        </div>
    </body>
    </html>
    """
    return render_template_string(
        html,
        access_token=access_token,
        expires_in=expires_in,
        user_id=user_id,
        scopes=scopes,
        accounts=accounts,
    )


if __name__ == "__main__":
    print("\n" + "="*70)
    print("  🧪 TEST OAUTH FACEBOOK E2E - CREATIVE TESTING SAAS")
    print("="*70)
    print()
    print("📋 Ce script teste le flux OAuth complet (end-to-end)")
    print()
    print("⚠️  PRÉREQUIS:")
    print("   Configurer le Redirect URI dans Facebook:")
    print(f"   👉 {FACEBOOK_REDIRECT_URI}")
    print()
    print("   Aller sur:")
    print(f"   https://developers.facebook.com/apps/{FACEBOOK_APP_ID}/fb-login/settings/")
    print()
    print("   Dans 'Valid OAuth Redirect URIs', ajouter:")
    print(f"   {FACEBOOK_REDIRECT_URI}")
    print()
    print("🚀 Serveur démarré sur http://localhost:5000")
    print("   Ouvre cette URL dans ton navigateur et clique 'Login with Facebook'")
    print()
    print("="*70)
    print()

    app.run(debug=True, port=5000)
