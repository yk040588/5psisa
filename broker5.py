#broker/py


from __future__ import annotations

import json
from datetime import datetime, timedelta

import requests

from config.settings import settings


class FivePaisaBroker:

    LOGIN_URL = (
        "https://dev-openapi.5paisa.com/"
        "WebVendorLogin/VLogin/Index"
    )

    TOKEN_URL = (
        "https://openapi.5paisa.com/"
        "VendorsAPI/Service1.svc/GetAccessToken"
    )

    HISTORICAL_URL = (
        "https://openapi.5paisa.com/V2/historical"
    )

    MARKET_FEED_URL = (
        "https://openapi.5paisa.com/"
        "VendorsAPI/Service1.svc/V1/MarketFeed"
    )

    MARKET_SNAPSHOT_URL = (
        "https://openapi.5paisa.com/"
        "VendorsAPI/Service1.svc/MarketSnapshot"
    )

    ORDER_URL = (
        "https://openapi.5paisa.com/V1/OrderRequest"
    )

    def __init__(self):
        self.access_token = None

        self.token_file = (
            settings.DATA_DIR / "5paisa_token.json"
        )

        self._load_token()

    # -------------------------------------------------
    # TOKEN
    # -------------------------------------------------

    def _load_token(self):
        try:
            if not self.token_file.exists():
                return

            with open(
                self.token_file,
                "r",
                encoding="utf-8"
            ) as file:
                data = json.load(file)

            self.access_token = data.get(
                "access_token"
            )

        except Exception:
            self.access_token = None

    def _save_token(self, token: str):
        self.token_file.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with open(
            self.token_file,
            "w",
            encoding="utf-8"
        ) as file:
            json.dump(
                {
                    "access_token": token,
                    "saved_at": datetime.now().isoformat()
                },
                file,
                indent=2
            )

        self.access_token = token

    def get_login_url(self):
        return self.LOGIN_URL

    def exchange_token(
        self,
        request_token: str
    ):
        payload = {
            "head": {
                "key": settings.FIVEPAISA_APP_KEY
            },
            "body": {
                "RequestToken": request_token,
                "EncryKey": settings.FIVEPAISA_ENCRYPTION_KEY,
                "VendorKey": settings.FIVEPAISA_VENDOR_KEY
            }
        }

        response = requests.post(
            self.TOKEN_URL,
            json=payload,
            timeout=20
        )

        response.raise_for_status()

        data = response.json()

        token = None

        body = data.get("body", {})

        if isinstance(body, dict):
            token = (
                body.get("AccessToken")
                or body.get("access_token")
                or body.get("Token")
            )

        if not token:
            token = (
                data.get("AccessToken")
                or data.get("access_token")
            )

        if not token:
            raise RuntimeError(
                "5paisa access token not found in response"
            )

        self._save_token(token)

        return {
            "success": True,
            "access_token": token
        }

    # -------------------------------------------------
    # HEADERS
    # -------------------------------------------------

    def _headers(self):
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        if self.access_token:
            headers["Authorization"] = (
                f"Bearer {self.access_token}"
            )

        return headers

    # -------------------------------------------------
    # HISTORICAL DATA
    # -------------------------------------------------

    def get_historical_data(
        self,
        exchange: str,
        exchange_type: str,
        scrip_code: int,
        interval: str = "5m",
        from_date: str | None = None,
        end_date: str | None = None
    ):

        if not from_date:
            from_date = (
                datetime.now() - timedelta(days=5)
            ).strftime("%Y-%m-%d")

        if not end_date:
            end_date = datetime.now().strftime(
                "%Y-%m-%d"
            )

        url = (
            f"{self.HISTORICAL_URL}/"
            f"{exchange}/"
            f"{exchange_type}/"
            f"{int(scrip_code)}/"
            f"{interval}"
        )

        params = {
            "from": from_date,
            "end": end_date
        }

        response = requests.get(
            url,
            headers=self._headers(),
            params=params,
            timeout=20
        )

        response.raise_for_status()

        return response.json()

    # -------------------------------------------------
    # MARKET SNAPSHOT
    # -------------------------------------------------

    def get_quote(
        self,
        exchange: str,
        exchange_type: str,
        scrip_code: int
    ):

        payload = {
            "head": {
                "key": settings.FIVEPAISA_APP_KEY
            },
            "body": {
                "ClientCode": (
                    settings.FIVEPAISA_CLIENT_CODE
                ),
                "Data": [
                    {
                        "Exch": exchange,
                        "ExchType": exchange_type,
                        "ScripCode": int(scrip_code)
                    }
                ]
            }
        }

        response = requests.post(
            self.MARKET_SNAPSHOT_URL,
            headers=self._headers(),
            json=payload,
            timeout=15
        )

        response.raise_for_status()

        return response.json()

    # -------------------------------------------------
    # MARKET FEED
    # -------------------------------------------------

    def get_market_feed(
        self,
        instruments
    ):

        payload = {
            "head": {
                "key": settings.FIVEPAISA_APP_KEY
            },
            "body": {
                "ClientCode": (
                    settings.FIVEPAISA_CLIENT_CODE
                ),
                "MarketFeedData": instruments
            }
        }

        response = requests.post(
            self.MARKET_FEED_URL,
            headers=self._headers(),
            json=payload,
            timeout=15
        )

        response.raise_for_status()

        return response.json()

    # -------------------------------------------------
    # ORDER
    # -------------------------------------------------

    def place_order(
        self,
        exchange: str,
        exchange_type: str,
        scrip_code: int,
        buy_sell: str,
        quantity: int,
        order_type: str = "MARKET",
        price: float = 0
    ):

        if not settings.TRADING_ENABLED:
            raise RuntimeError(
                "Trading is disabled in settings"
            )

        if not settings.ORDERS_ENABLED:
            raise RuntimeError(
                "Orders are disabled in settings"
            )

        payload = {
            "head": {
                "key": settings.FIVEPAISA_APP_KEY
            },
            "body": {
                "ClientCode": (
                    settings.FIVEPAISA_CLIENT_CODE
                ),
                "Exchange": exchange,
                "ExchangeType": exchange_type,
                "ScripCode": int(scrip_code),
                "BuySell": buy_sell,
                "Qty": int(quantity),
                "OrderType": order_type,
                "Price": float(price)
            }
        }

        response = requests.post(
            self.ORDER_URL,
            headers=self._headers(),
            json=payload,
            timeout=20
        )

        response.raise_for_status()

        return response.json()


broker = FivePaisaBroker()
