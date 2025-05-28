import os
import ssl
import logging
import json
import asyncio
import websockets
from urllib.parse import urljoin
from typing import Dict, Any, Callable, Tuple
from cryptoex import settings
from cryptoex.exceptions import ExchangeError, MaxLimitReached, WebsocketError

_logger = logging.getLogger(__name__)


class UnsubscribtionEvent(asyncio.Event):

    def __init__(self, close_socket: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.close_socket = close_socket


class _WSManager:

    def __init__(
        self,
        subdomain: str,
        domain: str,
        tl_domain: str,
        public_endpoint: str,
        private_endpoint: str,
        trading_endpoint: str,
        expiry_time: int,
        requires_auth: bool,
        max_connections: int,
        save_ssl_keys: bool,
        pcap_dir: str,
    ):

        self._ws_base_url = f"wss://{subdomain}.{domain}.{tl_domain}"
        if trading_endpoint is not None:
            self._trading_ws = None
            self._trading_endpoint_url = f"{self._ws_base_url}{trading_endpoint}"

        # protected
        self._sub_callbacks = {}
        self._sub_websockets = {}
        self._available_websockets = {}
        self._subscription_tasks = {}
        self.public_endpoint = public_endpoint
        self.private_endpoint = private_endpoint

        # public
        self._requires_ws_auth = requires_auth
        self._expiry_time = expiry_time
        self._max_connections = max_connections
        self._default_context = ssl.create_default_context()
        self._unsub_event: Dict[str, UnsubscribtionEvent] = {}
        self._name = type(self).__name__

        if save_ssl_keys:
            pcap_dir = os.path.join(settings.PCAP_DIR, self._name)
            os.makedirs(pcap_dir, exist_ok=True)
            self._default_context.keylog_filename = os.path.join(
                pcap_dir, "capture.keys"
            )

    @property
    def _can_subscribe(self) -> bool:
        return len(self._sub_websockets) < self._max_connections

    async def _subscribe(
        self,
        *,
        endpoint: str,
        topic: str,
        callback: Callable | None = None,
        **kwargs,
    ) -> None:
        """Subscribes to a stream from the exchange
        We ty reusing any available websoket. If none is found we check if we
        can create one. Otherwise we log an error stating that we cannot
        subscibe to the topic. In that case we are using too many connections
        and we should cancel some or wait the quota to be available again.

        Parameters
        ----------

        endpoint: str
            The connection endpoint that distinguishes private/public streams as
            well as the category of the symbol of interest:
            (spot, linear, inverse, option)

        topic: str
            the topic to receive updates from the exchange.
            (Ex. orderbook data, trade data, executions ... )

        callback: Callable
            The function to call when a push from the server is received.

        kwargs:
            Keyword arguments to pass to the subscription message function
            to build the subscription payload.

        """
        #
        if callback:
            self._sub_callbacks[topic + endpoint] = callback

        _logger.info(f"[{self._name}]: Received subscription to {topic}")

        if topic in self._sub_websockets:
            _logger.error(
                f"[{self._name}]: Cannot subscribe twice to the same {topic=}"
            )
            return

        await self._init_websocket(endpoint)
        await self._sub_handler(endpoint, topic, **kwargs)

    async def _init_websocket(self, endpoint: str) -> None:
        ws = self._available_websockets.get(endpoint)
        if ws:
            if ws.state == websockets.State.OPEN:
                _logger.info(
                    f"[{self._name}]:" f" Using an existing connection for {endpoint=}"
                )
                return
            else:
                self._available_websockets.pop(endpoint)

        uri = urljoin(self._ws_base_url, endpoint)
        if self._can_subscribe:
            _logger.info(f"[{self._name}]: " f"Creating a new connection for {uri=}")
            websocket = await websockets.connect(uri, ssl=self._default_context)
            # Manage private authentication
            private = self.private_endpoint in endpoint
            if private and self._requires_ws_auth:
                _logger.info(f"[{self._name}]: Authenticating for {endpoint=}")
                await self._authenticate(websocket)
            self._available_websockets[endpoint] = websocket
        else:
            _logger.error(
                f"[{self._name}]: Unable to init websocket. Max connections reached"
            )
            raise MaxLimitReached(
                f"[{self._name}]: Unable to init websocket for {uri=}"
            )

    async def _unsubscribe(
        self,
        *,
        endpoint: str,
        topic: str,
        close_socket: bool,
        **kwargs,
    ):
        """Unsbscribe from a stream from the exchange

        Parameters
        ----------

        endpoint: str
            The connection endpoint that distinguishes private/public streams as
            well as the category of the symbol of interest:
            (spot, linear, inverse, option)


        topic: str
            the topic to receive updates from the exchange.
            (Ex. orderbook data, trade data, executions ... )

        private: bool (default: False)
            Whether the unsubscription requires a private/public stream.
            Note that private streams require authentication using
            the API key and secret or any kind of exchange authentication
            mechanism.
        kwargs:
            Keyword arguments to pass to the unsubscription message
            function to build the unsubscription payload.

        """
        if topic + endpoint in self._unsub_event:
            self._unsub_event[topic + endpoint].close_socket = close_socket
            self._unsub_event[topic + endpoint].set()
            await asyncio.sleep(0)
        else:
            raise WebsocketError(f"No subscription for {topic=} and {endpoint=}")

    async def _sub_handler(
        self,
        endpoint: str,
        topic: str,
        **kwargs,
    ):
        # Since a call to init_websocket has been made, we are guaranteed to have
        # a websocket available
        websocket = self._available_websockets.pop(endpoint)
        self._sub_websockets[topic + endpoint] = websocket

        try:
            await self._send_subscription(websocket, endpoint, topic, **kwargs)

        except Exception as e:
            _logger.debug(f"[{self._name}]: Cleaning up for {topic}")
            _logger.exception(e)
            self._clean_data(topic)

    async def _send_subscription(
        self,
        websocket: websockets.ClientConnection,
        endpoint: str,
        topic: str,
        **kwargs,
    ) -> None:
        # Subscribe to topic
        message = self._generate_subscription_message(topic, **kwargs)
        _logger.debug(f"[{self._name}]: Generated subscription {message=}")
        path = topic + endpoint
        await websocket.send(message)
        message = json.loads(await websocket.recv())
        success, error = self._get_reply_status(message)
        if success:
            _logger.info(f"[{self._name}]: Subscription to {topic=} successful")
            self._unsub_event[path] = UnsubscribtionEvent()
            self._subscription_tasks[path] = asyncio.create_task(
                self._receive_messages(websocket, endpoint, topic, **kwargs), name=path
            )
        else:
            _logger.error(
                f"[{self._name}]: Subscription to {topic=} failed with {error=}"
            )
            raise ExchangeError(f"Unable to subscribe to {topic=}, {error!s}")

    async def _receive_messages(
        self,
        websocket: websockets.ClientConnection,
        endpoint: str,
        topic: str,
        **kwargs,
    ) -> None:
        path = topic + endpoint
        try:
            while True:
                recv_task = asyncio.Task(websocket.recv())
                wait_task = asyncio.Task(self._unsub_event[path].wait())
                tasks = (recv_task, wait_task)
                await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

                if self._unsub_event[path].is_set():
                    _logger.info(
                        f"[{self._name}]:"
                        f" Unsubscription event triggered for {topic}"
                    )
                    recv_task.cancel()
                    await asyncio.sleep(0)
                    close_socket = self._unsub_event[path].close_socket
                    await asyncio.wait_for(
                        self._send_unsubscription(
                            endpoint, topic, close_socket, **kwargs
                        ),
                        timeout=1,
                    )
                    self._unsub_event.pop(path)
                    break

                message = json.loads(recv_task.result())
                _logger.debug(f"[{self._name}]: Received {message=}")
                if path in self._sub_callbacks:
                    self._sub_callbacks[path](message)

        except asyncio.CancelledError:
            _logger.debug(f"[{self._name}]: Cleaning up for {topic}")
            await websocket.close()
            self._clean_data(path)
            _logger.debug(
                f"[{self._name}]: Unsubscription to {topic} has been cancelled"
            )
        except TimeoutError:
            _logger(f"[{self._name}]: Timeout - Unable to unsbscribe from {topic}.")
            websocket.close()
        except Exception as e:
            _logger.exception(e)

    async def _send_unsubscription(
        self, endpoint: str, topic: str, close_socket: bool, **kwargs
    ) -> None:
        path = topic + endpoint
        websocket = self._sub_websockets[path]
        message = self._generate_unsubscription_message(topic, **kwargs)
        _logger.debug(f"[{self._name}]: Generated unsubscription {message=}")

        await websocket.send(message)
        # Discard non unsubscription messages for this socket
        while True:
            message = json.loads(await websocket.recv())
            _logger.debug(
                f"[{self._name}]: Received unsubscription response: {message}"
            )
            try:
                success, reason = self._get_reply_status(message)
                break
            except KeyError:
                pass

        if success:
            _logger.info(f"[{self._name}]: Unsubscription from {topic=} successful.")
            ws = self._sub_websockets.pop(path)
            if endpoint in self._available_websockets or close_socket:
                await ws.close()
            else:
                self._available_websockets[endpoint] = ws
        else:
            raise ExchangeError(f"Unable to unsubscribe from {topic}, {reason=}")

    async def prepare_public_websocket(self, path: str | None = None) -> str:
        """Prepare a public websocket. Only needed if the intention is to retrieve
        information about remote host.
        is to live capture network packets and store then into
        pcap files. Otherwise, use any of the available `stream` methods.
        """
        endpoint = self.public_endpoint
        if path:
            endpoint = os.path.join(endpoint, path)

        return await self._prepare(endpoint)

    async def prepare_private_websocket(self, path: str | None = None) -> str:
        """Prepare a private websocket. Only needed if the intention is to retrieve
        information about remote host.
        is to live capture network packets and store then into
        pcap files. Otherwise, use any of the available `stream` methods.
        """
        if not hasattr(self, "trading_endpoint"):
            raise WebsocketError(f"[{self._name}]: This venue has no trading endpoint")
        endpoint = self.private_endpoint
        if path:
            endpoint = os.path.join(endpoint, path)

        return await self._prepare(endpoint)

    async def prepare_trading_websocket(self, path: str | None = None):
        """Prepare a trading websocket. Only needed if the intention is to retrieve
        information about remote host.
        is to live capture network packets and store then into
        pcap files. Otherwise, use any of the available `stream` methods.
        """
        endpoint = self.trading_endpoint
        if path:
            endpoint = os.path.join(endpoint, path)
        return await self._prepare(endpoint)

    async def _prepare(self, endpoint):
        await self._init_websocket(endpoint)
        return self._available_websockets.get(endpoint).remote_address

    def _clean_data(self, path: str) -> None:
        if path in self._sub_websockets:
            self._sub_websockets.pop(path)
        if path in self._unsub_event:
            self._unsub_event.pop(path)

    async def _authenticate(self, websocket: websockets.ClientConnection) -> None:
        message = self._generate_ws_authentication_message()
        await websocket.send(message)
        message = json.loads(await websocket.recv())
        success, error = self._get_reply_status(message)

        _logger.debug(
            f"[{self._name}]: Authentication request finished." f"{success=}, {error=}"
        )

        if not success:
            raise ExchangeError(f"Unable to authenticate, {error=}")

    def _generate_unsubscription_message(self, topic: str, **kwargs) -> str:
        raise NotImplementedError("This method needs to be implemented")

    def _generate_subscription_message(self, topic: str, **kwargs) -> str:
        raise NotImplementedError("This method needs to be implemented")

    def _generate_ws_authentication_message(self) -> str:
        raise NotImplementedError("This method needs to be implemented")

    def _get_reply_status(self, message: Dict[str, Any]) -> Tuple[bool, str]:
        """Processes the server reply to an subscription
        Used to tell whether the subscription is successful or not.
        """
        raise NotImplementedError("This method needs to be implemented")
