import logging

from typing import Callable, Any, Dict, Tuple

from cryptoex._wsmanager import _WSManager
from cryptoex._httpmanager import _HTTPManager
from cryptoex.exchanges.utils import ExchangeEndpoints
from cryptoex.exchanges.utils import ExchangeConfig
from cryptoex.exchanges.utils import handle_requests
from cryptoex.exchanges.formatters import AbstractFormatter

_logger = logging.getLogger(__name__)


class Exchange(_HTTPManager, _WSManager):

    def __init__(
        self,
        testnet: bool,
        demo: bool,
        config: ExchangeConfig,
        endpoints: ExchangeEndpoints,
        formatter: AbstractFormatter,
        expiry_time: int = 1,
        recv_window: int = 5000,
        max_connections: int = 500,
        save_ssl_keys: bool = False,
        pcap_dir: str | None = None,
        **kwargs,
    ):
        assert not (demo and testnet), "Use either testnet or demo not both."
        requires_auth = not testnet

        _HTTPManager.__init__(
            self,
            subdomain=config.http_subdomain,
            domain=config.http_domain,
            tl_domain=config.http_tld,
            recv_window=recv_window,
            key=config.key,
            secret=config.secret,
            requires_auth=requires_auth,
        )

        _WSManager.__init__(
            self,
            subdomain=config.ws_subdomain,
            domain=config.ws_domain,
            tl_domain=config.ws_tld,
            public_endpoint=endpoints.WS_PUBLIC_ENDPOINT,
            private_endpoint=endpoints.WS_PRIVATE_ENDPOINT,
            trading_endpoint=endpoints.WS_TRADING_ENDPOINT,
            expiry_time=expiry_time,
            requires_auth=requires_auth,
            max_connections=max_connections,
            save_ssl_keys=save_ssl_keys,
            pcap_dir=pcap_dir,
        )
        self.formatter = formatter
        self.endpoints = endpoints
        self.name = type(self).__name__
        self.auto_dump = kwargs.get("auto_dump", not (demo or testnet))

    # +--------------+
    # + http methods +
    # +--------------+
    @handle_requests(
        attribute="accounts",
        endpoint="ACCOUNT",
        private=True,
    )
    async def fetch_account_details(self, **kwargs):
        """Query the account information, like margin mode, account mode, etc.

        Parameters
        ----------

        kwargs: dict
            Contains the parameters corresponding to the endpoint.
        """
        pass

    @handle_requests(
        attribute="accounts",
        endpoint="WITHDRAWALS",
        private=True,
        filename="withdrawals",
    )
    async def fetch_withdrawal_details(self, **kwargs):
        """Query the available amount to transfer of a specific coin
        in the wallet.

        Parameters
        ----------

        kwargs: dict
            Contains the parameters corresponding to the endpoint.
        """
        pass

    @handle_requests(
        attribute="accounts",
        endpoint="WALLET",
        filename="wallets",
        private=True,
    )
    async def fetch_wallet_details(self, **kwargs):
        """Obtain wallet balance, query asset information of each currency.

        Parameters
        ----------

        kwargs: dict
            Contains the parameters corresponding to the endpoint.
        """
        pass

    @handle_requests(attribute="positions", endpoint="POSITIONS", private=True)
    async def fetch_positions(self, **kwargs):
        """Query real-time position data, such as position size,
        cumulative realized PNL, etc.

        Parameters
        ----------

        kwargs: dict
            Contains the parameters corresponding to the endpoint.
        """
        pass

    @handle_requests(attribute="fees", endpoint="TRADING_FEES", private=True)
    async def fetch_trading_fees(self, **kwargs):
        """Fetch trading fees data through REST API

        Parameters
        ----------

        kwargs: dict
            Contains the parameters corresponding to the endpoint.

        """
        pass

    @handle_requests(
        attribute="server",
        endpoint="SERVER_TIME",
    )
    async def fetch_server_time(self, **kwargs):
        """Get server time"""
        pass

    @handle_requests(
        attribute="markets",
        endpoint="CANDLESTICKS",
        filename="candlesticks",
    )
    async def fetch_candlesticks(self, **kwargs):
        """Query for historical klines (also known as candlesticks).
        Charts are returned in groups based on the requested bar_size.

        Parameters
        ----------

        kwargs: dict
            Contains the parameters corresponding to the endpoint.

        """
        pass

    @handle_requests(
        attribute="markets",
        endpoint="ORDERBOOK",
        filename="orderbook",
    )
    async def fetch_orderbook(self, **kwargs):
        """Downloads orderbook data

        Parameters
        ----------

        kwargs: dict
            Contains the parameters corresponding to the endpoint.
        """
        pass

    async def fetch_all_instruments_details(self, **kwargs):
        """Query for the instrument specification of online trading pairs of all category
        types.

        Parameters
        ----------

        kwargs: dict
            Contains the parameters corresponding to the endpoint(s).
        """
        raise NotImplementedError()

    @handle_requests(
        attribute="instruments",
        endpoint="INSTRUMENTS",
        level="category",
    )
    async def fetch_instruments_details(self, **kwargs):
        """Query for the instrument specification of online trading pairs.

        Parameters
        ----------

        kwargs: dict
            Contains the parameters corresponding to the endpoint.
        """
        pass

    @handle_requests(
        attribute="markets", endpoint="COINS", filename="coins", private=True
    )
    async def fetch_coin_details(self, **kwargs):
        """Query coin information, including chain information,
        withdraw and deposit status.

        Parameters
        ----------

        kwargs: dict
            Contains the parameters corresponding to the endpoint.
        """
        pass

    @handle_requests(
        attribute="markets",
        endpoint="PRICE_SNAPSHOTS",
        filename="price_snapshots",
        level="category",
    )
    async def fetch_price_snapshots(self, **kwargs):
        """Query for the latest price snapshot, best bid/ask price,
        and trading volume in the last 24 hours.

        Parameters
        ----------

        kwargs: dict
            Contains the parameters corresponding to the endpoint.
        """
        pass

    @handle_requests(
        attribute="announcements",
        endpoint="ANNOUNCEMENTS",
    )
    async def fetch_announcements(self, **kwargs):
        """Get announcements

        Parameters
        ----------

        kwargs: dict
            Contains the parameters corresponding to the endpoint.
        """
        pass

    async def get_rate_limits(self, **kwargs):
        """Fetch IP Rate Limits

        Parameters
        ----------

        kwargs: dict
            Contains the parameters corresponding to the endpoint.
        """
        # TODO: check if a file with limits exist ... if so load the file, otherwise
        # raise not implemented error
        raise NotImplementedError()

    # +-------------------+
    # + Websocket methods +
    # +-------------------+
    async def stream_wallet(self, callback: Callable, **kwargs):
        """Subscribes to the wallet stream

        Parameters
        ----------
        kwargs: dict
            Contains extra arguments specific to bybit.

        callback: Callable
            The function to call when new wallet messages are sent
            by the exchange.
        """
        raise NotImplementedError()

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
        """Subscribes to orderbook stream

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
            Contains extra arguments specific to the exchange.
        """
        raise NotImplementedError()

    async def stream_positions(self, *, callback: Callable | None = None, **kwargs):
        """streams position updates

        Parameters
        ----------

        callback: Callable
            The function to call when position messages are sent
            by the exchange.

        kwargs: dict
            Contains extra arguments specific to the exchange.
        """
        raise NotImplementedError()

    async def stream_trades(
        self,
        *,
        category: str,
        symbol: str,
        callback: Callable | None = None,
        **kwargs,
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
            Contains extra arguments specific to the exchange.
        """
        raise NotImplementedError()

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
            Contains extra arguments specific to the exchange.
        """
        raise NotImplementedError()

    async def stream_executions(self, *, callback: Callable | None = None, **kwargs):
        """streams executions updates

        Parameters
        ----------

        callback: Callable
            The function to call when execution messages are sent
            by the exchange.

        kwargs: dict
            Contains extra arguments specific to the exchange.
        """
        raise NotImplementedError()

    async def stream_orders(self, *, callback: Callable | None = None, **kwargs):
        """streams orders updates

        Parameters
        ----------

        callback: Callable
            The function to call when order messages are sent
            by the exchange.

        kwargs: dict
            Contains extra arguments specific to the exchange.
        """
        raise NotImplementedError()

    async def cancel_stream_executions(self, close_socket: bool = False, **kwargs):
        """Cancels execution feed

        Parameters
        ----------

        kwargs: dict
            Contains extra arguments specific to the exchange.
        """
        raise NotImplementedError()

    async def cancel_stream_orders(self, close_socket: bool = False, **kwargs):
        """Cancels orders feed

        Parameters
        ----------

        kwargs: dict
            Contains extra arguments specific to the exchange.
        """
        raise NotImplementedError()

    async def cancel_stream_positions(self, close_socket: bool = False, **kwargs):
        """Cancels position feed

        Parameters
        ----------

        kwargs: dict
            Contains extra arguments specific to the exchange.
        """
        raise NotImplementedError()

    async def cancel_stream_trades(
        self, *, category: str, symbol: str, close_socket: bool = False, **kwargs
    ):
        """Cancels trade feed

        Parameters
        ----------

        category: str
            The category of the symbol: spot, linear, inverse, option

        symbol: str
            The instrument ex: BTCUSDT

        kwargs: dict
            Contains extra arguments specific to the exchange.
        """
        raise NotImplementedError()

    async def cancel_stream_orderbook(
        self,
        *,
        category: str,
        symbol: str,
        depth: str,
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

        depth: int
            The number of bids / asks to fetch.

        kwargs: dict
            Contains extra arguments specific to the exchange.
        """
        raise NotImplementedError()

    async def cancel_stream_candlesticks(
        self,
        *,
        category: str,
        symbol: str,
        bar_size: str | int,
        close_socket: bool = False,
        **kwargs,
    ):
        """Cancels candlesticks feed

        Parameters
        ----------

        category: str
            The category of the symbol: spot, linear, inverse, option

        symbol: str
            The instrument ex: BTCUSDT

        bar_size: int or str
            The interval that the bar should represent, ex. '1' min or 'D'
            for 1 day.

        kwargs: dict
            Contains extra arguments specific to the exchange.
        """
        raise NotImplementedError()

    async def cancel_stream_wallets(self, **kwargs):
        """Cancels wallets feed

        Parameters
        ----------

        kwargs: dict
            Contains extra arguments specific to the exchange.
        """
        raise NotImplementedError()

    # +-----------------+
    # + Trading methods +
    # +-----------------+

    async def kill_trading(self, **kwargs):
        """Cancel all sent orders and perform sanity checks"""
        await self.order_cancel_all(**kwargs)

    async def order_create(self, **kwargs):
        """Creates limit, market and conditional orders"""
        endpoint = self.endpoints.CREATE_ORDER
        response = await self.request(
            method="POST", endpoint=endpoint, data=kwargs, private=True
        )
        return response

    async def order_set_trailing_stop(self, **kwargs):
        """Creates limit, market and conditional orders"""
        endpoint = self.endpoints.TRAILINGSTOP
        response = await self.request(
            method="POST", endpoint=endpoint, data=kwargs, private=True
        )
        return response

    async def order_set_take_profit(self, **kwargs):
        """Creates limit, market and conditional orders"""
        endpoint = self.endpoints.TAKEPROFIT
        response = await self.request(
            method="POST", endpoint=endpoint, data=kwargs, private=True
        )
        return response

    async def order_set_stoploss(self, **kwargs):
        """Creates limit, market and conditional orders"""
        endpoint = self.endpoints.STOPLOSS
        response = await self.request(
            method="POST", endpoint=endpoint, data=kwargs, private=True
        )
        return response

    async def order_cancel(self, **kwargs):
        """Cancels an order"""
        endpoint = self.endpoints.CANCEL_ORDER
        response = await self.request(
            method="POST", endpoint=endpoint, data=kwargs, private=True
        )
        return response

    async def order_amend(self, **kwargs):
        """Amends an order"""
        endpoint = self.endpoints.AMEND_ORDER
        response = await self.request(
            method="POST", endpoint=endpoint, data=kwargs, private=True
        )
        return response

    async def order_cancel_all(self, **kwargs):
        """Cancels all the orders sent to the exchange"""
        endpoint = self.endpoints.CANCEL_ALL_ORDERS
        response = await self.request(
            method="POST", endpoint=endpoint, data=kwargs, private=True
        )
        return response

    # +----------------------------------------------------------------------------+
    # + WS callbacks to map exchange keys of the stream responses to a local map +
    # +----------------------------------------------------------------------------+
    def _callback_order_stream(callback, *, message):
        raise NotImplementedError()

    def _callback_position_stream(callback, *, message):
        raise NotImplementedError()

    def _callback_execution_stream(callback, *, message):
        raise NotImplementedError()

    def handle_orderbook_delta(self, message: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError()

    @staticmethod
    def validate_http_response(
        response: Dict[str, Any],
    ) -> Tuple[bool, int, str]:
        raise NotImplementedError()

    @staticmethod
    def validate_ws_response(
        response: Dict[str, Any],
    ) -> Tuple[bool, int, str]:
        raise NotImplementedError()

    # +--------------------------------------------------------------------+
    # + Utilities to identify orderbook topics from trade and ack topics +
    # +--------------------------------------------------------------------+
    @staticmethod
    def is_quote_message(message):
        raise NotImplementedError()

    @staticmethod
    def is_trade_message(message):
        raise NotImplementedError()

    @staticmethod
    def is_ack_message(message):
        raise NotImplementedError()
