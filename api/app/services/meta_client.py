"""
Client Meta/Facebook avec retry intelligent et timeouts
Implémentation sécurisée avec appsecret_proof et gestion des rate limits
"""
import asyncio
import random
import hmac
import hashlib
from typing import Any, Dict, Optional
import httpx
from ..config import settings


class MetaAPIError(Exception):
    """Erreur lors d'un appel Meta API"""
    pass


class MetaClient:
    """
    Client asynchrone pour Meta Graph API

    Features:
    - Timeouts explicites (connect/read)
    - Retry avec backoff exponentiel + jitter
    - appsecret_proof automatique
    - Gestion intelligente des rate limits (429)
    """

    def __init__(self):
        self.app_id = settings.META_APP_ID
        self.app_secret = settings.META_APP_SECRET
        self.api_version = settings.META_API_VERSION
        self.base_url = f"https://graph.facebook.com/{self.api_version}"

    def _generate_appsecret_proof(self, access_token: str) -> str:
        """
        Génère appsecret_proof pour sécuriser les appels Meta API
        Best practice recommandée par Meta
        """
        return hmac.new(
            key=self.app_secret.encode("utf-8"),
            msg=access_token.encode("utf-8"),
            digestmod=hashlib.sha256
        ).hexdigest()

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        attempts: int = 4,
        base_delay: float = 0.4,
    ) -> Dict[str, Any]:
        """
        Effectue une requête HTTP avec retry intelligent

        Args:
            method: GET, POST, etc.
            url: URL complète
            params: Query parameters
            json_data: JSON body (pour POST)
            attempts: Nombre max de tentatives
            base_delay: Délai de base pour backoff (secondes)

        Returns:
            Response JSON

        Raises:
            MetaAPIError: En cas d'erreur après tous les retries
        """
        # Timeouts explicites pour éviter les blocages
        timeout = httpx.Timeout(
            connect=3.0,  # 3s max pour établir la connexion
            read=8.0,     # 8s max pour lire la réponse
            write=3.0,    # 3s max pour écrire la requête
            pool=3.0      # 3s max pour obtenir une connexion du pool
        )

        async with httpx.AsyncClient(timeout=timeout) as client:
            for attempt in range(1, attempts + 1):
                try:
                    # Effectuer la requête
                    if method.upper() == "GET":
                        response = await client.get(url, params=params)
                    elif method.upper() == "POST":
                        response = await client.post(url, params=params, json=json_data)
                    else:
                        raise ValueError(f"Method {method} not supported")

                    # Gestion des erreurs HTTP
                    # Stop retry sur 4xx (sauf 429 rate limit)
                    if 400 <= response.status_code < 500 and response.status_code != 429:
                        response.raise_for_status()
                        return response.json()

                    # 5xx ou 429 → retry
                    response.raise_for_status()
                    return response.json()

                except (httpx.HTTPStatusError, httpx.ConnectError, httpx.ReadTimeout) as e:
                    # Dernière tentative → raise
                    if attempt == attempts:
                        raise MetaAPIError(f"Meta API error after {attempts} attempts: {e}")

                    # Backoff exponentiel + jitter
                    delay = base_delay * (2 ** (attempt - 1)) + random.random() * 0.2
                    await asyncio.sleep(delay)

        raise MetaAPIError("Unexpected error in retry loop")

    async def exchange_code_for_token(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """
        Échange le code OAuth contre un access token
        Puis échange pour un long-lived token (60 jours)

        Returns:
            {
                "access_token": str,
                "token_type": "bearer",
                "expires_in": int (secondes, ~5184000 = 60 jours)
            }
        """
        token_url = f"{self.base_url}/oauth/access_token"

        # Étape 1: Code → Short-lived token
        short_token_data = await self._request_with_retry(
            "GET",
            token_url,
            params={
                "client_id": self.app_id,
                "client_secret": self.app_secret,
                "redirect_uri": redirect_uri,
                "code": code,
            }
        )
        short_token = short_token_data["access_token"]

        # Étape 2: Short-lived → Long-lived token
        long_token_data = await self._request_with_retry(
            "GET",
            token_url,
            params={
                "grant_type": "fb_exchange_token",
                "client_id": self.app_id,
                "client_secret": self.app_secret,
                "fb_exchange_token": short_token,
            }
        )

        return {
            "access_token": long_token_data["access_token"],
            "token_type": long_token_data.get("token_type", "bearer"),
            "expires_in": long_token_data.get("expires_in"),  # ~5184000 sec
        }

    async def debug_token(self, access_token: str) -> Dict[str, Any]:
        """
        Récupère les métadonnées d'un token (user_id, scopes, expiration)

        Returns:
            {
                "user_id": str,
                "app_id": str,
                "scopes": List[str],
                "expires_at": int (timestamp),
                ...
            }
        """
        app_token = f"{self.app_id}|{self.app_secret}"
        debug_url = f"{self.base_url}/debug_token"

        response = await self._request_with_retry(
            "GET",
            debug_url,
            params={
                "input_token": access_token,
                "access_token": app_token,
            }
        )
        return response["data"]

    async def get_user_info(self, access_token: str, fields: str = "id,name,email") -> Dict[str, Any]:
        """
        Récupère les infos de l'utilisateur

        Args:
            access_token: Token de l'utilisateur
            fields: Champs à récupérer (séparés par virgules)
        """
        me_url = f"{self.base_url}/me"
        proof = self._generate_appsecret_proof(access_token)

        return await self._request_with_retry(
            "GET",
            me_url,
            params={
                "access_token": access_token,
                "appsecret_proof": proof,
                "fields": fields,
            }
        )

    async def get_ad_accounts(
        self,
        access_token: str,
        fields: str = "id,name,currency,timezone_name,account_status"
    ) -> list[Dict[str, Any]]:
        """
        Récupère les ad accounts de l'utilisateur

        Args:
            access_token: Token de l'utilisateur
            fields: Champs à récupérer

        Returns:
            List of ad accounts with selected fields
        """
        accounts_url = f"{self.base_url}/me/adaccounts"
        proof = self._generate_appsecret_proof(access_token)

        response = await self._request_with_retry(
            "GET",
            accounts_url,
            params={
                "access_token": access_token,
                "appsecret_proof": proof,
                "fields": fields,
            }
        )

        return response.get("data", [])

    async def get_campaigns(
        self,
        ad_account_id: str,
        access_token: str,
        fields: str = "id,name,status",
        limit: int = 25
    ) -> list[Dict[str, Any]]:
        """
        Récupère les campaigns d'un ad account

        Args:
            ad_account_id: ID du compte (ex: "act_123456")
            access_token: Token de l'utilisateur
            fields: Champs à récupérer
            limit: Nombre max de campaigns à récupérer

        Returns:
            List of campaigns with selected fields
        """
        campaigns_url = f"{self.base_url}/{ad_account_id}/campaigns"
        proof = self._generate_appsecret_proof(access_token)

        response = await self._request_with_retry(
            "GET",
            campaigns_url,
            params={
                "access_token": access_token,
                "appsecret_proof": proof,
                "fields": fields,
                "limit": limit,
            }
        )

        return response.get("data", [])


# Instance globale (singleton pattern)
meta_client = MetaClient()
