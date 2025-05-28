import json
import logging
import httpx

from typing import Dict, Any
from urllib.parse import urlencode

from cryptoex.exceptions import ExchangeError

_logger = logging.getLogger(__name__)


class _HTTPManager:

    def __init__(
        self,
        subdomain: str,
        domain: str,
        tl_domain: str,
        recv_window: int,
        key: str,
        secret: str,
        requires_auth: bool = True,
    ):

        # protected
        self._http_base_url = f"https://{subdomain}.{domain}.{tl_domain}"
        self._key = key
        self._secret = secret
        self._requires_http_auth = requires_auth

        # public
        self._recv_window = recv_window
        self._private_client = httpx.AsyncClient(
            http2=True,
            headers={
                "Content-Type": "application/json",
            },
        )
        self._public_client = httpx.AsyncClient(
            http2=True,
            headers={
                "Content-Type": "application/json;charset=utf-8",
                "Accept": "application/json",
            },
        )

    @property
    def _can_make_request(self):
        """Attr that checks if there are limits to send orders per second
        if so we need to override this attribute
        """
        return True

    def _private_headers(self, signature, timestamp, recv_window):
        raise NotImplementedError()

    def _client(self, private: bool = False) -> httpx.AsyncClient:
        if private:
            return self._private_client
        return self._public_client

    async def request(
        self,
        *,
        method: str,
        endpoint: str,
        params: Dict[str, Any] = None,
        data: Dict[str, Any] = None,
        private: bool = False,
    ) -> Dict[str, Any] | str:
        """Generic method to process HTTP requests for all exchanges

        Parameters
        ----------

            method: str
            The HTTP method: GET, POST, PUT, ...

            endpoint: str
                The URL path that allow fetching a specific data
                from the server.

            params: dict
                The uri query in the form of a dictionnary.

            data: dict
                The POST/PUT data.

            private: bool
                Whether private headers are needed for authentication
                to the server.
        """
        params, data = self._request_params(params, data)
        client = self._client(private)
        headers = {}
        if private and self._requires_http_auth:
            headers = self._private_headers(data or params)
        url = f"{self._http_base_url}{endpoint}"
        if params:
            url = f"{url}?{params}"
        _logger.info(f"Calling API with {url=}, {headers=}, {params=}, {data=}")
        try:
            response = await client.request(
                method=method, url=url, data=data, headers=headers
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            _logger.exception(error)
            raise ExchangeError(
                f"Unsuccessful API request to {url}: Error {response.status_code}"
            )

        _logger.debug(f"Received {response=} with headers {response.headers}")
        _logger.info(f"Processing response for {url=}")
        return self._process_response(response=response)

    def _process_response(self, response: httpx.Response) -> Dict[str, Any] | str:
        try:
            return response.json()
        except (AttributeError, json.JSONDecodeError):
            return response.text

    def _request_params(self, params: Dict[str, Any], data: str) -> str:
        assert not (data and params), "Use either data or params, not both."
        if params:
            for k, v in params.items():
                if isinstance(v, float) and v == int(v):
                    params[k] = int(v)
            params = {k: v for k, v in params.items() if v is not None}

        if data:
            data = json.dumps(data)
        return urlencode(params or ""), data
