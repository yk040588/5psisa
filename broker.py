"""
broker.py

5paisa / Xstream broker integration layer.

This file is responsible for:
    - Broker configuration
    - Authentication/session handling
    - Market-data connection setup
    - Future order integration
    - Keeping broker-specific code separate from the rest of the app

IMPORTANT:
    API credentials must be stored in .env, never directly in this file.
"""

import os
import logging
from typing import Any, Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class BrokerError(Exception):
    """Raised when a broker operation fails."""
    pass


class FivePaisaBroker:
    """
    Wrapper around the 5paisa/Xstream API.

    The exact SDK/API calls should be added after we confirm the
    current Xstream API authentication and market-data interface.
    """

    def __init__(self):
        self.app_name = os.getenv("FIVEPAISA_APP_NAME")
        self.user_id = os.getenv("FIVEPAISA_USER_ID")
        self.password = os.getenv("FIVEPAISA_PASSWORD")
        self.user_key = os.getenv("FIVEPAISA_USER_KEY")
        self.encryption_key = os.getenv("FIVEPAISA_ENCRYPTION_KEY")

        self.client = None
        self.access_token: Optional[str] = None
        self.connected = False

    # ---------------------------------------------------------
    # Configuration
    # ---------------------------------------------------------

    def configuration_status(self) -> dict[str, bool]:
        """
        Check whether the required broker configuration exists.

        Does NOT return the actual credentials.
        """

        return {
            "app_name": bool(self.app_name),
            "user_id": bool(self.user_id),
            "password": bool(self.password),
            "user_key": bool(self.user_key),
            "encryption_key": bool(self.encryption_key),
        }

    # ---------------------------------------------------------
    # Authentication
    # ---------------------------------------------------------

    def login(self) -> bool:
        """
        Authenticate with 5paisa/Xstream.

        The actual login implementation will be connected here
        once the current Xstream authentication flow is configured.
        """

        required = self.configuration_status()

        missing = [
            name
            for name, available in required.items()
            if not available
        ]

        if missing:
            raise BrokerError(
                "Missing broker configuration: "
                + ", ".join(missing)
            )

        # TODO:
        # Initialize the official 5paisa/Xstream client here.
        #
        # Example structure:
        #
        # self.client = ...
        # response = self.client.login(...)
        # self.access_token = ...
        #
        # Do not hard-code credentials.

        logger.info("Broker configuration found.")

        self.connected = True

        return True

    # ---------------------------------------------------------
    # Connection
    # ---------------------------------------------------------

    def is_connected(self) -> bool:
        """Return current broker connection status."""
        return self.connected

    def disconnect(self) -> None:
        """Close the broker connection/session."""

        self.client = None
        self.access_token = None
        self.connected = False

        logger.info("Broker disconnected.")

    # ---------------------------------------------------------
    # Market Data
    # ---------------------------------------------------------

    def get_quote(
        self,
        exchange: str,
        symbol: str,
    ) -> dict[str, Any]:
        """
        Get the latest quote for an instrument.

        This will eventually be called by market_data.py.
        """

        if not self.connected:
            raise BrokerError(
                "Broker is not connected. Call login() first."
            )

        # TODO:
        # Replace with actual Xstream quote API call.

        return {
            "exchange": exchange,
            "symbol": symbol,
            "ltp": None,
            "open": None,
            "high": None,
            "low": None,
            "close": None,
            "volume": None,
        }

    # ---------------------------------------------------------
    # Historical Data
    # ---------------------------------------------------------

    def get_historical_data(
        self,
        exchange: str,
        symbol: str,
        interval: str,
        start_date: str,
        end_date: str,
    ) -> list[dict[str, Any]]:
        """
        Get historical OHLC candle data.

        Used to initially populate the three charts before
        live WebSocket data begins.
        """

        if not self.connected:
            raise BrokerError(
                "Broker is not connected. Call login() first."
            )

        # TODO:
        # Connect this to the actual Xstream historical-data API.

        return []

    # ---------------------------------------------------------
    # WebSocket / Live Feed
    # ---------------------------------------------------------

    async def subscribe_market_data(
        self,
        instruments: list[dict[str, Any]],
    ) -> None:
        """
        Subscribe to live market data.

        instruments will eventually contain the Future,
        selected Call and selected Put contracts.
        """

        if not self.connected:
            raise BrokerError(
                "Broker is not connected. Call login() first."
            )

        # TODO:
        # Connect to Xstream WebSocket/feed.
        #
        # Expected flow:
        #
        # 5paisa/Xstream
        #       ↓
        # broker.py
        #       ↓
        # market_data.py
        #       ↓
        # websocket_manager.py
        #       ↓
        # browser

        logger.info(
            "Market-data subscription requested for %d instruments.",
            len(instruments),
        )

    async def unsubscribe_market_data(
        self,
        instruments: list[dict[str, Any]],
    ) -> None:
        """Unsubscribe instruments from the live market feed."""

        if not self.connected:
            return

        # TODO: Implement Xstream unsubscribe.
        logger.info(
            "Market-data unsubscribe requested for %d instruments.",
            len(instruments),
        )

    # ---------------------------------------------------------
    # Orders - DISABLED FOR FIRST VERSION
    # ---------------------------------------------------------

    def place_order(self, order: dict[str, Any]) -> dict[str, Any]:
        """
        Place an order through the broker.

        NOT USED IN THE FIRST VERSION.

        Buy/Sell will be added later after the live
        market-data dashboard is working correctly.
        """

        raise NotImplementedError(
            "Order placement is disabled in the first version."
        )

    # ---------------------------------------------------------
    # Debug / Status
    # ---------------------------------------------------------

    def status(self) -> dict[str, Any]:
        """Return safe broker status information."""

        return {
            "connected": self.connected,
            "credentials_configured": any(
                self.configuration_status().values()
            ),
            "orders_enabled": False,
        }


# -------------------------------------------------------------
# Shared broker instance
# -------------------------------------------------------------

broker = FivePaisaBroker()
