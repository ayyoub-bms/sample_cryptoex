from typing import Any, Dict, TypeAlias, List

Timestamp: TypeAlias = float


class AbstractFormatter:

    @staticmethod
    def format_quotes(
        message: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Make the orderbook messages uniform across exchanges.

        The result should be of the following format:
        {
            topic: topic,  # The topic of interest (the way you subscribe to orderbook)
            type: type,  # Whether its a snapshot message or a delta message
            engine_timestamp: engine_timestamp,  # The time the engine produced the data
            bids: [...],
            asks: [...]
        }

        Parameters
        ----------

        message: dict
            Either a snapshot message or a delta message sent by the exchange.
        """
        return message

    @staticmethod
    def format_trades(
        message: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Make the trades message uniform across exchanges.

        The result should be of the following format:
        {
            topic: topic,  # The topic of interest (the way you subscribe to orderbook)
            trades: [...]  # List of all the trades received in the message
        }

        Parameters
        ----------

        message: dict
            The trades message sent by the exchange.
        """
        return message

    @staticmethod
    def format_announcements(
        announcements: Dict[str, Any], last_updated: Timestamp = 0
    ) -> List[Dict[str, str | List[str]]]:
        return announcements

    @staticmethod
    def format_instruments(
        instruments_groups: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        return instruments_groups

    @staticmethod
    def format_wallets(
        wallet_accounts: List[Dict[str, Any]],
    ) -> Dict[str, Dict[str, Any]]:
        return wallet_accounts
