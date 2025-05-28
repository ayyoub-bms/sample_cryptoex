import json
import pandas as pd

from datetime import datetime

from typing import Dict, Any, List
from cryptoex.utils import assign_dtypes
from cryptoex.exchanges.formatters import AbstractFormatter, Timestamp


class BybitFormatter(AbstractFormatter):

    @staticmethod
    def format_wallets(
        wallet_accounts: List[Dict[str, Any]],
    ) -> Dict[str, Dict[str, Any]]:
        summary_filters = (
            "wallet_balance",
            "total_equity",
            "available_balance",
            "initial_margin",
            "maintenance_margin",
        )

        coin_filters = (
            "coin",
            "coin_balance",
            "equity",
            "usd_value",
            "position_im",
            "position_mm",
        )

        wallets = {}
        for wallet in wallet_accounts:
            account = wallet["account_type"]
            summary = {f: wallet.pop(f) for f in summary_filters}
            wallet["summary"] = summary

            coins = wallet["coin"]
            for i in range(len(coins)):
                coins[i] = {k: coins[i][k] for k in coin_filters}

            for f in wallet:
                if f not in ("summary", "coin"):
                    wallet.pop(f)
            wallets[account] = wallet
        return wallets

    @staticmethod
    def format_quotes(message: Dict[str, Any]) -> Dict[str, Any]:
        data = message["data"]
        data["engine_timestamp"] = message["engine_timestamp"]
        data["topic"] = message["topic"]
        data["is_snapshot"] = message["type"] == "snapshot"
        return data

    @staticmethod
    def format_trades(message: Dict[str, Any]) -> Dict[str, Any]:
        data = {}
        data["trades"] = message["data"]
        data["topic"] = message["topic"]
        return data["trades"]

    @staticmethod
    def format_announcements(
        announcements: Dict[str, Any], last_updated: Timestamp = 0
    ) -> List[Dict[str, str | List[str]]]:

        announcements = [
            announcement
            for announcement in announcements["announcements"]
            if announcement.get("publish_time", 0) >= last_updated
        ]

        for a in announcements:
            a["type"] = a["type"]["title"]  # The key might be used as well
            if "publish_time" in a:
                a["published"] = datetime.fromtimestamp(
                    a["publish_time"] // 1000
                ).strftime(format="%Y-%m-%d %H:%M:%S")
                del a["publish_time"]

            a["fill_time"] = datetime.fromtimestamp(a["date_ts"] // 1000).strftime(
                format="%Y-%m-%d %H:%M:%S"
            )
            a["end_date"] = datetime.fromtimestamp(a["end_date_ts"] // 1000).strftime(
                format="%Y-%m-%d %H:%M:%S"
            )
            a["start_date"] = datetime.fromtimestamp(
                a["start_date_ts"] // 1000
            ).strftime(format="%Y-%m-%d %H:%M:%S")
            del a["date_ts"]
            del a["end_date_ts"]
            del a["start_date_ts"]

        return announcements

    @staticmethod
    def format_instruments(
        instruments_groups: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        result_dict = {}
        for category in instruments_groups:
            instruments = instruments_groups[category]["instruments"]
            result_dict[category] = {}
            for instrument in instruments:
                level = instrument.pop("lot_size_details")
                instrument.update(level)
                level = instrument.pop("price_details")
                instrument.update(level)

                match category:
                    case "spot":
                        level = instrument.pop("risk_parameters")
                        instrument.update(level)
                        instrument["margin_trading"] = (
                            instrument["margin_trading"] == "utaOnly"
                        )
                    case "linear" | "inverse":
                        level = instrument.pop("risk_parameters")
                        instrument.update(level)
                        level = instrument.pop("leverage_details")
                        instrument.update(level)
                        instrument["margin_trading"] = instrument["unified_margin_trade"]

                    case "option":
                        instrument["margin_trading"] = None

                result_dict[category][instrument["symbol"]] = instrument
        return result_dict

    @staticmethod
    def aggregate_trades(trades_file_path):
        trades_data = []
        trades_meta = []

        with open(trades_file_path) as file:

            for line in file:
                line = json.loads(line)
                topic_name = line["topic"]
                data_type = line["type"]
                engine_timestamp = line["engine_timestamp"]
                for data in line["data"]:

                    trades_data.append(
                        [
                            data["symbol"],
                            1 if data["side"] == "Buy" else -1,
                            data["volume"],
                            data["price"],
                            data["trade_id"],
                            data["is_block_trade"],
                        ]
                    )
                trades_meta.append([topic_name, data_type, engine_timestamp])

            df_trades_metadata = _format_trades_meta(trades_meta)
            df_trades = _format_trades(trades_data)
            df_trades.index = df_trades_metadata.index
        return df_trades, df_trades_metadata

    @staticmethod
    def aggregate_events(events_file_path):
        pass


@assign_dtypes(trade_id="str", symbol="str", direction="str")
def _format_trades(data):
    trades_columns = [
        "symbol",
        "side",
        "volume",
        "price",
        "trade_id",
        "is_block",
    ]
    df_trades = pd.DataFrame(data=data, columns=trades_columns)
    df_trades.index.name = "Timestamp"
    df_trades.name = "TRADES"
    return df_trades


@assign_dtypes(default="str")
def _format_trades_meta(data):
    meta_columns = ["topic_name", "data_type", "engine_timestamp"]
    df_trades_metadata = pd.DataFrame(data=data, columns=meta_columns)
    df_trades_metadata.set_index("engine_timestamp", inplace=True)
    return df_trades_metadata


@assign_dtypes(default="str")
def _format_quotes_meta(data):
    meta_columns = [
        "engine_timestamp",
        "seq_id",
        "update_id",
        "topic_name",
        "data_type",
        "system_timestamp",
    ]
    df_quotes_metadata = pd.DataFrame(data=data, columns=meta_columns)
    df_quotes_metadata.set_index("engine_timestamp", inplace=True)
    return df_quotes_metadata


@assign_dtypes()
def _format_quotes(data, depth):
    try:
        quotes_columns = BybitFormatter.get_quote_headers(depth)
        df_quotes = pd.DataFrame(data=data, columns=quotes_columns, dtype=float)
    except ValueError:
        print(data)
        raise
    df_quotes.index.name = "Timestamp"
    df_quotes.columns.name = "Depth"
    df_quotes.name = "QUOTES"
    return df_quotes
