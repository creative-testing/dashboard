"""
Client Meta/Facebook avec retry intelligent et timeouts
Gestion des rate limits avec backoff exponentiel
"""
import asyncio
import json
import random
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
    - Gestion intelligente des rate limits (429)
    - Support user access tokens (long-lived)
    """

    def __init__(self):
        self.app_id = settings.META_APP_ID
        self.app_secret = settings.META_APP_SECRET
        self.api_version = settings.META_API_VERSION
        self.base_url = f"https://graph.facebook.com/{self.api_version}"

    # DISABLED: appsecret_proof causes 400 errors with production tokens
    # Meta docs say it's optional for user access tokens
    # def _generate_appsecret_proof(self, access_token: str) -> str:
    #     """
    #     Génère appsecret_proof pour sécuriser les appels Meta API
    #     Best practice recommandée par Meta
    #     """
    #     return hmac.new(
    #         key=self.app_secret.encode("utf-8"),
    #         msg=access_token.encode("utf-8"),
    #         digestmod=hashlib.sha256
    #     ).hexdigest()

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
        # Read timeout élevé (30s) pour gros comptes comme Mandala (2000+ ads)
        timeout = httpx.Timeout(
            connect=5.0,  # 5s max pour établir la connexion
            read=30.0,    # 30s max pour lire la réponse (Meta API peut être lent pour gros datasets)
            write=5.0,    # 5s max pour écrire la requête
            pool=5.0      # 5s max pour obtenir une connexion du pool
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

        return await self._request_with_retry(
            "GET",
            me_url,
            params={
                "access_token": access_token,
                "fields": fields,
            }
        )

    async def get_ad_accounts(
        self,
        access_token: str,
        fields: str = "id,name,currency,timezone_name,account_status",
        limit: int = 100
    ) -> list[Dict[str, Any]]:
        """
        Récupère TOUS les ad accounts de l'utilisateur (avec pagination)

        Args:
            access_token: Token de l'utilisateur
            fields: Champs à récupérer
            limit: Nombre max de comptes par page (max 100)

        Returns:
            List of ALL ad accounts with selected fields (paginated)
        """
        accounts_url = f"{self.base_url}/me/adaccounts"

        all_accounts = []
        params = {
            "access_token": access_token,
            "fields": fields,
            "limit": limit,
        }

        # Paginate through all results
        next_url = accounts_url
        page_count = 0
        max_pages = 50  # Safety limit (50 pages * 100 comptes = 5000 max)

        while next_url and page_count < max_pages:
            response = await self._request_with_retry("GET", next_url, params=params)

            if "data" in response:
                all_accounts.extend(response["data"])

            # Check for next page
            if "paging" in response and "next" in response["paging"]:
                next_url = response["paging"]["next"]
                params = {}  # Next URL contient déjà les params
                page_count += 1
            else:
                break

        return all_accounts

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

        response = await self._request_with_retry(
            "GET",
            campaigns_url,
            params={
                "access_token": access_token,
                "fields": fields,
                "limit": limit,
            }
        )

        return response.get("data", [])

    async def get_insights_daily(
        self,
        ad_account_id: str,
        access_token: str,
        since_date: str,
        until_date: str,
        limit: int = 500
    ) -> list[Dict[str, Any]]:
        """
        Récupère les insights daily (time_increment=1) pour un ad account

        CRITICAL: Returns daily granular data needed for period aggregation

        Args:
            ad_account_id: ID du compte (ex: "act_123456")
            access_token: Token de l'utilisateur
            since_date: Date de début (YYYY-MM-DD)
            until_date: Date de fin (YYYY-MM-DD)
            limit: Nombre max de rows par page (max 500)

        Returns:
            List of daily ad insights with fields:
            - ad_id, ad_name, campaign_name, campaign_id, adset_name, adset_id
            - date_start, date_stop (each row = 1 day)
            - impressions, clicks, unique_outbound_clicks, reach, frequency
            - cpm, ctr, spend
            - actions, action_values, conversions, conversion_values
            - created_time
        """
        insights_url = f"{self.base_url}/{ad_account_id}/insights"

        # Fields matching production pipeline (fetch_with_smart_limits.py:271)
        fields = (
            "ad_id,ad_name,campaign_name,campaign_id,adset_name,adset_id,"
            "impressions,spend,clicks,unique_outbound_clicks,reach,frequency,"
            "cpm,ctr,actions,action_values,conversions,conversion_values,created_time"
        )

        all_insights = []
        params = {
            "access_token": access_token,
            "level": "ad",
            "time_range": json.dumps({"since": since_date, "until": until_date}),
            "time_increment": "1",  # ← CRITICAL: daily data
            "fields": fields,
            "limit": limit,
            "action_report_time": "conversion",  # Align with Ads Manager
            "use_unified_attribution_setting": "true"  # Best practice
        }

        # Paginate through all results
        next_url = insights_url
        page_count = 0
        max_pages = 200  # Safety limit

        while next_url and page_count < max_pages:
            response = await self._request_with_retry("GET", next_url, params=params)

            if "data" in response:
                all_insights.extend(response["data"])

            # Check for next page
            if "paging" in response and "next" in response["paging"]:
                next_url = response["paging"]["next"]
                params = {}  # Next URL contains all params
                page_count += 1
            else:
                break

        return all_insights

    async def fetch_creatives_batch(
        self,
        ad_ids: list[str],
        access_token: str
    ) -> Dict[str, dict]:
        """
        Récupère les creatives (format, media_url) pour un batch de max 50 ads

        Utilise l'API Batch de Meta pour optimiser les appels
        """
        if not ad_ids or len(ad_ids) == 0:
            return {}

        # Limiter à 50 ads max par batch (limitation Meta API)
        ad_ids = ad_ids[:50]

        # Préparer les requêtes batch
        batch_requests = []
        for ad_id in ad_ids:
            batch_requests.append({
                "method": "GET",
                "relative_url": f"{ad_id}?fields=status,effective_status,created_time,creative{{status,video_id,image_url,instagram_permalink_url,object_story_spec}}"
            })

        try:
            params = {
                "access_token": access_token,
                "batch": json.dumps(batch_requests)
            }

            async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
                response = await client.post(self.base_url, data=params)

            if response.status_code != 200:
                return {}

            results = {}
            batch_responses = response.json()

            for i, resp in enumerate(batch_responses):
                if resp.get("code") == 200:
                    ad_data = json.loads(resp["body"])
                    ad_id = ad_ids[i]

                    # Extraire les infos creative
                    creative = ad_data.get("creative", {})

                    # Déterminer format et media_url
                    format_type = "UNKNOWN"
                    media_url = ""

                    if creative.get("video_id"):
                        format_type = "VIDEO"
                        media_url = f"https://www.facebook.com/watch/?v={creative['video_id']}"
                    elif creative.get("image_url"):
                        format_type = "IMAGE"
                        media_url = creative["image_url"]
                    elif creative.get("instagram_permalink_url"):
                        format_type = "CAROUSEL"
                        media_url = creative["instagram_permalink_url"]
                    elif creative.get("object_story_spec"):
                        # Fallback: chercher dans object_story_spec
                        story = creative.get("object_story_spec", {})
                        if story.get("video_data"):
                            format_type = "VIDEO"
                        elif story.get("link_data", {}).get("image_hash"):
                            format_type = "IMAGE"

                    results[ad_id] = {
                        "status": ad_data.get("status", "UNKNOWN"),
                        "effective_status": ad_data.get("effective_status", "UNKNOWN"),
                        "format": format_type,
                        "media_url": media_url,
                        "creative_status": creative.get("status", "UNKNOWN")
                    }

            return results

        except Exception:
            return {}

    async def enrich_ads_with_creatives(
        self,
        ads: list[Dict[str, Any]],
        access_token: str
    ) -> list[Dict[str, Any]]:
        """
        Enrichit les ads avec leurs creatives (format, media_url, status)

        Utilise des batch requests (50 ads/batch) en parallèle pour optimiser

        Args:
            ads: Liste des ads à enrichir (doit contenir 'ad_id')
            access_token: Token Meta

        Returns:
            Liste des ads enrichies avec format, media_url, status
        """
        if not ads:
            return ads

        # Extraire les unique ad_ids
        ad_ids = list(set(ad['ad_id'] for ad in ads if 'ad_id' in ad))

        # Grouper en batchs de 50
        batches = [ad_ids[i:i+50] for i in range(0, len(ad_ids), 50)]

        # Fetch tous les batchs en parallèle (limité à 25 concurrent)
        creative_data = {}

        # Process by chunks of 25 batches at a time
        for chunk_start in range(0, len(batches), 25):
            chunk = batches[chunk_start:chunk_start+25]
            tasks = [self.fetch_creatives_batch(batch, access_token) for batch in chunk]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, dict):
                    creative_data.update(result)

        # Enrichir les ads avec les données creative
        enriched_count = 0
        for ad in ads:
            ad_id = ad.get('ad_id')
            if ad_id and ad_id in creative_data:
                ad.update(creative_data[ad_id])
                enriched_count += 1
            else:
                # Valeurs par défaut si pas de données creative
                ad.setdefault('status', 'UNKNOWN')
                ad.setdefault('effective_status', 'UNKNOWN')
                ad.setdefault('format', 'UNKNOWN')
                ad.setdefault('media_url', '')

        return ads


# Instance globale (singleton pattern)
meta_client = MetaClient()
