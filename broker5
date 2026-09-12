import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import requests

from config.settings import settings


# =========================================================
# LOGGING
# =========================================================

logger = logging.getLogger(__name__)


# =========================================================
# 5PAISA BROKER
# =========================================================

class FivePaisaBroker:

    # -----------------------------------------------------
    # API URLs
    # -----------------------------------------------------

    OAUTH_LOGIN_URL = (
        "https://dev-openapi.5paisa.com/"
        "WebVendorLogin/VLogin/Index"
    )

    OAUTH_TOKEN_URL = (
        "https://openapi.5paisa.com/"
        "VendorsAPI/Service1.svc/"
        "GetAccessToken"
    )

    HISTORICAL_BASE_URL = (
        "https://openapi.5paisa.com/"
        "V2/historical"
    )

    MARKET_FEED_URL = (
        "https://openapi.5paisa.com/"
        "V1/MarketFeed"
    )

    MARKET_SNAPSHOT_URL = (
        "https://openapi.5paisa.com/"
        "V1/MarketSnapshot"
    )

    ORDER_URL = (
        "https://openapi.5paisa.com/"
        "V1/OrderRequest"
    )

    # -----------------------------------------------------
    # Constructor
    # -----------------------------------------------------

    def __init__(self):

        self.app_key = (
            settings.FIVEPAISA_APP_KEY
        )

        self.vendor_key = (
            settings.FIVEPAISA_VENDOR_KEY
        )

        self.user_id = (
            settings.FIVEPAISA_USER_ID
        )

        self.encryption_key = (
            settings.FIVEPAISA_ENCRYPTION_KEY
        )

        self.client_code = (
            settings.FIVEPAISA_CLIENT_CODE
        )

        self.redirect_url = (
            settings.FIVEPAISA_REDIRECT_URL
        )

        self.access_token: Optional[str] = None

        self.token_data: Dict[str, Any] = {}

        self.data_dir = (
            settings.DATA_DIR
        )

        self.token_file = (
            self.data_dir
            / "5paisa_token.json"
        )

        self.session = requests.Session()

        self.session.headers.update(
            {
                "User-Agent":
                    "TradingDashboard/1.0",
                "Accept":
                    "application/json",
                "Content-Type":
                    "application/json",
            }
        )

        self.load_token()

    # =====================================================
    # CONFIGURATION
    # =====================================================

    def configuration_status(self):

        return {
            "app_key": bool(
                self.app_key
            ),
            "user_id": bool(
                self.user_id
            ),
            "encryption_key": bool(
                self.encryption_key
            ),
            "vendor_key": bool(
                self.vendor_key
            ),
            "client_code": bool(
                self.client_code
            ),
        }

    # =====================================================
    # CONNECTED STATUS
    # =====================================================

    @property
    def connected(self) -> bool:

        return bool(
            self.access_token
        )

    # =====================================================
    # OAUTH LOGIN URL
    # =====================================================

    def get_oauth_login_url(self):

        if not self.vendor_key:
            raise ValueError(
                "FIVEPAISA_VENDOR_KEY is missing "
                "in .env"
            )

        if not self.redirect_url:
            raise ValueError(
                "FIVEPAISA_REDIRECT_URL is missing "
                "in .env"
            )

        params = {
            "VendorKey":
                self.vendor_key,
            "ResponseURL":
                self.redirect_url,
        }

        request = requests.Request(
            "GET",
            self.OAUTH_LOGIN_URL,
            params=params,
        )

        prepared = request.prepare()

        return prepared.url

    # =====================================================
    # TOKEN SAVE
    # =====================================================

    def save_token(
        self,
        token_data: Dict[str, Any],
    ):

        self.data_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        with open(
            self.token_file,
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                token_data,
                file,
                indent=2,
            )

        logger.info(
            "5paisa token saved."
        )

    # =====================================================
    # TOKEN LOAD
    # =====================================================

    def load_token(self):

        if not self.token_file.exists():

            return False

        try:

            with open(
                self.token_file,
                "r",
                encoding="utf-8",
            ) as file:

                data = json.load(file)

            if not isinstance(
                data,
                dict,
            ):

                return False

            self.token_data = data

            token = (
                data.get("access_token")
                or data.get("AccessToken")
                or data.get("accessToken")
                or data.get("Token")
            )

            if token:

                self.access_token = str(
                    token
                )

                logger.info(
                    "5paisa access token loaded."
                )

                return True

        except Exception as error:

            logger.warning(
                "Unable to load 5paisa token: %s",
                error,
            )

        return False

    # =====================================================
    # SET ACCESS TOKEN
    # =====================================================

    def set_access_token(
        self,
        access_token: str,
        client_code: Optional[str] = None,
    ):

        if not access_token:

            raise ValueError(
                "Access token cannot be empty."
            )

        self.access_token = str(
            access_token
        )

        if client_code:

            self.client_code = str(
                client_code
            )

        self.token_data = {
            "access_token":
                self.access_token,

            "client_code":
                self.client_code,

            "saved_at":
                __import__(
                    "datetime"
                ).datetime.now().isoformat(),
        }

        self.save_token(
            self.token_data
        )

    # =====================================================
    # AUTH HEADERS
    # =====================================================

    def _auth_headers(self):

        if not self.access_token:

            raise RuntimeError(
                "5paisa is not connected. "
                "Please login first."
            )

        return {
            "Authorization":
                f"Bearer {self.access_token}",

            "Accept":
                "application/json",

            "Content-Type":
                "application/json",
        }

    # =====================================================
    # GENERIC RESPONSE HANDLER
    # =====================================================

    def _handle_response(
        self,
        response: requests.Response,
    ):

        status_code = (
            response.status_code
        )

        try:

            data = response.json()

        except Exception:

            data = {
                "raw_text":
                    response.text
            }

        if not response.ok:

            raise RuntimeError(
                f"5paisa API HTTP {status_code}: "
                f"{data}"
            )

        return data

    # =====================================================
    # EXCHANGE REQUEST TOKEN
    # =====================================================

    def exchange_request_token(
        self,
        request_token: str,
    ):

        if not request_token:

            raise ValueError(
                "RequestToken is required."
            )

        # -------------------------------------------------
        # 5paisa OAuth session endpoint
        # -------------------------------------------------

        url = (
            self.OAUTH_TOKEN_URL
        )

        payload = {
            "RequestToken":
                request_token,

            "VendorKey":
                self.vendor_key,

            "EncryKey":
                self.encryption_key,

            "UserId":
                self.user_id,

            "ClientCode":
                self.client_code,
        }

        logger.info(
            "Requesting 5paisa access token."
        )

        try:

            response = self.session.post(
                url,
                json=payload,
                timeout=30,
            )

        except requests.RequestException as error:

            raise RuntimeError(
                f"5paisa token request failed: "
                f"{error}"
            ) from error

        data = self._handle_response(
            response
        )

        logger.debug(
            "5paisa token response received."
        )

        # -------------------------------------------------
        # Find access token recursively
        # -------------------------------------------------

        access_token = (
            self._find_value(
                data,
                [
                    "AccessToken",
                    "access_token",
                    "accessToken",
                    "Token",
                    "token",
                ],
            )
        )

        if not access_token:

            # Some responses may contain
            # the token in a nested body.
            raise RuntimeError(
                "5paisa did not return an "
                f"access token. Response: {data}"
            )

        access_token = str(
            access_token
        )

        self.access_token = (
            access_token
        )

        self.token_data = {
            "access_token":
                access_token,

            "client_code":
                self.client_code,

            "response":
                data,

            "saved_at":
                __import__(
                    "datetime"
                ).datetime.now().isoformat(),
        }

        self.save_token(
            self.token_data
        )

        return {
            "status":
                "success",

            "connected":
                True,

            "client_code":
                self.client_code,

            "access_token":
                access_token,
        }

    # =====================================================
    # FIND VALUE RECURSIVELY
    # =====================================================

    def _find_value(
        self,
        data: Any,
        keys,
    ):

        if isinstance(
            data,
            dict,
        ):

            for key in keys:

                if key in data:

                    value = data[key]

                    if value not in (
                        None,
                        "",
                    ):

                        return value

            for value in data.values():

                result = self._find_value(
                    value,
                    keys,
                )

                if result is not None:
                    return result

        elif isinstance(
            data,
            list,
        ):

            for item in data:

                result = self._find_value(
                    item,
                    keys,
                )

                if result is not None:
                    return result

        return None

    # =====================================================
    # HISTORICAL DATA
    # =====================================================

    def get_historical_data(
        self,
        exchange: str,
        exchange_type: str,
        scrip_code: int,
        interval: str,
        start_date: str,
        end_date: str,
    ):

        if not self.access_token:

            raise RuntimeError(
                "5paisa is not connected. "
                "Login before downloading "
                "historical data."
            )

        exchange = str(
            exchange
        ).upper()

        exchange_type = str(
            exchange_type
        ).upper()

        interval = str(
            interval
        ).lower()

        scrip_code = int(
            scrip_code
        )

        supported_intervals = {
            "1m",
            "5m",
            "10m",
            "15m",
            "30m",
            "60m",
            "1d",
        }

        if interval not in supported_intervals:

            raise ValueError(
                "Unsupported 5paisa historical "
                f"interval: {interval}"
            )

        url = (
            f"{self.HISTORICAL_BASE_URL}/"
            f"{exchange}/"
            f"{exchange_type}/"
            f"{scrip_code}/"
            f"{interval}"
        )

        params = {
            "from":
                start_date,

            "end":
                end_date,
        }

        logger.info(
            "5paisa historical request: "
            "%s %s %s %s %s -> %s",
            exchange,
            exchange_type,
            scrip_code,
            interval,
            start_date,
            end_date,
        )

        try:

            response = self.session.get(
                url,
                params=params,
                headers=self._auth_headers(),
                timeout=60,
            )

        except requests.RequestException as error:

            raise RuntimeError(
                "5paisa historical request "
                f"failed: {error}"
            ) from error

        return self._handle_response(
            response
        )

    # =====================================================
    # QUOTE / MARKET SNAPSHOT
    # =====================================================

    def get_quote(
        self,
        exchange: str,
        exchange_type: str,
        scrip_code: int,
    ):

        if not self.access_token:

            raise RuntimeError(
                "5paisa is not connected."
            )

        payload = [
            {
                "Exchange":
                    str(exchange).upper(),

                "ExchangeType":
                    str(exchange_type).upper(),

                "ScripCode":
                    int(scrip_code),
            }
        ]

        logger.info(
            "5paisa quote request: "
            "%s %s %s",
            exchange,
            exchange_type,
            scrip_code,
        )

        try:

            response = self.session.post(
                self.MARKET_SNAPSHOT_URL,
                headers=self._auth_headers(),
                json=payload,
                timeout=30,
            )

        except requests.RequestException as error:

            raise RuntimeError(
                "5paisa quote request failed: "
                f"{error}"
            ) from error

        return self._handle_response(
            response
        )

    # =====================================================
    # MARKET FEED
    # =====================================================

    def get_market_feed(
        self,
        instruments,
    ):

        if not self.access_token:

            raise RuntimeError(
                "5paisa is not connected."
            )

        if not isinstance(
            instruments,
            list,
        ):

            raise ValueError(
                "instruments must be a list."
            )

        payload = {
            "head": {
                "key":
                    self.access_token,
            },

            "body": {
                "MarketFeedData":
                    instruments,
            },
        }

        try:

            response = self.session.post(
                self.MARKET_FEED_URL,
                headers=self._auth_headers(),
                json=payload,
                timeout=30,
            )

        except requests.RequestException as error:

            raise RuntimeError(
                "5paisa market feed request "
                f"failed: {error}"
            ) from error

        return self._handle_response(
            response
        )

    # =====================================================
    # ORDER PLACE
    # =====================================================

    def place_order(
        self,
        exchange: str,
        exchange_type: str,
        scrip_code: int,
        quantity: int,
        order_type: str,
        price: float = 0,
        is_intraday: bool = True,
        remote_order_id: str = "",
    ):

        if not settings.ORDERS_ENABLED:

            raise RuntimeError(
                "Orders are currently disabled. "
                "Set ORDERS_ENABLED=true in .env "
                "only after the market-data system "
                "has been verified."
            )

        if not settings.TRADING_ENABLED:

            raise RuntimeError(
                "Trading is currently disabled. "
                "Set TRADING_ENABLED=true in .env "
                "only when you are ready for live trading."
            )

        if not self.access_token:

            raise RuntimeError(
                "5paisa is not connected."
            )

        exchange = str(
            exchange
        ).upper()

        exchange_type = str(
            exchange_type
        ).upper()

        order_type = str(
            order_type
        ).upper()

        if order_type not in {
            "BUY",
            "SELL",
        }:

            raise ValueError(
                "order_type must be BUY or SELL."
            )

        quantity = int(
            quantity
        )

        if quantity <= 0:

            raise ValueError(
                "Quantity must be greater than zero."
            )

        # -------------------------------------------------
        # This payload follows the 5paisa order structure.
        # Live order execution remains protected by the
        # TRADING_ENABLED + ORDERS_ENABLED switches.
        # -------------------------------------------------

        payload = {
            "head": {
                "key":
                    self.access_token,
            },

            "body": {
                "Exchange":
                    exchange,

                "ExchangeType":
                    exchange_type,

                "ScripCode":
                    int(scrip_code),

                "OrderType":
                    order_type,

                "Qty":
                    quantity,

                "DisQty":
                    0,

                "Price":
                    float(price),

                "StopLossPrice":
                    0,

                "IsIntraday":
                    bool(is_intraday),

                "iOrderValidity":
                    "0",

                "RemoteOrderID":
                    remote_order_id,
            },
        }

        logger.warning(
            "LIVE ORDER REQUEST: %s",
            payload,
        )

        try:

            response = self.session.post(
                self.ORDER_URL,
                headers=self._auth_headers(),
                json=payload,
                timeout=30,
            )

        except requests.RequestException as error:

            raise RuntimeError(
                "5paisa order request failed: "
                f"{error}"
            ) from error

        return self._handle_response(
            response
        )

    # =====================================================
    # ORDER BOOK
    # =====================================================

    def get_order_book(self):

        if not self.access_token:

            raise RuntimeError(
                "5paisa is not connected."
            )

        raise NotImplementedError(
            "Order book endpoint will be enabled "
            "with the live trading module."
        )

    # =====================================================
    # POSITIONS
    # =====================================================

    def get_positions(self):

        if not self.access_token:

            raise RuntimeError(
                "5paisa is not connected."
            )

        raise NotImplementedError(
            "Positions endpoint will be enabled "
            "with the live trading module."
        )

    # =====================================================
    # HOLDINGS
    # =====================================================

    def get_holdings(self):

        if not self.access_token:

            raise RuntimeError(
                "5paisa is not connected."
            )

        raise NotImplementedError(
            "Holdings endpoint will be enabled "
            "with the account module."
        )


# =========================================================
# GLOBAL BROKER INSTANCE
# =========================================================

broker = FivePaisaBroker()
