# ============================================================
#  deribit_client.py — minimal Deribit v2 JSON-RPC (HTTP) client.
#  TESTNET by default (test.deribit.com). OAuth client_credentials.
#  Option amounts are in BTC (1 contract = 1 BTC); premium prices in BTC.
# ============================================================
import time
import requests

TESTNET = "https://test.deribit.com"
LIVE = "https://www.deribit.com"


class DeribitError(Exception):
    pass


class Deribit:
    def __init__(self, client_id, client_secret, testnet=True):
        self.base = (TESTNET if testnet else LIVE) + "/api/v2"
        self.cid = client_id or ""
        self.csec = client_secret or ""
        self.s = requests.Session()
        self._token = None
        self._token_exp = 0

    def _call(self, method, params=None, auth=False):
        if auth:
            self._ensure_token()
            self.s.headers.update({"Authorization": "Bearer " + self._token})
        r = self.s.get(f"{self.base}/{method}", params=params or {}, timeout=15)
        d = r.json()
        if "error" in d and d["error"]:
            raise DeribitError(f"{method}: {d['error']}")
        return d["result"]

    # ── auth ───────────────────────────────────────────────
    def _ensure_token(self):
        if self._token and time.time() < self._token_exp - 30:
            return
        r = self.s.get(f"{self.base}/public/auth", params={
            "grant_type": "client_credentials", "client_id": self.cid,
            "client_secret": self.csec}, timeout=15).json()
        if "error" in r and r["error"]:
            raise DeribitError(f"auth: {r['error']}")
        res = r["result"]
        self._token = res["access_token"]
        self._token_exp = time.time() + res.get("expires_in", 900)

    # ── public ─────────────────────────────────────────────
    def index_price(self, name="btc_usd"):
        return self._call("public/get_index_price", {"index_name": name})["index_price"]

    def instruments(self, currency="BTC"):
        return self._call("public/get_instruments", {"currency": currency, "kind": "option", "expired": "false"})

    def ticker(self, instrument):
        return self._call("public/ticker", {"instrument_name": instrument})

    # ── private ────────────────────────────────────────────
    def account(self, currency="BTC"):
        return self._call("private/get_account_summary", {"currency": currency, "extended": "true"}, auth=True)

    def positions(self, currency="BTC"):
        return self._call("private/get_positions", {"currency": currency, "kind": "option"}, auth=True)

    def open_orders(self, currency="BTC"):
        return self._call("private/get_open_orders_by_currency", {"currency": currency, "kind": "option"}, auth=True)

    def sell(self, instrument, amount, price=None, post_only=True, reduce_only=False):
        p = {"instrument_name": instrument, "amount": amount}
        if price is None:
            p["type"] = "market"
        else:
            p.update({"type": "limit", "price": price, "post_only": "true" if post_only else "false"})
        if reduce_only:
            p["reduce_only"] = "true"
        return self._call("private/sell", p, auth=True)

    def buy(self, instrument, amount, price=None, post_only=True, reduce_only=False):
        p = {"instrument_name": instrument, "amount": amount}
        if price is None:
            p["type"] = "market"
        else:
            p.update({"type": "limit", "price": price, "post_only": "true" if post_only else "false"})
        if reduce_only:
            p["reduce_only"] = "true"
        return self._call("private/buy", p, auth=True)

    def cancel_all(self):
        return self._call("private/cancel_all", {}, auth=True)
