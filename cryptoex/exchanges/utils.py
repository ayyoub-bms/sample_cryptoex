import os
import json
import yaml
import logging
from pathlib import Path
from functools import wraps
from datetime import datetime
from pydantic.dataclasses import dataclass
from typing import Any, Dict, List
from cryptoex import settings
from cryptoex.exceptions import ExchangeError


_logger = logging.getLogger(__name__)


def _get_config():
    exchanges_file = settings.EXCHANGES_CONFIG_PATH
    with open(exchanges_file, "r") as f:
        config = yaml.safe_load(f)

    for env in config:
        for k, v in config[env].items():
            config[env][k] = ExchangeConfig(**v)
    return config


@dataclass
class ExchangeEndpoints:
    # Announcements
    ANNOUNCEMENTS: str
    # Accounts & positions
    ACCOUNT: str
    COINS: str
    POSITIONS: str
    TRADING_FEES: str
    WALLET: str
    WITHDRAWALS: str
    # Server data
    SERVER_TIME: str
    # Market data
    CANDLESTICKS: str
    INSTRUMENTS: str
    ORDERBOOK: str
    PRICE_SNAPSHOTS: str
    # Order management
    AMEND_ORDER: str
    BATCH_AMEND: str
    BATCH_CANCEL: str
    BATCH_CREATE: str
    CANCEL_ALL_ORDERS: str
    CANCEL_ORDER: str
    CREATE_ORDER: str
    OPEN_ORDERS: str
    ORDER_HISTORY: str
    SET_TRADING_STOP: str
    # For linear and inverse
    STOPLOSS: str
    TAKEPROFIT: str
    TRAILINGSTOP: str
    # Websocket streams
    WS_PUBLIC_ENDPOINT: str
    WS_PRIVATE_ENDPOINT: str
    WS_TRADING_ENDPOINT: str

    @classmethod
    def from_yaml(cls, filename: str) -> "ExchangeEndpoints":
        exchanges_file = os.path.join(settings.ENDPOINTS_DIR, filename)
        with open(exchanges_file, "r") as f:
            config = yaml.safe_load(f)
        return cls(**config)


@dataclass(repr=False)
class ExchangeConfig:
    key: str
    secret: str
    class_name: str
    http_domain: str
    http_subdomain: str
    http_tld: str
    ws_domain: str
    ws_subdomain: str
    ws_tld: str

    def __post_init__(self):
        self.key = os.getenv(self.key)
        self.secret = os.getenv(self.secret)

    def __repr__(self):
        return f"ExchangeConfig(class_name={self.class_name})"


@dataclass
class Mapping:
    defaults: dict[str, Any] | None = None
    required: List[str] | None = None
    cond_required: Dict[str, List[str]] | None = None
    inputs: Dict[str, Any] | None = None
    outputs: Dict[str, Any] | None = None


@dataclass
class ExchangeMappings:
    accounts: Dict[str, Mapping]
    instruments: Dict[str, Mapping]
    markets: Dict[str, Mapping]
    orders: Dict[str, Mapping]
    positions: Dict[str, Mapping]
    fees: Dict[str, Mapping] | None = None
    limits: Dict[str, Mapping] | None = None
    announcements: Dict[str, Mapping] | None = None
    server: Dict[str, Mapping] | None = None

    @classmethod
    def from_yaml(cls, dirname):
        conf = {}
        for file in Path(settings.MAPPINGS_DIR).joinpath(dirname).glob("*"):
            with open(file, "r") as f:
                c = yaml.safe_load(f)
                conf.update(c)
        return cls(**{k: {i: Mapping(**conf[k][i]) for i in conf[k]} for k in conf})


class WrapDictConfig:
    def __init__(self, config, max_depth=1):
        for k, v in config.items():
            if isinstance(v, dict):
                v = WrapDictConfig(v, max_depth - 1)
            elif isinstance(v, list):
                v = [
                    WrapDictConfig(i, max_depth - 1) if isinstance(i, dict) else i
                    for i in v
                ]
            setattr(self, k, v)

    def __repr__(self):
        params = ", ".join(
            f"{k!r}={v!r}" for k, v in self.__dict__.items() if not k.startswith("_")
        )
        return f"WrapDictConfig({params})"

    def __str__(self):
        params = ", ".join(
            f"{k!s}={v!s}" for k, v in self.__dict__.items() if not k.startswith("_")
        )
        return f"WrapDictConfig({params})"


def handle_requests(
    *,
    attribute: str,
    endpoint: str,
    method: str = "GET",
    level: str = None,
    private: bool = False,
    transform_output: bool = True,
    use_defaults: bool = True,
    filepath: str = "rest-api",
    filename: str = None,
    logger: logging.Logger | Any = _logger,
):
    """Decorator that does 3 things:
    1. transforms the input from the standard mapping
    to the exchange mapping.
    2. Checks that all the required arguments are set.
    3. Transforms the output and remap it to the standard
    mapping from the exchange mapping.
    """

    filename = filename or attribute

    def wrap(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):

            mapping = getattr(self.mappings, attribute).get(endpoint)
            defaults = mapping.defaults
            # If keyword arguments are present they are used with defaults
            # a default attribute will be overriden if it is present in kwargs.
            if use_defaults and defaults:
                logger.info(f"Using default arguments: {defaults=}")
                kwargs = {**defaults, **kwargs}

            check_required(mapping, **kwargs)

            params = build_params(mapping, **kwargs)

            ept = getattr(self.endpoints, endpoint)
            result = await self.request(
                method=method, endpoint=ept, params=params, private=private
            )
            success, error_code, error_message = self.validate_http_response(result)
            if not success:
                _logger.error(
                    f"Request to {ept} failed. {error_code=}, {error_message=}"
                )
                raise ExchangeError(error_message)

            # Dump raw data for backup
            if self.auto_dump:
                datestr = datetime.today().strftime("%Y-%m-%d")
                source_dir = os.path.join(
                    settings.REST_DIR, self.name, filepath, datestr
                )
                os.makedirs(source_dir, exist_ok=True)
                if level:
                    file = f"{filename}_{kwargs.get(level)}"
                file = f"{filename}.json"
                fullpath = os.path.join(source_dir, file)
                logger.info(f"Dumping data to {fullpath}")
                with open(fullpath, "w") as f:
                    json.dump(result, f)

            if not mapping:
                raise ValueError(f"Mapping missing for {self.__name__}@{endpoint=}")

            outputs = mapping.outputs
            if not outputs:
                logger.warning(f"Missing results mapping for {endpoint=}")

            if outputs and transform_output:
                if level:
                    outputs = outputs[kwargs[level]]
                result = apply_map(outputs, result)
            return result

        return wrapper

    return wrap


def callback_mapper(
    *,
    attribute: str,
    endpoint: str,
    level: str = None,
    logger: logging.Logger | Any = _logger,
):
    def wrap(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            mapping: Mapping = getattr(self.mappings, attribute).get(endpoint)
            results = mapping.results
            if results:
                if level:
                    results = results[kwargs[level]]
                kwargs = apply_map(results, kwargs)
            else:
                logger.warning(f"Missing results mapping for {endpoint=}")
            return func(*args, **kwargs)

        return wrapper

    return wrap


def apply_map(
    mapping: Dict[str, str],
    content: Dict[str, Any] | Any,
    to_dict=False,
    prefix: str = "",
) -> Dict[str, Any]:
    """Creates a new dictionnay that maps an exchange keys to
    cryptoex standard keys. It supports values that are either
    numbers or characters, dicts of those or lists of dicts of
    those.

    Parameters
    ----------

    mapping: The mapping of the exchange in question that maps
        exchange keys with standard ones

    content: The result of a REST or Websocket API as a dictionnary
    """
    if to_dict and isinstance(content, list):
        result = {}
        for i, v in enumerate(content):
            result[mapping.get(f"{prefix}.{i}", i)] = v
        return result

    if not isinstance(content, dict):
        return content

    std_content = {}
    for k, v in content.items():
        key = mapping.get(k, k)
        if isinstance(v, dict):
            std_content[key] = apply_map(mapping, v)
        elif isinstance(v, list):
            std_content[key] = [
                apply_map(mapping, e, to_dict=True, prefix=k) for e in v
            ]
        else:
            std_content[key] = v
    return std_content


def check_required(
    mapping: Mapping,
    **kwargs,
):

    required = mapping.required or []
    cond_required = mapping.cond_required or {}
    # Handles missing required attributes
    missing = []
    for k in required:
        if k not in kwargs:
            missing.append(k)

    if missing:
        n = len(missing)
        raise TypeError(f"{n} missing attribute{'s'[:n != 1]}: {', '.join(missing)}")

    # Handles conditionally required attributes. meaning that if an attribute
    # is set while it requires another attribute to be set, then raise an error
    if cond_required:
        cond_missing = []
        cond_fields = []
        for k in kwargs:
            v = kwargs[k]
            if v in cond_required:
                req = None
                for c in cond_required[v]:
                    found = False
                    for e in c.split(" or "):
                        if e in kwargs:
                            found = True
                            break

                    if not found:
                        req = c if req is None else ", ".join((req, c))
                if req:
                    cond_fields.append(f"{k}={v}")
                    cond_missing.append(req)
        msg = ""
        for i, f in enumerate(cond_fields):
            msg = "\n".join((msg, f"Used {f} but we are missing: {cond_missing[i]}"))
        if msg:
            raise TypeError(msg)


def build_params(mapping: Mapping, **kwargs) -> Dict[str, Any]:

    if not mapping.inputs:
        return kwargs
    params = {}
    for k in kwargs:
        if k in mapping.inputs:
            params[mapping.inputs[k]] = kwargs[k]

    return params


exchanges_config = WrapDictConfig(_get_config())
