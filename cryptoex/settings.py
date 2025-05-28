import os
import logging
import logging.config
from pathlib import Path
from dotenv import load_dotenv

CONFIG_DIR = os.path.join(
    os.environ.get("APPDATA")
    or os.environ.get("XDG_CONFIG_HOME")
    or os.path.join(os.environ["HOME"], ".config"),
    "cryptoex",
)

try:
    DEFAULT_LOG_DIR = os.path.join(os.environ["LOCALAPPDATA"], "cryptoex/logs")
except KeyError:
    DEFAULT_LOG_DIR = "/var/log/cryptoex/"

load_dotenv(f"{CONFIG_DIR}/cryptoex.env")

LOGS_PATH = os.getenv("LOGS_DIR", DEFAULT_LOG_DIR)


DATA_PATH = os.getenv(
    "DATA_DIR",
    os.path.join(
        os.getenv("APPDATA") or os.path.join(os.getenv("HOME"), ".local/share"),
        "cryptoex",
    ),
)

EXCHANGES_DIR = os.getenv("EXCHANGES_DIR", os.path.join(CONFIG_DIR, "exchanges"))
MAPPINGS_DIR = os.getenv("MAPPINGS_DIR", os.path.join(EXCHANGES_DIR, "mappings"))
ENDPOINTS_DIR = os.getenv("ENDPOINTS_DIR", os.path.join(EXCHANGES_DIR, "endpoints"))
PCAP_DIR = os.getenv("PCAP_DIR", os.path.join(DATA_PATH, "pcap-files"))
REST_DIR = os.getenv("REST_DIR", os.path.join(DATA_PATH, "rest-files"))
STREAM_DIR = os.getenv("STREAM_DIR", os.path.join(DATA_PATH, "stream-files"))

EXCHANGES_CONFIG_PATH = os.path.join(EXCHANGES_DIR, "exchanges.yml")

Path(DATA_PATH).mkdir(parents=True, exist_ok=True)


def _setup_logging():
    logging.config.fileConfig(
        os.path.join(CONFIG_DIR, "logging.ini"),
        defaults={"filename": os.path.join(LOGS_PATH, "cryptoex.log")},
    )
