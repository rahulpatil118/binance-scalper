# ============================================================
#  binance_client.py — Binance REST + WebSocket Client
# ============================================================
import time
import logging
import pandas as pd
from binance.client import Client
from binance.exceptions import BinanceAPIException
from config import (TESTNET_API_KEY, TESTNET_API_SECRET,
                    LIVE_API_KEY, LIVE_API_SECRET,
                    USE_TESTNET, SYMBOL, INTERVAL, ORDERBOOK_DEPTH)

log = logging.getLogger("BinanceClient")


class BinanceClient:
    def __init__(self):
        from config import USE_FUTURES, FUTURES_LEVERAGE, MARGIN_TYPE

        # Initialize client (works for both spot and futures)
        if USE_TESTNET:
            self.client = Client(TESTNET_API_KEY, TESTNET_API_SECRET,
                                 testnet=True)
            if USE_FUTURES:
                log.info("✅  Connected to Binance FUTURES TESTNET")
            else:
                log.info("✅  Connected to Binance SPOT TESTNET")
        else:
            self.client = Client(LIVE_API_KEY, LIVE_API_SECRET)
            if USE_FUTURES:
                log.info("🔴  Connected to Binance FUTURES LIVE")
            else:
                log.info("🔴  Connected to Binance SPOT LIVE — USE CAUTION")

        # Set leverage and margin type for futures
        if USE_FUTURES:
            try:
                self.client.futures_change_leverage(symbol=SYMBOL, leverage=FUTURES_LEVERAGE)
                try:
                    self.client.futures_change_margin_type(symbol=SYMBOL, marginType=MARGIN_TYPE)
                except:
                    pass  # Already set
                log.info(f"✅  Leverage={FUTURES_LEVERAGE}x | Margin={MARGIN_TYPE}")
            except Exception as e:
                log.warning(f"Leverage setup: {e} (may already be set)")

        self.is_futures = USE_FUTURES

    # ── Market data ───────────────────────────────────────────
    def get_klines(self, symbol: str = SYMBOL,
                   interval: str = INTERVAL,
                   limit: int = 200) -> pd.DataFrame:
        try:
            if self.is_futures:
                raw = self.client.futures_klines(
                    symbol=symbol, interval=interval, limit=limit)
            else:
                raw = self.client.get_klines(
                    symbol=symbol, interval=interval, limit=limit)
            df = pd.DataFrame(raw, columns=[
                "open_time","open","high","low","close","volume",
                "close_time","quote_vol","trades",
                "taker_base","taker_quote","ignore"
            ])
            for col in ["open","high","low","close","volume"]:
                df[col] = df[col].astype(float)
            df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
            df.set_index("open_time", inplace=True)
            return df[["open","high","low","close","volume"]]
        except BinanceAPIException as e:
            log.error(f"Klines error: {e}")
            return pd.DataFrame()

    def get_order_book(self, symbol: str = SYMBOL,
                        limit: int = ORDERBOOK_DEPTH) -> dict:
        try:
            if self.is_futures:
                ob = self.client.futures_order_book(symbol=symbol, limit=limit)
            else:
                ob = self.client.get_order_book(symbol=symbol, limit=limit)
            return {
                "bids": [[float(p), float(q)] for p, q in ob["bids"]],
                "asks": [[float(p), float(q)] for p, q in ob["asks"]],
            }
        except BinanceAPIException as e:
            log.error(f"Order book error: {e}")
            return {}

    def get_ticker(self, symbol: str = SYMBOL) -> dict:
        try:
            if self.is_futures:
                return self.client.futures_symbol_ticker(symbol=symbol)
            else:
                return self.client.get_symbol_ticker(symbol=symbol)
        except BinanceAPIException as e:
            log.error(f"Ticker error: {e}")
            return {}

    def get_account_balance(self, asset: str = "USDT") -> float:
        if self.is_futures:
            balance_info = self.get_futures_balance(asset)
            return balance_info["available"]
        else:
            try:
                info = self.client.get_asset_balance(asset=asset)
                return float(info["free"]) if info else 0.0
            except BinanceAPIException as e:
                log.error(f"Balance error: {e}")
                return 0.0

    # ── Order execution ───────────────────────────────────────
    def place_market_order(self, symbol: str, side: str,
                           quantity: float) -> dict:
        """
        side: 'BUY' or 'SELL'
        Returns order dict or empty dict on error.
        """
        try:
            if self.is_futures:
                order = self.client.futures_create_order(
                    symbol   = symbol,
                    side     = side,
                    type     = "MARKET",
                    quantity = quantity,
                )
            else:
                order = self.client.create_order(
                    symbol   = symbol,
                    side     = side,
                    type     = "MARKET",
                    quantity = quantity,
                )
            log.info(f"📋 Order placed: {side} {quantity} {symbol} "
                     f"| ID={order['orderId']}")
            return order
        except BinanceAPIException as e:
            log.error(f"Order error [{side} {quantity} {symbol}]: {e}")
            return {}

    def place_oco_order(self, symbol: str, side: str,
                        quantity: float, stop_price: float,
                        limit_price: float, take_profit_price: float) -> dict:
        """
        OCO = One-Cancels-the-Other (stop-loss + take-profit in one call).
        side should be opposite of entry: if BUY entry → SELL OCO
        """
        try:
            order = self.client.create_oco_order(
                symbol        = symbol,
                side          = side,
                quantity      = quantity,
                price         = str(round(take_profit_price, 2)),
                stopPrice     = str(round(stop_price, 2)),
                stopLimitPrice= str(round(limit_price, 2)),
                stopLimitTimeInForce="GTC",
            )
            log.info(f"🔒 OCO set: TP={take_profit_price:.2f} "
                     f"SL={stop_price:.2f}")
            return order
        except BinanceAPIException as e:
            log.error(f"OCO order error: {e}")
            return {}

    def cancel_order(self, symbol: str, order_id: int) -> bool:
        try:
            if self.is_futures:
                self.client.futures_cancel_order(symbol=symbol, orderId=order_id)
            else:
                self.client.cancel_order(symbol=symbol, orderId=order_id)
            return True
        except BinanceAPIException as e:
            log.error(f"Cancel error: {e}")
            return False

    def get_open_orders(self, symbol: str = SYMBOL) -> list:
        try:
            if self.is_futures:
                return self.client.futures_get_open_orders(symbol=symbol)
            else:
                return self.client.get_open_orders(symbol=symbol)
        except BinanceAPIException as e:
            log.error(f"Open orders error: {e}")
            return []

    # ── Symbol info ───────────────────────────────────────────
    def get_symbol_info(self, symbol: str = SYMBOL) -> dict:
        """Returns min qty, step size, min notional etc."""
        try:
            if self.is_futures:
                exchange_info = self.client.futures_exchange_info()
                info = next((s for s in exchange_info['symbols'] if s['symbol'] == symbol), None)
                if not info:
                    raise Exception(f"Symbol {symbol} not found")
            else:
                info = self.client.get_symbol_info(symbol)
            filters = {f["filterType"]: f for f in info["filters"]}
            return {
                "minQty":    float(filters["LOT_SIZE"]["minQty"]),
                "stepSize":  float(filters["LOT_SIZE"]["stepSize"]),
                "minNotional": float(filters.get("MIN_NOTIONAL", {}).get("minNotional", 10)),
                "tickSize":  float(filters["PRICE_FILTER"]["tickSize"]),
            }
        except Exception as e:
            log.error(f"Symbol info error: {e}")
            return {"minQty": 0.001, "stepSize": 0.001,
                    "minNotional": 10.0, "tickSize": 0.01}

    def round_qty(self, qty: float, step: float) -> float:
        from math import floor
        precision = len(str(step).rstrip("0").split(".")[-1]) if "." in str(step) else 0
        return round(floor(qty / step) * step, precision)

    # ── Futures-specific methods ──────────────────────────────
    def get_futures_balance(self, asset: str = "USDT") -> dict:
        """Get futures account balance and equity."""
        try:
            account = self.client.futures_account()
            for asset_info in account["assets"]:
                if asset_info["asset"] == asset:
                    return {
                        "available": float(asset_info["availableBalance"]),
                        "total_equity": float(asset_info["walletBalance"]),
                    }
            return {"available": 0.0, "total_equity": 0.0}
        except Exception as e:
            log.error(f"Futures balance error: {e}")
            return {"available": 0.0, "total_equity": 0.0}

    def calculate_liquidation_price(self, side: str, entry_price: float,
                                     leverage: int) -> float:
        """Calculate liquidation price for a position."""
        maintenance_margin_rate = 0.005  # 0.5% for BTC

        if side == "BUY" or side == "LONG":
            liq_price = entry_price * (1 - 1/leverage + maintenance_margin_rate)
        else:  # SELL/SHORT
            liq_price = entry_price * (1 + 1/leverage - maintenance_margin_rate)

        return liq_price

    def place_futures_market_order(self, symbol: str, side: str,
                                   quantity: float, reduce_only: bool = False) -> dict:
        """Place futures market order."""
        try:
            params = {
                "symbol": symbol,
                "side": side,
                "type": "MARKET",
                "quantity": quantity,
            }
            if reduce_only:
                params["reduceOnly"] = True

            order = self.client.futures_create_order(**params)
            log.info(f"📋 Futures: {side} {quantity} {symbol}")
            return order
        except Exception as e:
            log.error(f"Futures order error: {e}")
            return {}

    def place_futures_stop_loss(self, symbol: str, side: str,
                                quantity: float, stop_price: float) -> dict:
        """Place stop-loss order."""
        try:
            order = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type="STOP_MARKET",
                quantity=quantity,
                stopPrice=str(round(stop_price, 2)),
                reduceOnly=True,
            )
            log.info(f"🔒 Stop-loss: {side} @ {stop_price:.2f}")
            return order
        except Exception as e:
            log.error(f"Stop-loss error: {e}")
            return {}

    def get_funding_rate(self, symbol: str = SYMBOL) -> float:
        """Get current funding rate (positive = longs pay shorts)."""
        if not self.is_futures:
            return 0.0
        try:
            funding = self.client.futures_funding_rate(symbol=symbol, limit=1)
            if funding:
                return float(funding[0]["fundingRate"])
            return 0.0
        except Exception as e:
            log.error(f"Funding rate error: {e}")
            return 0.0

    def server_time_offset(self) -> int:
        """Returns clock difference in ms — important for signed requests."""
        server_time = self.client.get_server_time()["serverTime"]
        return server_time - int(time.time() * 1000)
