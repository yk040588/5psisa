```python
"""
5paisa Xstream Broker Integration
Phase 1

Responsibilities:
- OAuth login URL
- RequestToken -> AccessToken exchange
- Access-token persistence
- Historical candle data
- MarketSnapshot quote
- Broker connection status

Phase 1 intentionally does NOT place orders.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlencode

import requests

from config.settings import settings


logger = logging.getLogger(__name__)


class FivePaisaBroker:
    """5paisa Xstream API wrapper for Phase 1."""

    OAUTH_LOGIN_URL = (
        "https://dev-openapi.5paisa.com/"
        "WebVendorLogin/VLogin/Index"
    )

    ACCESS_TOKEN_URL = (
        "https://Openapi.5paisa.com/"
        "VendorsAPI/Service1.svc/GetAccessToken"
    )

    HISTORICAL_URL = (
        "https://openapi.5paisa.com/V2/historical"
    )

    MARKET_SNAPSHOT_URL = (
        "https://Openapi.5paisa.com/"
        "V1/MarketSnapshot"
    )

    def __init__(self) -> None:
        self.connected: bool = False
        self.access_token: Optional[str] = None

        self.client_code: Optional[str] = getattr(
            settings,
            "FIVEPAISA_CLIENT_CODE",
            None,
        )

        self.token_file: Path = (
            Path(settings.DATA_DIR) / "5paisa_token.json"
        )

        self.session = requests.Session()

        self.load_saved_token()

    # =========================================================
    # CONFIGURATION
    # =========================================================

    def configuration_status(self) -> dict[str, Any]:
        """Return broker configuration status without exposing secrets."""

        return {
            "app_key": bool(
                getattr(settings, "FIVEPAISA_APP_KEY", "")
            ),
            "user_id": bool(
                getattr(settings, "FIVEPAISA_USER_ID", "")
            ),
            "encryption_key": bool(
                getattr(settings, "FIVEPAISA_ENCRYPTION_KEY", "")
            ),
            "vendor_key": bool(
                getattr(settings, "FIVEPAISA_VENDOR_KEY", "")
            ),
            "client_code": bool(
                getattr(settings, "FIVEPAISA_CLIENT_CODE", "")
            ),
        }

    def is_configured(self) -> bool:
        """Check whether required OAuth credentials are available."""

        required = [
            getattr(settings, "FIVEPAISA_APP_KEY", ""),
            getattr(settings, "FIVEPAISA_USER_ID", ""),
            getattr(settings, "FIVEPAISA_ENCRYPTION_KEY", ""),
            getattr(settings, "FIVEPAISA_VENDOR_KEY", ""),
        ]

        return all(bool(value) for value in required)

    # =========================================================
    # OAUTH LOGIN
    # =========================================================

    def get_oauth_login_url(self) -> str:
        """
        Build the official 5paisa OAuth login URL.

        User opens this URL in browser and completes login.
        5paisa then redirects to the configured ResponseURL
        with a RequestToken.
        """

        if not self.is_configured():
            raise RuntimeError(
                "5paisa OAuth configuration is incomplete."
            )

        vendor_key = getattr(
            settings,
            "FIVEPAISA_VENDOR_KEY",
            "",
        )

        redirect_url = getattr(
            settings,
            "FIVEPAISA_REDIRECT_URL",
            "http://127.0.0.1:8000/api/auth/callback",
        )

        state = getattr(
            settings,
            "FIVEPAISA_OAUTH_STATE",
            "trading-dashboard",
        )

        params = {
            "VendorKey": vendor_key,
            "ResponseURL": redirect_url,
            "State": state,
        }

        return f"{self.OAUTH_LOGIN_URL}?{urlencode(params)}"

    # =========================================================
    # REQUEST TOKEN -> ACCESS TOKEN
    # =========================================================

    def exchange_request_token(
        self,
        request_token: str,
    ) -> dict[str, Any]:
        """
        Exchange the OAuth RequestToken for an AccessToken.
        """

        if not request_token:
            raise ValueError("RequestToken is required.")

        payload = {
            "head": {
                "Key": getattr(
                    settings,
                    "FIVEPAISA_APP_KEY",
                    "",
                )
            },
            "body": {
                "RequestToken": request_token,
                "EncryKey": getattr(
                    settings,
                    "FIVEPAISA_ENCRYPTION_KEY",
                    "",
                ),
                "UserId": getattr(
                    settings,
                    "FIVEPAISA_USER_ID",
                    "",
                ),
            },
        }

        response = self.session.post(
            self.ACCESS_TOKEN_URL,
            json=payload,
            timeout=30,
        )

        response.raise_for_status()

        data = response.json()

        body = data.get("body", data)

        access_token = (
            body.get("AccessToken")
            or body.get("access_token")
            or body.get("Token")
        )

        client_code = (
            body.get("ClientCode")
            or body.get("ClientCodeId")
            or body.get("client_code")
        )

        if not access_token:
            raise RuntimeError(
                f"5paisa did not return AccessToken: {data}"
            )

        self.access_token = access_token
        self.connected = True

        if client_code:
            self.client_code = str(client_code)

        self.save_token()

        return {
            "success": True,
            "connected": True,
            "client_code": self.client_code,
            "access_token_received": True,
        }

    # =========================================================
    # TOKEN STORAGE
    # =========================================================

    def save_token(self) -> None:
        """Save access token locally."""

        if not self.access_token:
            return

        self.token_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        saved_at = datetime.now()

        token_data = {
            "access_token": self.access_token,
            "client_code": self.client_code,
            "saved_at": saved_at.isoformat(),
            "expires_at": (
                saved_at + timedelta(hours=23)
            ).isoformat(),
        }

        self.token_file.write_text(
            json.dumps(
                token_data,
                indent=2,
            ),
            encoding="utf-8",
        )

    def load_saved_token(self) -> bool:
        """Load previously saved token if it is still usable."""

        if not self.token_file.exists():
            return False

        try:
            data = json.loads(
                self.token_file.read_text(
                    encoding="utf-8"
                )
            )

            access_token = data.get("access_token")

            if not access_token:
                return False

            expires_at_raw = data.get("expires_at")

            if expires_at_raw:
                expires_at = datetime.fromisoformat(
                    expires_at_raw
                )

                if datetime.now() >= expires_at:
                    self.delete_saved_token()
                    return False

            self.access_token = access_token

            saved_client_code = data.get("client_code")

            if saved_client_code:
                self.client_code = str(
                    saved_client_code
                )

            self.connected = True

            logger.info(
                "5paisa saved access token loaded."
            )

            return True

        except Exception:
            logger.exception(
                "Unable to load saved 5paisa token."
            )

            self.access_token = None
            self.connected = False

            return False

    def delete_saved_token(self) -> None:
        """Delete locally stored token."""

        self.access_token = None
        self.connected = False

        try:
            if self.token_file.exists():
                self.token_file.unlink()
        except Exception:
            logger.exception(
                "Unable to delete saved 5paisa token."
            )

    # =========================================================
    # AUTHENTICATION
    # =========================================================

    def require_connection(self) -> None:
        """Raise an error when broker connection is unavailable."""

        if not self.access_token:
            self.connected = False

            raise RuntimeError(
                "5paisa is not connected. "
                "Complete OAuth login first."
            )

    def _headers(self) -> dict[str, str]:
        """Headers used by authenticated APIs."""

        self.require_connection()

        return {
            "Authorization": (
                f"Bearer {self.access_token}"
            ),
            "Content-Type": "application/json",
        }

    # =========================================================
    # HISTORICAL DATA
    # =========================================================

    def get_historical_data(
        self,
        exchange: str,
        exchange_type: str,
        scrip_code: int | str,
        interval: str,
        from_date: str,
        end_date: str,
    ) -> Any:
        """
        Fetch historical candles from 5paisa.

        Official format:

        /V2/historical/
        {Exch}/{ExchType}/{ScripCode}/{Interval}
        ?from=...&end=...
        """

        self.require_connection()

        url = (
            f"{self.HISTORICAL_URL}/"
            f"{exchange}/"
            f"{exchange_type}/"
            f"{scrip_code}/"
            f"{interval}"
        )

        params = {
            "from": from_date,
            "end": end_date,
        }

        response = self.session.get(
            url,
            params=params,
            headers=self._headers(),
            timeout=30,
        )

        response.raise_for_status()

        return response.json()

    # =========================================================
    # MARKET SNAPSHOT
    # =========================================================

    def get_quote(
        self,
        exchange: str,
        exchange_type: str,
        scrip_code: int | str,
        scrip_data: str = "",
    ) -> Any:
        """
        Get current quote using 5paisa MarketSnapshot.
        """

        self.require_connection()

        if not self.client_code:
            raise RuntimeError(
                "5paisa ClientCode is not available."
            )

        payload = {
            "head": {
                "key": getattr(
                    settings,
                    "FIVEPAISA_APP_KEY",
                    "",
                )
            },
            "body": {
                "ClientCode": self.client_code,
                "Data": [
                    {
                        "Exch": exchange,
                        "ExchType": exchange_type,
                        "ScripCode": int(scrip_code),
                        "ScripData": scrip_data,
                    }
                ],
            },
        }

        response = self.session.post(
            self.MARKET_SNAPSHOT_URL,
            json=payload,
            headers=self._headers(),
            timeout=15,
        )

        response.raise_for_status()

        return response.json()

    # =========================================================
    # MARKET FEED PLACEHOLDERS
    # =========================================================

    def subscribe_market_data(
        self,
        instruments: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        MarketFeedV3 subscription is handled by
        websocket_manager.py.

        This method exists only as a compatibility interface.
        """

        return {
            "success": True,
            "handled_by": "websocket_manager",
            "count": len(instruments),
        }

    def unsubscribe_market_data(
        self,
        instruments: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Compatibility interface for WebSocket manager."""

        return {
            "success": True,
            "handled_by": "websocket_manager",
            "count": len(instruments),
        }

    # =========================================================
    # ORDER PLACEMENT
    # =========================================================

    def place_order(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Phase 1 safety lock.

        Order placement is intentionally disabled.
        """

        if not getattr(
            settings,
            "TRADING_ENABLED",
            False,
        ):
            raise RuntimeError(
                "Trading is disabled in Phase 1."
            )

        if not getattr(
            settings,
            "ORDERS_ENABLED",
            False,
        ):
            raise RuntimeError(
                "Order placement is disabled."
            )

        raise NotImplementedError(
            "Order placement is not implemented yet."
        )

    # =========================================================
    # STATUS
    # =========================================================

    def status(self) -> dict[str, Any]:
        """Return safe broker status."""

        return {
            "connected": self.connected,
            "access_token": bool(
                self.access_token
            ),
            "client_code": self.client_code,
            "configured": self.is_configured(),
            "configuration": self.configuration_status(),
            "orders_enabled": bool(
                getattr(
                    settings,
                    "ORDERS_ENABLED",
                    False,
                )
            ),
            "trading_enabled": bool(
                getattr(
                    settings,
                    "TRADING_ENABLED",
                    False,
                )
            ),
        }


# Shared broker instance
broker = FivePaisaBroker()
```
