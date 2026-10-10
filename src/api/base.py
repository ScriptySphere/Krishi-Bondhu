"""Base NASA API client with common functionality."""
import asyncio
import hashlib
import json
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import httpx
from loguru import logger

from ..models.location import Location


class NASAAPIError(Exception):
    """Base exception for NASA API errors."""
    def __init__(self, message: str, status_code: Optional[int] = None, response: Optional[Dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class NASAAPIClient(ABC):
    """Abstract base class for NASA API clients."""

    BASE_URL: str = ""
    RATE_LIMIT: float = 1.0  # requests per second
    CACHE_TTL: int = 86400  # 24 hours default

    def __init__(
        self,
        api_key: Optional[str] = None,
        cache_dir: Optional[Path] = None,
        timeout: float = 60.0,
    ):
        self.api_key = api_key
        self.cache_dir = cache_dir or Path("./data/cache")
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            # Read-only filesystem: run uncached rather than crash
            logger.warning(f"Cache dir unavailable ({e}); running without disk cache")
            self.cache_dir = None
        self.timeout = timeout
        self._last_request_time = 0.0
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                headers=self._default_headers(),
            )
        return self._client

    def _default_headers(self) -> Dict[str, str]:
        # NASA POWER is public and rejects unexpected auth headers, so send only
        # a User-Agent. Clients that need a key pass it as a query param.
        return {"User-Agent": "NASA-CropRotation-Tool/1.0"}

    async def _rate_limit(self):
        """Enforce rate limiting."""
        elapsed = time.time() - self._last_request_time
        min_interval = 1.0 / self.RATE_LIMIT
        if elapsed < min_interval:
            await asyncio.sleep(min_interval - elapsed)
        self._last_request_time = time.time()

    def _cache_path(self, cache_key: str) -> Path:
        return self.cache_dir / f"{self.__class__.__name__}_{cache_key}.json"

    def _cache_key(self, endpoint: str, params: Dict) -> str:
        """Generate a stable cache key from endpoint and params."""
        key_string = f"{endpoint}?{urlencode(sorted((k, str(v)) for k, v in params.items()))}"
        return hashlib.sha256(key_string.encode()).hexdigest()[:32]

    async def _get_cached(self, cache_key: str) -> Optional[Dict]:
        """Retrieve cached response if still fresh."""
        if self.cache_dir is None:
            return None

        cache_file = self._cache_path(cache_key)
        if not cache_file.exists():
            return None

        try:
            with open(cache_file) as f:
                cached = json.load(f)

            if time.time() - cached["timestamp"] > self.CACHE_TTL:
                return None

            return cached["data"]
        except (OSError, ValueError, KeyError) as e:
            logger.warning(f"Cache read failed for {cache_key}: {e}")
            return None

    async def _save_cache(self, cache_key: str, data: Dict):
        """Save response to cache."""
        if self.cache_dir is None:
            return

        try:
            with open(self._cache_path(cache_key), "w") as f:
                json.dump({"timestamp": time.time(), "data": data}, f)
        except (OSError, TypeError) as e:
            logger.warning(f"Cache write failed for {cache_key}: {e}")

    async def request(
        self,
        endpoint: str,
        params: Dict[str, Any],
        use_cache: bool = True,
    ) -> Dict:
        """Make HTTP request with caching and rate limiting."""
        # POWER rejects unknown query params, so drop None values defensively
        params = {k: v for k, v in params.items() if v is not None}
        cache_key = self._cache_key(endpoint, params)

        if use_cache:
            cached = await self._get_cached(cache_key)
            if cached is not None:
                return cached

        await self._rate_limit()
        client = await self._get_client()
        base = self.BASE_URL.rstrip("/")
        url = f"{base}/{endpoint.lstrip('/')}" if endpoint.strip("/") else base

        try:
            response = await client.get(url, params=params)
            response.raise_for_status()

            try:
                data = response.json()
            except ValueError:
                logger.error(f"Non-JSON response: {response.text[:300]}")
                raise NASAAPIError(f"API returned non-JSON: {response.text[:200]}")

            # POWER reports problems inside a 200 JSON body
            msg = data.get("messages") or []
            if isinstance(msg, dict):
                msg = [msg]
            errors = [
                f"{m.get('severity')}: {m.get('message')}"
                for m in msg
                if isinstance(m, dict) and m.get("severity") == "ERROR"
            ]
            if errors:
                raise NASAAPIError("; ".join(errors))

            if use_cache:
                await self._save_cache(cache_key, data)

            return data
        except httpx.HTTPStatusError as e:
            logger.error(f"API error {e.response.status_code}: {e.response.text}")
            detail = None
            if e.response.content:
                try:
                    detail = e.response.json()
                except ValueError:
                    detail = None
            raise NASAAPIError(
                f"API request failed: {e.response.status_code}",
                status_code=e.response.status_code,
                response=detail,
            )
        except httpx.RequestError as e:
            logger.error(f"Request error: {e}")
            raise NASAAPIError(f"Request failed: {e}") from e
        except NASAAPIError:
            raise

    async def close(self):
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        self._client = None

    @abstractmethod
    async def fetch_climate_data(self, location: Location, start_date: str, end_date: str) -> Dict:
        """Fetch climate data for a location and date range."""
        pass