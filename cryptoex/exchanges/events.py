import logging

_logger = logging.getLogger(__name__)


def write_headers(depth, trades_file, quotes_file, events_file):
    quotes_file.write(quote_headers(depth))
    quotes_file.write("\n")
    events_file.write(event_headers(depth))
    events_file.write("\n")
    trades_file.write(trade_headers())
    trades_file.write("\n")


def process_trade(trade):
    """Extract trade price and volume

    Process a message received from the exchange and extract:
        - trade_id
        - symbol
        - timestamp
        - side
        - price
        - volume
    see also: `trade_headers`
    """

    return ",".join(
        (
            trade["trade_id"],
            trade["symbol"],
            str(trade["engine_timestamp"]),
            str(trade["side"] == "Buy" and 1 or -1),
            trade["price"],
            trade["volume"],
        )
    )


def process_quote(message, depth):
    """Extract orderbook bid/ask prices and volumes from the message.

    Process a message received from the exchange and extract only relevant data:
        - Timestamp
        - symbol
        - bid prices
        - ask prices
        - bid volumes
        - ask volumes
    see also: `quote_headers`
    """
    bsize = len(message["bids"]) - depth
    bid_data = sorted(message["bids"], key=lambda x: x["price"])[bsize:]
    ask_data = sorted(message["asks"], key=lambda x: x["price"])[:depth]
    ts = message["engine_timestamp"]
    symbol = message["symbol"]
    bid_p = [d["price"] for d in bid_data]
    bid_q = [d["volume"] for d in bid_data]
    ask_p = [d["price"] for d in ask_data]
    ask_q = [d["volume"] for d in ask_data]

    quotes = f"{ts},{symbol}"
    quotes = f"{quotes},{','.join(bid_p)}"
    quotes = f"{quotes},{','.join(ask_p)}"
    quotes = f"{quotes},{','.join(bid_q)}"
    quotes = f"{quotes},{','.join(ask_q)}"

    return quotes


def process_event(depth, event):
    """Extract event data from quote/trade messages

        - Timestamp
        - symbol
        - bid prices
        - ask prices
        - bid events
        - ask events
        - bid volumes
        - ask volumes

    see also: `event_headers`
    """
    size = len(event["bids"]) - depth
    event["bids"] = sorted(event["bids"], key=lambda x: x[0])[size:]
    event["asks"] = sorted(event["asks"], key=lambda x: x[0])[:depth]

    bid_p, bid_e, bid_s = list(zip(*event["bids"]))
    ask_p, ask_e, ask_s = list(zip(*event["asks"]))
    return ",".join(
        [
            str(event["timestamp"]),
            event["symbol"],
            ",".join(bid_p),
            ",".join(ask_p),
            ",".join(bid_e),
            ",".join(ask_e),
            ",".join(bid_s),
            ",".join(ask_s),
        ]
    )


def write_trades(depth, trades, previous_quote, trades_file, events_file):
    """Writes trade details and events to file"""
    for trade in trades:
        event = {
            "timestamp": trade["engine_timestamp"],
            "symbol": previous_quote["symbol"],
        }
        trades_file.write(process_trade(trade))
        trades_file.write("\n")
        side = trade["side"] == "Sell" and "bids" or "asks"
        other_side = trade["side"] == "Sell" and "asks" or "bids"
        event[side] = {k["price"]: [k["price"], "", ""] for k in previous_quote[side]}
        event[other_side] = sorted(
            [[k["price"], "", ""] for k in previous_quote[other_side]],
            key=lambda x: x[0],
        )
        event[side][trade["price"]] = [trade["price"], "M", f"-{trade["volume"]}"]
        event[side] = sorted(event[side].values(), key=lambda x: x[0])
        events_file.write(process_event(depth, event))
        events_file.write("\n")


def write_quote(
    depth, current_quote, previous_quote, current_trades, quotes_file, events_file
):
    """Writes quote details and events to file"""
    if not current_quote["is_snapshot"]:
        uid = current_quote["update_id"]
        puid = previous_quote["update_id"]
        if uid <= puid:
            _logger.warning(
                f"Received an update id {uid} lower "
                f"than in the previous message {puid}"
            )

        data = {}
        event = {
            "timestamp": current_quote["engine_timestamp"],
            "symbol": current_quote["symbol"],
        }
        for side in ("bids", "asks"):
            quotes = current_quote[side]
            previous_quotes = {q["price"]: q["volume"] for q in previous_quote[side]}
            if current_trades:
                for trade in current_trades:
                    trade_side = trade["side"] == "Sell" and "bids" or "asks"
                    if trade_side == side:
                        price = trade["price"]
                        if price in previous_quotes:
                            old_volume = float(previous_quotes[price])
                            vol_diff = old_volume - float(trade["volume"])
                            if vol_diff == 0:
                                # The price/volume is not needed
                                del previous_quotes[price]
                            else:
                                previous_quotes[price] = str(vol_diff)
                        else:
                            raise ValueError(
                                f"Unable to find {price=}\n\n"
                                f"\t{current_quote}\n\n"
                                f"\t{previous_quote}\n\n"
                                f"\t{current_trades}\n\n"
                            )

                        if old_volume < 0:
                            raise ValueError(
                                f"Negative volume encoutered:\n"
                                f"\tTrade:\n\n{trade}\n"
                                f"\tQuote:\n\n{previous_quote}"
                            )
            event[side] = {
                q["price"]: [q["price"], "", ""] for q in previous_quote[side]
            }
            for quote in quotes:
                price = quote["price"]
                volume = quote["volume"]
                if volume == "0":
                    if price in previous_quotes and float(previous_quotes[price]) != 0:
                        event[side][price] = [price, "C", f"-{previous_quotes[price]}"]
                        del previous_quotes[price]
                    else:
                        _logger.warning(
                            f"Received data for a missing {price=}"
                            f"with a volume=0. Event with {uid=}"
                        )
                else:
                    volume_diff = float(previous_quotes.get(price, 0)) - float(volume)
                    if volume_diff > 0:
                        # add cancel
                        event[side][price] = [price, "C", f"-{volume}"]
                    elif volume_diff < 0:
                        # add insert
                        event[side][price] = [price, "I", volume]
                    previous_quotes[price] = volume
            data[side] = [{"price": p, "volume": v} for p, v in previous_quotes.items()]
            event[side] = event[side].values()

        current_quote |= data
    current_quote["type"] = "snapshot"
    quotes_str = process_quote(current_quote, depth)
    quotes_file.write(quotes_str)
    quotes_file.write("\n")
    if previous_quote:
        events_file.write(process_event(depth, event))
        events_file.write("\n")
    return current_quote


def event_headers(depth):
    return ",".join(
        ["timestamp"]
        + [f"BidPrice{i}" for i in range(depth, 0, -1)]
        + [f"AskPrice{i}" for i in range(1, depth + 1)]
        + [f"BidEvent{i}" for i in range(depth, 0, -1)]
        + [f"AskEvent{i}" for i in range(1, depth + 1)]
        + [f"BidSize{i}" for i in range(depth, 0, -1)]
        + [f"AskSize{i}" for i in range(1, depth + 1)]
    )


def quote_headers(depth):
    return ",".join(
        ["timestamp", "symbol"]
        + [f"BidPrice{i}" for i in range(depth, 0, -1)]
        + [f"AskPrice{i}" for i in range(1, depth + 1)]
        + [f"BidSize{i}" for i in range(depth, 0, -1)]
        + [f"AskSize{i}" for i in range(1, depth + 1)]
    )


def trade_headers():
    return "trade_id,symbol,timestamp,side,price,volume"
