import asyncio
from datetime import date
from typing import Any, Dict, List, Optional, Union
import httpx

from app.core.config import get_settings
from app.core.logging import logger
from app.core.security import sanitize_sensitive_data
from app.clients.smartlead_exceptions import (
    SmartleadApiError,
    SmartleadAuthError,
    SmartleadNotFoundError,
    SmartleadRateLimitError,
    SmartleadServerError,
    SmartleadNetworkError,
)


class SmartleadApiClient:
    """
    Robust, production-ready async HTTP client for the official Smartlead API.

    Features:
    - Official query-parameter authentication (?api_key=...)
    - Concurrency bounding via asyncio.Semaphore
    - Exponential backoff retry logic for transient errors (429, 5xx, timeouts)
    - Retry-After header parsing for rate limits
    - Strict log sanitization preventing API keys from ever leaking
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        max_concurrency: Optional[int] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        client: Optional[httpx.AsyncClient] = None,
    ):
        settings = get_settings()
        self.api_key = api_key.strip() if api_key is not None else settings.smartlead_api_key.strip()
        self.base_url = (base_url or settings.api_base_url).rstrip("/")
        self.max_retries = max_retries if max_retries is not None else settings.max_retries
        self.timeout = timeout if timeout is not None else settings.request_timeout
        self.semaphore = asyncio.Semaphore(
            max_concurrency if max_concurrency is not None else min(3, settings.smartlead_max_concurrency or 3)
        )
        self._external_client = client
        self._internal_client: Optional[httpx.AsyncClient] = None
        self._rate_limit_lock = asyncio.Lock()
        self._last_request_time: float = 0.0
        self._min_interval: float = 0.65  # Paces to ~92 req/min (under Smartlead 100 req/min ceiling)
        self._cooldown_until: float = 0.0

    async def _get_http_client(self) -> httpx.AsyncClient:
        if self._external_client is not None:
            return self._external_client
        if self._internal_client is None or self._internal_client.is_closed:
            limits = httpx.Limits(max_connections=40, max_keepalive_connections=25)
            self._internal_client = httpx.AsyncClient(timeout=self.timeout, limits=limits)
        return self._internal_client

    async def aclose(self):
        """Closes internal HTTP client if open."""
        if self._internal_client is not None and not self._internal_client.is_closed:
            await self._internal_client.aclose()
            self._internal_client = None

    def _get_masked_url(self, url: str) -> str:
        return sanitize_sensitive_data(url, self.api_key)

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Any:
        # STRICT READ-ONLY GUARD:
        # Enforce that no deletion or mutating HTTP methods (DELETE, POST, PUT, PATCH) are ever sent to Smartlead API
        clean_method = method.strip().upper()
        if clean_method != "GET":
            raise SmartleadApiError(
                f"Prohibited HTTP method '{clean_method}'. Smartlead API integration is strictly READ-ONLY (GET only). Deletion or modification operations are strictly blocked."
            )

        if not self.api_key:
            raise SmartleadAuthError(
                "SMARTLEAD_API_KEY is not configured. Please supply a valid API key in environment variables."
            )

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        query_params = dict(params or {})
        query_params["api_key"] = self.api_key

        masked_url = self._get_masked_url(url)
        headers = {"Accept": "application/json"}

        attempt = 0
        backoff = 1.0

        async with self.semaphore:
            while attempt <= self.max_retries:
                attempt += 1
                try:
                    logger.debug(f"Smartlead API request [{method}] {masked_url} (attempt {attempt}/{self.max_retries + 1})")

                    # Smooth rate limiter: enforce pacing and respect any active cooldown
                    async with self._rate_limit_lock:
                        now = asyncio.get_event_loop().time()
                        if now < self._cooldown_until:
                            wait_cooldown = self._cooldown_until - now
                            logger.info(f"Rate limit cooldown active. Waiting {wait_cooldown:.1f}s before sending next request...")
                            await asyncio.sleep(wait_cooldown)
                            now = asyncio.get_event_loop().time()

                        elapsed = now - self._last_request_time
                        if elapsed < self._min_interval:
                            await asyncio.sleep(self._min_interval - elapsed)
                        self._last_request_time = asyncio.get_event_loop().time()

                    http_client = await self._get_http_client()
                    resp = await http_client.request(
                        method=method,
                        url=url,
                        params=query_params,
                        json=json_data,
                        headers=headers,
                    )

                    # Handle 2xx Success
                    if 200 <= resp.status_code < 300:
                        try:
                            return resp.json()
                        except Exception as json_err:
                            logger.error(f"Failed to decode JSON response from {masked_url}: {json_err}")
                            raise SmartleadApiError(
                                f"Invalid JSON received from Smartlead API: {json_err}",
                                status_code=resp.status_code,
                                response_text=resp.text[:500],
                            )

                    # Handle Auth Failures (401, 403) - DO NOT retry
                    if resp.status_code in (401, 403):
                        logger.error(f"Authentication failed ({resp.status_code}) when calling {masked_url}")
                        raise SmartleadAuthError(
                            f"Smartlead API authentication failure (HTTP {resp.status_code}). Check SMARTLEAD_API_KEY.",
                            status_code=resp.status_code,
                            response_text=resp.text[:500],
                        )

                    # Handle 404 Not Found
                    if resp.status_code == 404:
                        logger.warning(f"Resource not found (404) at {masked_url}")
                        raise SmartleadNotFoundError(
                            f"Resource not found at {masked_url}",
                            status_code=404,
                            response_text=resp.text[:500],
                        )

                    # Handle 429 Rate Limit
                    if resp.status_code == 429:
                        retry_after_header = resp.headers.get("Retry-After")
                        retry_after = float(retry_after_header) if retry_after_header else 60.0
                        now = asyncio.get_event_loop().time()
                        self._cooldown_until = max(self._cooldown_until, now + retry_after)
                        logger.info(
                            f"Smartlead API rate limit reached. Pausing gracefully for {retry_after:.0f}s to reset quota..."
                        )
                        if attempt > self.max_retries:
                            raise SmartleadRateLimitError(
                                f"Rate limit exceeded after {attempt} attempts.",
                                retry_after=retry_after,
                                response_text=resp.text[:500],
                            )
                        await asyncio.sleep(retry_after)
                        continue

                    # Handle 5xx Server Errors
                    if resp.status_code >= 500:
                        logger.warning(
                            f"Smartlead server error ({resp.status_code}) on attempt {attempt}. Retrying in {backoff:.2f}s..."
                        )
                        if attempt > self.max_retries:
                            raise SmartleadServerError(
                                f"Smartlead server returned HTTP {resp.status_code}.",
                                status_code=resp.status_code,
                                response_text=resp.text[:500],
                            )
                        await asyncio.sleep(backoff)
                        backoff *= 2.0
                        continue

                    # Other 4xx client errors
                    logger.error(f"Unexpected HTTP {resp.status_code} from {masked_url}: {resp.text[:300]}")
                    raise SmartleadApiError(
                        f"Smartlead API returned status {resp.status_code}",
                        status_code=resp.status_code,
                        response_text=resp.text[:500],
                    )

                except (httpx.TimeoutException, httpx.NetworkError, httpx.ConnectError) as net_err:
                    logger.warning(
                        f"Network exception calling {masked_url} on attempt {attempt}: {net_err}. Retrying in {backoff:.2f}s..."
                    )
                    if attempt > self.max_retries:
                        raise SmartleadNetworkError(
                            f"Smartlead network failure after {attempt} attempts: {net_err}"
                        )
                    await asyncio.sleep(backoff)
                    backoff *= 2.0

        raise SmartleadApiError(f"Request to {masked_url} failed after maximum retry attempts.")

    # -------------------------------------------------------------
    # High-level API Methods
    # -------------------------------------------------------------

    async def get_clients(self) -> List[Dict[str, Any]]:
        """
        Retrieves list of agency clients / sub-accounts.
        Endpoints: GET /client/list (or fallback GET /client/)
        """
        try:
            res = await self._request("GET", "client/list")
            if isinstance(res, list):
                return res
            if isinstance(res, dict) and "data" in res:
                return res["data"]
            return []
        except SmartleadNotFoundError:
            # Fallback to GET /client/
            logger.info("Attempting fallback to /client/ endpoint...")
            res = await self._request("GET", "client/")
            if isinstance(res, list):
                return res
            if isinstance(res, dict) and "data" in res:
                return res["data"]
            return []

    async def get_campaigns(self, client_id: Optional[Union[str, int]] = None) -> List[Dict[str, Any]]:
        """
        Retrieves all campaigns, optionally filtered by client_id.
        Endpoint: GET /campaigns/
        """
        params = {}
        if client_id is not None:
            params["client_id"] = str(client_id)

        res = await self._request("GET", "campaigns/", params=params)
        if isinstance(res, list):
            return res
        if isinstance(res, dict) and "data" in res:
            return res["data"]
        return []

    async def get_campaign_email_accounts(self, campaign_id: Union[str, int]) -> List[Dict[str, Any]]:
        """
        Retrieves all sending email accounts/mailboxes attached to a campaign.
        Endpoint: GET /campaigns/{campaign_id}/email-accounts
        """
        res = await self._request("GET", f"campaigns/{campaign_id}/email-accounts")
        if isinstance(res, list):
            return res
        if isinstance(res, dict) and "data" in res:
            return res["data"]
    async def get_campaign_analytics(self, campaign_id: Union[str, int]) -> Dict[str, Any]:
        """
        Retrieves top-level all-time analytics for a specific campaign.
        Official endpoint: GET /campaigns/{campaign_id}/analytics
        """
        res = await self._request("GET", f"campaigns/{campaign_id}/analytics")
        if isinstance(res, dict):
            return res
        return {}

    async def get_campaign_statistics(
        self,
        campaign_id: Union[str, int],
        email_status: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Retrieves campaign statistics.
        Official endpoint: GET /campaigns/{campaign_id}/statistics
        Reference: https://api.smartlead.ai/api-reference/campaigns/statistics
        """
        params = {"limit": limit, "offset": offset}
        if email_status:
            params["email_status"] = email_status
        params.update(kwargs)
        res = await self._request("GET", f"campaigns/{campaign_id}/statistics", params=params)
        if isinstance(res, dict):
            return res
        return {}

    async def get_campaign_analytics_by_date(
        self,
        campaign_id: Union[str, int],
        start_date: Union[str, date],
        end_date: Union[str, date],
    ) -> Any:
        """
        Retrieves analytics by date range for a specific campaign.
        Endpoint: GET /campaigns/{campaign_id}/analytics-by-date?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
        """
        s_date = start_date.isoformat() if isinstance(start_date, date) else str(start_date)
        e_date = end_date.isoformat() if isinstance(end_date, date) else str(end_date)

        params = {
            "start_date": s_date,
            "end_date": e_date,
        }
        res = await self._request("GET", f"campaigns/{campaign_id}/analytics-by-date", params=params)
        return res

    async def get_campaign_mailbox_statistics(
        self,
        campaign_id: Union[str, int],
        start_date: Union[str, date],
        end_date: Union[str, date],
        offset: int = 0,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves mailbox-level statistics for a campaign within a date range.
        Official endpoint: GET /campaigns/{campaign_id}/mailbox-statistics
        """
        s_date = start_date.isoformat() if isinstance(start_date, date) else str(start_date)
        e_date = end_date.isoformat() if isinstance(end_date, date) else str(end_date)

        params = {
            "start_date": s_date,
            "end_date": e_date,
            "limit": min(limit, 20),
            "offset": offset,
        }
        res = await self._request("GET", f"campaigns/{campaign_id}/mailbox-statistics", params=params)
        if isinstance(res, dict) and "data" in res:
            return res["data"]
        if isinstance(res, list):
            return res
        return []

    async def get_all_campaign_mailbox_statistics(
        self,
        campaign_id: Union[str, int],
        start_date: Union[str, date],
        end_date: Union[str, date],
    ) -> List[Dict[str, Any]]:
        """
        Retrieves all mailbox statistics for a campaign across all paginated pages.
        """
        all_stats: List[Dict[str, Any]] = []
        offset = 0
        limit = 20

        while True:
            batch = await self.get_campaign_mailbox_statistics(
                campaign_id=campaign_id,
                start_date=start_date,
                end_date=end_date,
                offset=offset,
                limit=limit,
            )
            if not batch:
                break
            all_stats.extend(batch)
            if len(batch) < limit:
                break
            offset += limit

        return all_stats

    async def get_email_accounts(self, offset: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Retrieves workspace email accounts with pagination.
        Endpoint: GET /email-accounts/
        """
        params = {"offset": offset, "limit": limit}
        res = await self._request("GET", "email-accounts/", params=params)
        if isinstance(res, list):
            return res
        if isinstance(res, dict) and "data" in res:
            return res["data"]
        return []

    async def test_connection(self) -> Dict[str, Any]:
        """
        Performs a safe, read-only test request to verify API authentication and connectivity.
        Never reveals the full API key.
        """
        settings = get_settings()
        masked_key = settings.masked_api_key

        logger.info(f"Testing Smartlead API connection using key: {masked_key}...")
        try:
            # Safe call to list campaigns with a limit or first page
            campaigns = await self.get_campaigns()
            count = len(campaigns) if isinstance(campaigns, list) else 0
            return {
                "status": "success",
                "message": f"Successfully connected to Smartlead API. Accessible campaigns count: {count}",
                "masked_api_key": masked_key,
                "campaigns_count": count,
            }
        except SmartleadAuthError as ae:
            return {
                "status": "auth_error",
                "message": f"Authentication failed: {ae.message}",
                "masked_api_key": masked_key,
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Connection test failed: {str(e)}",
                "masked_api_key": masked_key,
            }
