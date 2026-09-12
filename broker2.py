from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

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
        "https://openapi.5paisa.com/V1/MarketFeed"
    )

    MARKET_SNAPSHOT_URL = (
        "https://openapi.5paisa.com/V1/MarketSnapshot"
    )

    ORDER_URL = (
        "https://openapi.5paisa.com/V1/OrderRequest"
    )

    def __init__(self):

        self.token_file = (
            settings.DATA_DIR / "5paisa_token.json"
        )

        self.access_token = None
        self._load_token()

    # ---------------------------------------------------------
    # TOKEN
    # ---------------------------------------------------------

    def _load_token(self):

        if not self.token_file.exists():
            return

        try:

            data = json.loads(
                self.token_file.read_text(
                    encoding="utf-8"
                )
            )

            self.access_token = (
                data.get("access_token")
                or data.get("AccessToken")
            )

        except Exception as exc:
            print(f"[BROKER] Token load error: {exc}")

    def _save_token(self, token):

        self.access_token = token

        self.token_file.write_text(
            json.dumps(
                {
                    "access_token": token,
                    "saved_at": datetime.now().isoformat(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    # ---------------------------------------------------------
    # LOGIN
    # ---------------------------------------------------------

    def get_login_url(self):

        return (
            f"{self.LOGIN_URL}"
            f"?VendorKey={settings.FIVEPAISA_VENDOR_KEY}"
            f"&ResponseType=code"
            f"&RedirectURI={settings.FIVEPAISA_REDIRECT_URL}"
            f"&State=5paisa_dashboard"
        )

    def exchange_token(self, code: str):

        payload = {
            "head": {
                "key": settings.FIVEPAISA_APP_KEY,
            },
            "body": {
                "RequestToken": code,
                "EncryKey": settings.FIVEPAISA_ENCRYPTION_KEY,
                "VendorKey": settings.FIVEPAISA_VENDOR_KEY,
            },
        }

        response = requests.post(
            self.TOKEN_URL,
            json=payload,
            timeout=30,
        )

        response.raise_for_status()

        data = response.json()

        body = data.get("body", data)

        token = (
            body.get("AccessToken")
            or body.get("access_token")
        )

        if not token:
            raise RuntimeError(
                f"Access token not returned: {data}"
            )

        self._save_token(token)

        return {
            "success": True,
            "access_token_saved": True,
        }

    # ---------------------------------------------------------
    # AUTH HEADERS
    # ---------------------------------------------------------

    def _headers(self):

        if not self.access_token:
            raise RuntimeError(
                "5paisa access token not available"
            )

        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    # ---------------------------------------------------------
    # HISTORICAL
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

        url = (
            f"{self.HISTORICAL_URL}/"
            f"{exchange}/"
            f"{exchange_type}/"
            f"{scrip_code}/"
            f"{interval}"
        )

        response = requests.get(
            url,
            headers=self._headers(),
            params={
                "from": start_date,
                "end": end_date,
            },
            timeout=30,
        )

        response.raise_for_status()

        return response.json()

    # ---------------------------------------------------------
    # QUOTE
    # ---------------------------------------------------------

    def get_quote(
        self,
        exchange: str,
        exchange_type: str,
        scrip_code: int,
    ):

        payload = [
            {
                "Exchange": exchange,
                "ExchangeType": exchange_type,
                "ScripCode": int(scrip_code),
            }
        ]

        response = requests.post(
            self.MARKET_SNAPSHOT_URL,
            headers=self._headers(),
            json=payload,
            timeout=15,
        )

        response.raise_for_status()

        return response.json()

    # ---------------------------------------------------------
    # MARKET FEED
    # ---------------------------------------------------------

    def get_market_feed(self, instruments):

        payload = {
            "head": {
                "key": self.access_token,
            },
            "body": {
                "MarketFeedData": instruments,
            },
        }

        response = requests.post(
            self.MARKET_FEED_URL,
            headers={
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=15,
        )

        response.raise_for_status()

        return response.json()

    # ---------------------------------------------------------
    # ORDER
    # ---------------------------------------------------------

    def place_order(
        self,
        exchange: str,
        exchange_type: str,
        scrip_code: int,
        quantity: int,
        buy_sell: str,
        price: float = 0,
        order_type: str = "MARKET",
    ):

        if not settings.TRADING_ENABLED:
            raise RuntimeError(
                "TRADING_ENABLED=false"
            )

        if not settings.ORDERS_ENABLED:
            raise RuntimeError(
                "ORDERS_ENABLED=false"
            )

        payload = {
            "head": {
                "key": self.access_token,
            },
            "body": {
                "ClientCode": settings.FIVEPAISA_CLIENT_CODE,
                "Exchange": exchange,
                "ExchangeType": exchange_type,
                "ScripCode": int(scrip_code),
                "BuySell": buy_sell.upper(),
                "Qty": int(quantity),
                "OrderType": order_type,
                "Price": float(price),
            },
        }

        response = requests.post(
            self.ORDER_URL,
            headers=self._headers(),
            json=payload,
            timeout=20,
        )

        response.raise_for_status()

        return response.json()


broker = FivePaisaBroker()
