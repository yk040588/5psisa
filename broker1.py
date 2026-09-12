import logging
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests

from config.settings import settings

logger = logging.getLogger(__name__)


class FivePaisaBroker:
    OAUTH_URL = "https://dev-openapi.5paisa.com/WebVendorLogin/VLogin/Index"
    ACCESS_TOKEN_URL = (
        "https://Openapi.5paisa.com/VendorsAPI/Service1.svc/GetAccessToken"
    )
    HISTORICAL_URL = "https://openapi.5paisa.com/V2/historical"

    def __init__(self):
        self.connected = False
        self.access_token: Optional[str] = None
        self.client_code: Optional[str] = settings.FIVEPAISA_CLIENT_CODE

    # ---------------------------------------------------------
    # STATUS
    # ---------------------------------------------------------

    def configuration_status(self) -> Dict[str, bool]:
        return {
            "app_key": bool(settings.FIVEPAISA_APP_KEY),
            "user_id": bool(settings.FIVEPAISA_USER_ID),
            "encryption_key": bool(settings.FIVEPAISA_ENCRYPTION_KEY),
            "vendor_key": bool(settings.FIVEPAISA_VENDOR_KEY),
            "client_code": bool(settings.FIVEPAISA_CLIENT_CODE),
        }

    def is_configured(self) -> bool:
        status = self.configuration_status()

        return (
            status["app_key"]
            and status["user_id"]
            and status["encryption_key"]
            and status["vendor_key"]
        )

    # ---------------------------------------------------------
    # OAUTH LOGIN
    # ---------------------------------------------------------

    def get_oauth_login_url(self) -> str:
        if not self.is_configured():
            raise RuntimeError(
                "5paisa credentials are incomplete. "
                "Check .env configuration."
            )

        params = {
            "VendorKey": settings.FIVEPAISA_VENDOR_KEY,
            "ResponseURL": settings.FIVEPAISA_REDIRECT_URL,
            "State": "trading-dashboard",
        }

        return f"{self.OAUTH_URL}?{urlencode(params)}"

    # ---------------------------------------------------------
    # ACCESS TOKEN
    # ---------------------------------------------------------

    def exchange_request_token(self, request_token: str) -> Dict[str, Any]:

        if not request_token:
            raise ValueError("RequestToken is missing.")

        payload = {
            "head": {
                "Key": settings.FIVEPAISA_APP_KEY
            },
            "body": {
                "RequestToken": request_token,
                "EncryKey": settings.FIVEPAISA_ENCRYPTION_KEY,
                "UserId": settings.FIVEPAISA_USER_ID,
            },
        }

        response = requests.post(
            self.ACCESS_TOKEN_URL,
            json=payload,
            timeout=20,
        )

        response.raise_for_status()

        data = response.json()

        logger.info("5paisa access-token response received.")

        body = data.get("body", data)

        access_token = (
            body.get("AccessToken")
            or body.get("access_token")
            or body.get("accessToken")
        )

        client_code = (
            body.get("ClientCode")
            or body.get("clientCode")
            or body.get("Clientcode")
        )

        if not access_token:
            raise RuntimeError(
                f"5paisa access token was not returned: {data}"
            )

        self.access_token = access_token

        if client_code:
            self.client_code = str(client_code)

        self.connected = True

        return {
            "connected": True,
            "client_code": self.client_code,
            "message": "5paisa login successful.",
        }

    # ---------------------------------------------------------
    # HEADERS
    # ---------------------------------------------------------

    def _headers(self) -> Dict[str, str]:

        if not self.access_token:
            raise RuntimeError(
                "5paisa is not connected. Login first."
            )

        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}",
        }

    # ---------------------------------------------------------
    # HISTORICAL DATA
    # ---------------------------------------------------------

    def get_historical_data(
        self,
        exchange: str,
        exchange_type: str,
        scrip_code: int,
        interval: str,
        start_date: str,
        end_date: str,
    ):

        if not self.connected:
            raise RuntimeError("5paisa is not connected.")

        exchange = exchange.upper()
        exchange_type = exchange_type.upper()

        # Historical API expects lower-case segment in URL.
        url = (
            f"{self.HISTORICAL_URL}/"
            f"{exchange}/"
            f"{exchange_type}/"
            f"{int(scrip_code)}/"
            f"{interval}"
        )

        params = {
            "from": start_date,
            "end": end_date,
        }

        response = requests.get(
            url,
            headers=self._headers(),
            params=params,
            timeout=30,
        )

        response.raise_for_status()

        return response.json()

    # ---------------------------------------------------------
    # MARKET FEED / QUOTE
    # ---------------------------------------------------------

    def get_quote(
        self,
        exchange: str,
        exchange_type: str,
        scrip_code: int,
    ):

        if not self.connected:
            raise RuntimeError("5paisa is not connected.")

        url = (
            "https://Openapi.5paisa.com/"
            "VendorsAPI/Service1.svc/MarketSnapshot"
        )

        payload = {
            "head": {
                "key": settings.FIVEPAISA_APP_KEY
            },
            "body": {
                "ClientCode": self.client_code,
                "Data": [
                    {
                        "Exch": exchange,
                        "ExchType": exchange_type,
                        "ScripCode": str(scrip_code),
                        "ScripData": "",
                    }
                ],
            },
        }

        response = requests.post(
            url,
            headers=self._headers(),
            json=payload,
            timeout=20,
        )

        response.raise_for_status()

        return response.json()

    # ---------------------------------------------------------
    # MARKET SUBSCRIPTION
    # ---------------------------------------------------------

    def subscribe_market_data(self, instruments):
        logger.info(
            "Live market subscription will be connected "
            "through 5paisa WebSocket."
        )

    def unsubscribe_market_data(self, instruments):
        logger.info("Market unsubscribe requested.")

    # ---------------------------------------------------------
    # ORDER
    # ---------------------------------------------------------

    def place_order(self, *args, **kwargs):
        raise NotImplementedError(
            "Orders are disabled. We will add Buy/Sell after "
            "market data is working."
        )


broker = FivePaisaBroker()
