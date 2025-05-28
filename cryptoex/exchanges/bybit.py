import asyncio
import time

# import uuid
import logging
from typing import Any, Dict, Callable, Tuple

from cryptoex._exchange import Exchange
from cryptoex._authentication import hmac_signature

from cryptoex.utils import build_message
from cryptoex.utils import get_timestamp
from cryptoex.utils import overrides
from cryptoex.exchanges.utils import (
    ExchangeMappings,
    ExchangeConfig,
    exchanges_config,
    ExchangeEndpoints,
    callback_mapper,
)
from cryptoex.exchanges.formatters.bybit import BybitFormatter

_logger = logging.getLogger(__name__)


class _BybitExchange(Exchange):

    def __init__(self, *, testnet: bool, demo: bool, config: ExchangeConfig, **kwargs):
        super().__init__(
            testnet=testnet,
            demo=demo,
            config=config,
            endpoints=ExchangeEndpoints.from_yaml("bybit.yml"),
            formatter=BybitFormatter,
            **kwargs,
        )
        self.mappings: ExchangeMappings = ExchangeMappings.from_yaml("bybit")
        self._previous_snapshot = {}

    @overrides(Exchange)
    def _private_headers(self, payload):
        """Generates the required parameters for REST authentication


        Parameters
        ----------
            signature: str
                The HMAC or RSA signature
            timestamp: int
                The current time
        """
        timestamp = get_timestamp()
        query_string = f"{timestamp}{self._key}{self._recv_window}{payload}"
        signature = hmac_signature(self._secret, query_string)
        return {
            "X-BAPI-API-KEY": self._key,
            "X-BAPI-SIGN-TYPE": "2",
            "X-BAPI-SIGN": signature,
            "X-BAPI-RECV-WINDOW": str(self._recv_window),
            "X-BAPI-TIMESTAMP": str(timestamp),
        }

    # +--------------+
    # + http methods +
    # +--------------+
    @overrides(Exchange)
    async def fetch_account_details(self, **kwargs):
        """Fetch account related data through REST API

        Parameters
        ----------

        kwargs: dict
            Contains the parameters corresponding to the endpoint.
            Mandatory are:
                -account_type: UNIFIED/CONTRACT/SPOT

        See
        ---

        https://bybit-exchange.github.io/docs/v5/account/wallet-balance
        https://bybit-exchange.github.io/docs/v5/account/account-info
        """
        response = await super().fetch_account_details(**kwargs)
        return response["result"]

    @overrides(Exchange)
    async def fetch_withdrawal_details(self, **kwargs):
        """Fetch account related data through REST API"""
        response = await super().fetch_withdrawal_details(**kwargs)
        return response["result"]

    @overrides(Exchange)
    async def fetch_wallet_details(self, **kwargs):
        """Fetch account related data through REST API"""
        response = await super().fetch_wallet_details(**kwargs)
        return response["result"]["wallets"]

    @overrides(Exchange)
    async def fetch_positions(self, **kwargs):
        """Fetch positions related data through REST API

        Parameters
        ----------

        kwargs: dict
            Contains the parameters corresponding to the endpoint.
            Mandatory are:
                - category: spot, linear, inverse, option

        See
        ---

        https://bybit-exchange.github.io/docs/v5/position
        """
        response = await super().fetch_positions(**kwargs)
        return response["result"]

    @overrides(Exchange)
    async def fetch_trading_fees(self, **kwargs):
        """Fetch trading fees data through REST API

        Parameters
        ----------

        kwargs: dict
            Contains the parameters corresponding to the endpoint.
            Mandatory are:
                - category: spot, linear, inverse, option
        See
        ---

        https://bybit-exchange.github.io/docs/v5/account/fee-rate
        """
        response = await super().fetch_trading_fees(**kwargs)
        return response["result"]

    @overrides(Exchange)
    async def fetch_server_time(self, **kwargs):
        """Get server time

        Parameters
        ----------
        kwargs: dict
            Contains the parameters corresponding to the endpoint.

        See
        ---

        https://bybit-exchange.github.io/docs/v5/market/time
        """
        response = await super().fetch_server_time(**kwargs)
        return response["result"]

    @overrides(Exchange)
    async def fetch_candlesticks(self, **kwargs):
        """Downloads candlesticks data

        Parameters
        ----------

        kwargs: dict
            Contains the parameters corresponding to the endpoint.
            Mandatory are:
                - category: spot, linear, inverse, option
                - symbol
                -bar_size: 1,3,5,15,30,60,120,240,360,720,D,M,W
        See
        ---

        https://bybit-exchange.github.io/docs/v5/market/kline
        """
        response = await super().fetch_candlesticks(**kwargs)
        return response["result"]

    @overrides(Exchange)
    async def fetch_orderbook(self, **kwargs):
        """Downloads orderbook data

        Parameters
        ----------

        kwargs: dict
            Contains the parameters corresponding to the endpoint.
            Mandatory are:
                - category: spot, linear, inverse, option
                - symbol

        See
        ---

        https://bybit-exchange.github.io/docs/v5/market/orderbook
        """
        response = await super().fetch_orderbook(**kwargs)
        return response["result"]

    @overrides(Exchange)
    async def fetch_all_instruments_details(self, **kwargs):
        """Downloads instruments data

        Parameters
        ----------

        kwargs: dict
            Contains the parameters corresponding to the endpoint.
        See
        ---

        https://bybit-exchange.github.io/docs/v5/market/instrument
        """
        requests = (
            self.fetch_instruments_details(category="spot"),
            self.fetch_instruments_details(category="linear", limit=1000),
            self.fetch_instruments_details(category="inverse", limit=1000),
            self.fetch_instruments_details(category="option", limit=1000),
        )
        return dict(
            zip(
                ["spot", "linear", "inverse", "option"],
                await asyncio.gather(*requests),
            )
        )

    @overrides(Exchange)
    async def fetch_instruments_details(self, **kwargs):
        """Downloads instruments data

        Parameters
        ----------

        kwargs: dict
            Contains the parameters corresponding to the endpoint.
            Mandatory are:
                - category: spot, linear, inverse, option
        See
        ---

        https://bybit-exchange.github.io/docs/v5/market/instrument
        """
        response = await super().fetch_instruments_details(**kwargs)
        return response["result"]

    @overrides(Exchange)
    async def fetch_coin_details(self, **kwargs):
        """Query coin information, including chain information,
        withdraw and deposit status.

        Parameters
        ----------

        kwargs: dict
            Contains the parameters corresponding to the endpoint.

        See
        ---

        https://bybit-exchange.github.io/docs/v5/asset/coin-info
        """
        response = await super().fetch_coin_details(**kwargs)
        return response["result"]

    @overrides(Exchange)
    async def fetch_price_snapshots(self, **kwargs):
        """Query for the latest price snapshot, best bid/ask price,
        and trading volume in the last 24 hours.

        Parameters
        ----------

        kwargs: dict
            Contains the parameters corresponding to the endpoint.
            Mandatory are:
                - category: spot, linear, inverse, option
        See
        ---

        https://bybit-exchange.github.io/docs/v5/market/tickers
        """
        response = await super().fetch_price_snapshots(**kwargs)
        return response["result"]

    @overrides(Exchange)
    async def fetch_announcements(self, **kwargs):
        """Get announcements

        Parameters
        ----------

        kwargs: dict
            Contains the parameters corresponding to the endpoint.
            Mandatory are:
                - locale

        See
        ---

        https://bybit-exchange.github.io/docs/v5/announcement
        """
        response = await super().fetch_announcements(**kwargs)
        return response["result"]

    @overrides(Exchange)
    async def stream_wallet(self, callback: Callable, **kwargs):
        """Subscribes to the wallet stream

        Parameters
        ----------
        kwargs: dict
            Contains extra arguments specific to bybit.

        callback: Callable
            The function to call when new wallet messages are sent
            by the exchange.

        see
        ---

        https://bybit-exchange.github.io/docs/v5/websocket/public/orderbook
        """
        topic = "wallet"
        endpoint = self.private_endpoint
        await self._subscribe(
            endpoint=endpoint, topic=topic, callback=callback, **kwargs
        )

    @overrides(Exchange)
    async def stream_orderbook(
        self,
        *,
        category: str,
        symbol: str,
        depth: int,
        callback: Callable | None = None,
        handle_delta: bool = True,
        **kwargs,
    ):
        """Subscribes to orderbook stream to fetch orderbook data.

        Parameters
        ----------

        category: str
            The category of the symbol: spot, linear, inverse, option

        symbol: str
            The instrument ex: BTCUSDT

        depth: int
            The number of bids / asks to fetch. For linear and inverse
            contracts, are supported depths [1, 50, 200, 500]. For spot
            [1, 50, 200]. For options [25, 100].

        callback: Callable
            The function to call when new transaction messages are sent
            by the exchange.

        kwargs: dict
            Contains extra arguments specific to bybit.

        see
        ---

        https://bybit-exchange.github.io/docs/v5/websocket/public/orderbook

        Note
        ----

        Latencies vary depending on the depth. We receive delta and snapshot
        messages and one need to take them into account and adjust the local
        orderbook.

        """
        topic = f"orderbook.{depth}.{symbol.upper()}"
        endpoint = f"{self.public_endpoint}/{category}"

        if callback and handle_delta:

            def _callback(message):
                return callback(self.handle_orderbook_delta(message))

        else:
            _callback = callback

        await self._subscribe(
            endpoint=endpoint, topic=topic, callback=_callback, **kwargs
        )

    @overrides(Exchange)
    async def stream_trades(
        self, *, category: str, symbol: str, callback: Callable | None = None, **kwargs
    ):
        """Subscribes to trade stream

        Parameters
        ----------

        category: str
            The category of the symbol: spot, linear, inverse, option

        symbol: str
            The instrument ex: BTCUSDT

        callback: Callable
            The function to call when new transaction messages are sent
            by the exchange.

        kwargs: dict
            Contains extra arguments specific to bybit.

        see
        ---

        https://bybit-exchange.github.io/docs/v5/websocket/public/trade

        """
        topic = f"publicTrade.{symbol.upper()}"
        endpoint = f"{self.public_endpoint}/{category}"
        await self._subscribe(
            endpoint=endpoint, topic=topic, callback=callback, **kwargs
        )

    @overrides(Exchange)
    async def stream_candlesticks(
        self,
        *,
        category: str,
        symbol: str,
        bar_size: int | str,
        callback: Callable | None = None,
        **kwargs,
    ):
        """streams candlesticks updates

        Parameters
        ----------

        category: str
            The category of the symbol: spot, linear, inverse, option

        symbol: str
            The instrument ex: BTCUSDT

        bar_size: int or str
            The interval that the bar should represent, ex. '1' min or 'D'
            for 1 day.

        callback: Callable
            The function to call when new transaction messages are sent
            by the exchange.

        kwargs: dict
            Contains extra arguments specific to bybit.

            Mandatory fields are:
                -bar_size: 1,3,5,15,30,60,120,240,360,720,D,M,W

        see
        ---

        https://bybit-exchange.github.io/docs/v5/websocket/public/kline

        """
        topic = f"kline.{bar_size}.{symbol.upper()}"
        endpoint = f"{self.public_endpoint}/{category}"
        await self._subscribe(
            endpoint=endpoint, topic=topic, callback=callback, **kwargs
        )

    @overrides(Exchange)
    async def stream_executions(self, *, callback: Callable | None = None, **kwargs):
        """streams executions updates

        Parameters
        ----------

        callback: Callable
            The function to call when execution messages are sent
            by the exchange.

        kwargs: dict
            Contains extra arguments specific to bybit.

        see
        ---

        https://bybit-exchange.github.io/docs/v5/websocket/private/execution

        """
        topic = "execution"
        endpoint = self.private_endpoint
        await self._subscribe(
            endpoint=endpoint, topic=topic, callback=callback, **kwargs
        )

    @overrides(Exchange)
    async def stream_orders(self, *, callback: Callable | None = None, **kwargs):
        """streams orders updates

        Parameters
        ----------

        callback: Callable
            The function to call when order messages are sent
            by the exchange.

        kwargs: dict
            Contains extra arguments specific to bybit.

        see
        ---

        https://bybit-exchange.github.io/docs/v5/websocket/private/order

        """
        topic = "order"
        endpoint = self.private_endpoint
        category = kwargs.get("category")
        if category is not None:
            endpoint = f"{endpoint}.{category}"
        await self._subscribe(
            endpoint=endpoint, topic=topic, callback=callback, **kwargs
        )

    @overrides(Exchange)
    async def stream_positions(self, *, callback: Callable | None = None, **kwargs):
        """streams position updates

        Parameters
        ----------

        callback: Callable
            The function to call when position messages are sent
            by the exchange.

        kwargs: dict
            Contains extra arguments specific to bybit.

        see
        ---

        https://bybit-exchange.github.io/docs/v5/websocket/private/position

        """
        topic = "position"
        endpoint = self.private_endpoint
        await self._subscribe(
            endpoint=endpoint, topic=topic, callback=callback, **kwargs
        )

    async def cancel_stream_positions(self, close_socket: bool = False, **kwargs):
        """Cancels position feed

        Parameters
        ----------

        kwargs: dict
            Contains extra arguments specific to bybit.

        see
        ---

        https://bybit-exchange.github.io/docs/v5/websocket/private/position

        """
        topic = "position"
        endpoint = self.private_endpoint
        await self._unsubscribe(
            endpoint=endpoint, topic=topic, close_socket=close_socket, **kwargs
        )

    async def cancel_stream_orders(self, close_socket: bool = False, **kwargs):
        """Cancels orders feed

        Parameters
        ----------

        kwargs: dict
            Contains extra arguments specific to bybit.

        see
        ---

        https://bybit-exchange.github.io/docs/v5/websocket/private/order

        """
        topic = "order"
        endpoint = self.private_endpoint
        await self._unsubscribe(
            endpoint=endpoint, topic=topic, close_socket=close_socket, **kwargs
        )

    async def cancel_stream_executions(self, close_socket: bool = False, **kwargs):
        """Cancels execution feed

        Parameters
        ----------

        kwargs: dict
            Contains extra arguments specific to bybit.

        see
        ---

        https://bybit-exchange.github.io/docs/v5/websocket/private/execution

        """
        topic = "execution"
        endpoint = self.private_endpoint
        await self._unsubscribe(
            endpoint=endpoint, topic=topic, close_socket=close_socket, **kwargs
        )

    async def cancel_stream_fast_executions(self, close_socket: bool = False, **kwargs):
        """Cancels fast execution feed (specific to Bybit)

        Parameters
        ----------

        kwargs: dict
            Contains extra arguments specific to bybit.

        see
        ---

        https://bybit-exchange.github.io/docs/v5/websocket/private/fast-execution

        """
        topic = "fasst-execution"
        endpoint = self.private_endpoint
        await self._unsubscribe(
            endpoint=endpoint, topic=topic, close_socket=close_socket, **kwargs
        )

    async def cancel_stream_orderbook(
        self,
        *,
        category: str,
        symbol: str,
        depth: int,
        close_socket: bool = False,
        **kwargs,
    ):
        """Cancels orderbook feed

        Parameters
        ----------

        category: str
            The category of the symbol: spot, linear, inverse, option

        symbol: str
            The instrument ex: BTCUSDT

        kwargs: dict
            Contains extra arguments specific to bybit.

        see
        ---

        https://bybit-exchange.github.io/docs/v5/websocket/public/orderbook

        """

        topic = f"orderbook.{depth}.{symbol.upper()}"
        endpoint = f"{self.public_endpoint}/{category}"
        await self._unsubscribe(
            endpoint=endpoint, topic=topic, close_socket=close_socket, **kwargs
        )

    async def cancel_stream_trades(
        self, *, category: str, symbol: str, close_socket: bool = False, **kwargs
    ):
        """Cancels trade feed

        Parameters
        ----------

        kwargs: dict
            Contains extra arguments specific to bybit.

        see
        ---

        https://bybit-exchange.github.io/docs/v5/websocket/public/trade

        """
        topic = f"publicTrade.{symbol.upper()}"
        endpoint = f"{self.public_endpoint}/{category}"
        await self._unsubscribe(
            endpoint=endpoint, topic=topic, close_socket=close_socket, **kwargs
        )

    async def cancel_stream_candlesticks(
        self,
        *,
        category: str,
        symbol: str,
        bar_size: int | str,
        close_socket: bool = False,
        **kwargs,
    ):
        """Cancels candlesticks feed

        Parameters
        ----------

        kwargs: dict
            Contains extra arguments specific to bybit.

        see
        ---

        https://bybit-exchange.github.io/docs/v5/websocket/public/kline

        """
        topic = f"kline.{bar_size}.{symbol.upper()}"
        endpoint = f"{self.public_endpoint}/{category}"
        await self._unsubscribe(
            endpoint=endpoint, topic=topic, close_socket=close_socket, **kwargs
        )

    async def cancel_stream_wallets(self, close_socket: bool = False, **kwargs):
        """Cancels wallets feed

        Parameters
        ----------

        kwargs: dict
            Contains extra arguments specific to the exchange.

        see
        ---

        https://bybit-exchange.github.io/docs/v5/websocket/public/kline

        """
        topic = "wallet"
        endpoint = self.private_endpoint
        await self._unsubscribe(
            endpoint=endpoint, topic=topic, close_socket=close_socket, **kwargs
        )

    # +---------------------------+
    # +  WS formatting callbacks  +
    # +---------------------------+

    @callback_mapper(attribute="orders", endpoint="orders")
    @overrides(Exchange)
    def _callback_order_stream(callback, *, message):
        return callback(message)

    @callback_mapper(attribute="positions", endpoint="positions")
    @overrides(Exchange)
    def _callback_position_stream(callback, *, message):
        return callback(message)

    @callback_mapper(attribute="orders", endpoint="execution")
    @overrides(Exchange)
    def _callback_execution_stream(callback, *, message):
        return callback(message)

    # +-----------------------+
    # + parent helper methods +
    # +-----------------------+

    @overrides(Exchange)
    def _generate_subscription_message(self, topic: str, **kwargs) -> str:
        """Method that builds the subscription message for websocket streams"""
        # req_id not set for now.
        # req_id = str(uuid.uuid4())
        return build_message(op="subscribe", args=[topic], **kwargs)

    @overrides(Exchange)
    def _generate_unsubscription_message(self, topic: str, **kwargs) -> str:
        """Method that builds the unsubscription message for
        websocket streams

        """
        # req_id = str(uuid.uuid4())
        return build_message(op="unsubscribe", args=[topic], **kwargs)

    @overrides(Exchange)
    def _get_reply_status(self, message: Dict[str, Any]) -> Tuple[bool, str]:
        """Method that takes care of the server acknowledgment to either
        an authenticaion, a subscription or unsubscription

        Parameters
        ----------

            message: dict
                The response of the exchange server.

            reason: str
                The reason to be displayed that represents the nature
                of the response, ex. Authentication / Subscription ...
        """
        success = message.get("success")
        error = message["ret_msg"]
        return success, error

    @overrides(Exchange)
    def _generate_ws_authentication_message(self):
        expires = str(int((time.time() + self._expiry_time) * 1000))
        signature = hmac_signature(
            api_secret=self._secret, payload=f"GET/realtime{expires}"
        )
        message = build_message(op="auth", args=[self._key, expires, signature])
        return message

    @overrides(Exchange)
    def handle_orderbook_delta(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Manages delta messages sent from the exchange.

        When an exchange sends a snapshot this is saved in order to build a local
        orderbook. Then the exchange sends delta messages representing the price/volume
        change at a certain limit. This method allows to construct the local orderbook.

        Note: If a depth `d` is retrieved from the exchange, depending on delta messages
        we might not get the same depth after processing as the original message.
        Sometimes we get more sometimes less. You might want to restric the depth of
        the messages to a certain `max_depth` in order to have a consistent bid/ask
        lengths, otherwise you should increase the depth you get from the exchange.

        Parameters
        ----------
            message: dict
                A snapshot or delta message sent by the exchange

        returns
        -------
            message: dict
                a snapshot message computed from the delta.
        """
        topic = message["topic"]
        # Change only the bid/ask data keep the rest untouched
        new_message = {**message}
        if message["type"] != "snapshot":
            uid = message["data"]["u"]
            puid = self._previous_snapshot[topic]["data"]["u"]
            if uid <= puid:
                _logger.warning(
                    f"Received an update id {uid} lower than in the previous message "
                    f"{puid}"
                )
            data = {}

            for side in ("b", "a"):
                prices = message["data"][side]
                prev_prices = {
                    k: v for k, v in self._previous_snapshot[topic]["data"][side]
                }
                for price, volume in prices:
                    if volume == "0":
                        if price in prev_prices:
                            del prev_prices[price]
                    else:
                        prev_prices[price] = volume
                data[side] = [[k, v] for k, v in prev_prices.items()]
            new_message["type"] = "snapshot"
            new_message["data"] = message["data"] | data

        self._previous_snapshot[topic] = new_message
        return new_message

    @overrides(Exchange)
    @staticmethod
    def is_quote_message(message):
        return "topic" in message and message["topic"].startswith("o")

    @overrides(Exchange)
    @staticmethod
    def is_trade_message(message):
        return "topic" in message and message["topic"].startswith("public")

    @overrides(Exchange)
    @staticmethod
    def is_ack_message(message):
        return "success" in message

    @overrides(Exchange)
    @staticmethod
    def validate_http_response(response: Dict[str, Any]) -> Tuple[bool, int, str]:
        error_code = response.get("retCode")
        error_message = response.get("retMsg")
        if error_code != 0:
            return False, error_code, error_message
        return True, error_code, error_message

    @overrides(Exchange)
    @staticmethod
    def validate_ws_response(self, response: Dict[str, Any]) -> Tuple[bool, int, str]:
        success = response.get("success")
        error_message = response.get("retMsg")
        return success, 0, error_message


class BybitLive(_BybitExchange):

    def __init__(self, **kwargs):
        super().__init__(
            testnet=False,
            demo=False,
            config=exchanges_config.live.bybit,
            **kwargs,
        )


class BybitTestnet(_BybitExchange):

    def __init__(self, **kwargs):

        super().__init__(
            testnet=True,
            demo=False,
            config=exchanges_config.testnet.bybit,
            **kwargs,
        )


class BybitDemo(_BybitExchange):

    def __init__(self, **kwargs):
        super().__init__(
            testnet=False,
            demo=True,
            config=exchanges_config.demo.bybit,
            dump_ssl_keys=True,
            **kwargs,
        )
