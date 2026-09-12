import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests

from config.settings import settings

logger = logging.getLogger(__name__)


class FivePaisaBroker:

    OAUTH_URL = (
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

    def __init__(self):

        self.connected = False
        self.access_token: Optional[str] = None
        self.client_code: Optional[str] = (
            settings.FIVEPAISA_CLIENT_CODE
        )

        # Token file
        self.token_file = (
            settings.DATA_DIR / "5paisa_token.json"
        )

        # Server start होते ही saved token check करें
        self.load_saved_token()

    # ---------------------------------------------------------
    # TOKEN SAVE
    # ---------------------------------------------------------

    def save_token(self):

        if not self.access_token:
            return

        token_data = {
            "access_token": self.access_token,
            "client_code": self.client_code,
            "saved_at": datetime.now().isoformat(),
            "expires_at": (
                datetime.now() + timedelta(hours=23)
            ).isoformat(),
        }

        try:

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
                    token_data,
                    file,
                    indent=2
                )

            logger.info(
                "5paisa access token saved locally."
            )

        except Exception as e:

            logger.error(
                f"Unable to save 5paisa token: {e}"
            )

    # ---------------------------------------------------------
    # TOKEN LOAD
    # ---------------------------------------------------------

    def load_saved_token(self):

        if not self.token_file.exists():

            logger.info(
                "No saved 5paisa token found."
            )

            return False

        try:

            with open(
                self.token_file,
                "r",
                encoding="utf-8"
            ) as file:

                token_data = json.load(file)

            access_token = token_data.get(
                "access_token"
            )

            client_code = token_data.get(
                "client_code"
            )

            expires_at = token_data.get(
                "expires_at"
            )

            if not access_token or not expires_at:

                logger.info(
                    "Saved 5paisa token is incomplete."
                )

                return False

            expiry_time = datetime.fromisoformat(
                expires_at
            )

            # Token expire हो चुका है
            if datetime.now() >= expiry_time:

                logger.info(
                    "Saved 5paisa token has expired."
                )

                self.delete_saved_token()

                return False

            self.access_token = access_token

            if client_code:
                self.client_code = str(
                    client_code
                )

            self.connected = True

            logger.info(
                "Saved 5paisa token loaded successfully."
            )

            return True

        except Exception as e:

            logger.error(
                f"Unable to load 5paisa token: {e}"
            )

            return False

    # ---------------------------------------------------------
    # TOKEN DELETE
    # ---------------------------------------------------------

    def delete_saved_token(self):

        try:

            if self.token_file.exists():
                self.token_file.unlink()

            self.access_token = None
            self.connected = False

            logger.info(
                "Saved 5paisa token deleted."
            )

        except Exception as e:

            logger.error(
                f"Unable to delete token: {e}"
            )

    # ---------------------------------------------------------
    # STATUS
    # ---------------------------------------------------------

    def configuration_status(self) -> Dict[str, bool]:

        return {

            "app_key": bool(
                settings.FIVEPAISA_APP_KEY
            ),

            "user_id": bool(
                settings.FIVEPAISA_USER_ID
            ),

            "encryption_key": bool(
                settings.FIVEPAISA_ENCRYPTION_KEY
            ),

            "vendor_key": bool(
                settings.FIVEPAISA_VENDOR_KEY
            ),

            "client_code": bool(
                settings.FIVEPAISA_CLIENT_CODE
            ),
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

            "VendorKey":
                settings.FIVEPAISA_VENDOR_KEY,

            "ResponseURL":
                settings.FIVEPAISA_REDIRECT_URL,

            "State":
                "trading-dashboard",
        }

        return (
            f"{self.OAUTH_URL}?"
            f"{urlencode(params)}"
        )

    # ---------------------------------------------------------
    # ACCESS TOKEN
    # ---------------------------------------------------------

    def exchange_request_token(
        self,
        request_token: str
    ) -> Dict[str, Any]:

        if not request_token:

            raise ValueError(
                "RequestToken is missing."
            )

        payload = {

            "head": {

                "Key":
                    settings.FIVEPAISA_APP_KEY
            },

            "body": {

                "RequestToken":
                    request_token,

                "EncryKey":
                    settings.FIVEPAISA_ENCRYPTION_KEY,

                "UserId":
                    settings.FIVEPAISA_USER_ID,
            },
        }

        response = requests.post(

            self.ACCESS_TOKEN_URL,

            json=payload,

            timeout=20,
        )

        response.raise_for_status()

        data = response.json()

        logger.info(
            "5paisa access-token response received."
        )

        body = data.get(
            "body",
            data
        )

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
                "5paisa access token was not returned."
            )

        self.access_token = access_token

        if client_code:

            self.client_code = str(
                client_code
            )

        self.connected = True

        # नया token local में save करें
        self.save_token()

        return {

            "connected": True,

            "client_code":
                self.client_code,

            "message":
                "5paisa login successful.",
        }

    # ---------------------------------------------------------
    # HEADERS
    # ---------------------------------------------------------

    def _headers(self) -> Dict[str, str]:

        if not self.access_token:

            raise RuntimeError(
                "5paisa is not connected. "
                "Login first."
            )

        return {

            "Content-Type":
                "application/json",

            "Authorization":
                f"Bearer {self.access_token}",
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

            raise RuntimeError(
                "5paisa is not connected."
            )

        exchange = exchange.upper()
        exchange_type = exchange_type.upper()

        url = (

            f"{self.HISTORICAL_URL}/"

            f"{exchange}/"

            f"{exchange_type}/"

            f"{int(scrip_code)}/"

            f"{interval}"
        )

        params = {

            "from":
                start_date,

            "end":
                end_date,
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
    # MARKET SNAPSHOT
    # ---------------------------------------------------------

    def get_quote(
        self,
        exchange: str,
        exchange_type: str,
        scrip_code: int,
    ):

        if not self.connected:

            raise RuntimeError(
                "5paisa is not connected."
            )

        url = (
            "https://Openapi.5paisa.com/"
            "VendorsAPI/Service1.svc/"
            "MarketSnapshot"
        )

        payload = {

            "head": {

                "key":
                    settings.FIVEPAISA_APP_KEY
            },

            "body": {

                "ClientCode":
                    self.client_code,

                "Data": [

                    {

                        "Exch":
                            exchange,

                        "ExchType":
                            exchange_type,

                        "ScripCode":
                            str(scrip_code),

                        "ScripData":
                            "",
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

    def subscribe_market_data(
        self,
        instruments
    ):

        logger.info(
            "Live market subscription will be "
            "connected through 5paisa WebSocket."
        )

    def unsubscribe_market_data(
        self,
        instruments
    ):

        logger.info(
            "Market unsubscribe requested."
        )

    # ---------------------------------------------------------
    # ORDER
    # ---------------------------------------------------------

    def place_order(
        self,
        *args,
        **kwargs
    ):

        raise NotImplementedError(
            "Orders are disabled. "
            "We will add Buy/Sell after "
            "market data is working."
        )


# ---------------------------------------------------------
# SHARED BROKER
# ---------------------------------------------------------

broker = FivePaisaBroker()
