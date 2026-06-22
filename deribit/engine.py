# ============================================================
#  engine.py — Deribit BTC options: weekly CASH-SECURED PUT seller.
#   Sell a ~OTM weekly put (collect premium = harvest the VRP). Take profit
#   at TP% of premium, else hold to expiry (Deribit auto-settles); then roll.
#   Optional defined-risk: buy a further-OTM put wing (credit spread).
#   P&L tracked via Deribit account equity delta (real, includes fees).
# ============================================================
import os, json, time, copy, logging, threading
from datetime import datetime, timezone
from deribit_client import Deribit, DeribitError

log = logging.getLogger("engine")
def _now(): return datetime.now(timezone.utc)


class Engine:
    def __init__(self, cfg):
        self.cfg = cfg
        self.dx = Deribit(cfg["client_id"], cfg["client_secret"], testnet=cfg["testnet"])
        self.lock = threading.Lock(); self._stop = False
        self.realized_btc = 0.0; self.wins = 0; self.losses = 0
        self.short_inst = None; self.wing_inst = None
        self._eq_entry = None; self._confirmed = False; self._entry_prem = None
        self.state = {
            "status": "starting", "auth_ok": False, "auth_msg": "",
            "trading_enabled": cfg["trading_enabled"], "testnet": cfg["testnet"],
            "strategy": f"Weekly cash-secured PUT ~{int(cfg['otm_pct']*100)}% OTM"
                        + (" + defined-risk wing" if cfg["spread"] else ""),
            "currency": "BTC", "otm_pct": cfg["otm_pct"], "dte_min": cfg["dte_min"],
            "contracts": cfg["contracts"], "tp_pct": cfg["tp_pct"], "spread": cfg["spread"],
            "index": None, "equity_btc": None, "equity_usd": None, "avail_btc": None,
            "position": None, "realized_btc": 0.0, "realized_usd": 0.0,
            "wins": 0, "losses": 0, "trades": [], "log": [], "last_update": None,
        }
        self.hist = os.path.join(os.path.dirname(os.path.abspath(__file__)), "opt_history.json")
        self._all = []; self._load()

    def _load(self):
        try:
            d = json.load(open(self.hist))
            self.realized_btc=float(d.get("realized_btc",0)); self.wins=int(d.get("wins",0)); self.losses=int(d.get("losses",0))
            self._all=d.get("trades",[]); self.state.update({"realized_btc":round(self.realized_btc,6),"wins":self.wins,"losses":self.losses,"trades":self._all[:30]})
        except FileNotFoundError: pass
        except Exception as e: self._emit(f"history load failed: {e}")

    def _save(self):
        try:
            tmp=self.hist+".tmp"; json.dump({"realized_btc":self.realized_btc,"wins":self.wins,"losses":self.losses,"trades":self._all[:500]},open(tmp,"w")); os.replace(tmp,self.hist)
        except Exception as e: self._emit(f"history save failed: {e}")

    def _emit(self,m):
        self.state["log"]=([_now().strftime("%m-%d %H:%M:%S")+"  "+m]+self.state["log"])[:60]; log.info(m)

    def snapshot(self):
        with self.lock: return copy.deepcopy(self.state)

    def start(self):
        threading.Thread(target=self._run,daemon=True,name="engine").start()

    def _setup(self):
        if not self.cfg["client_id"]:
            self.state["auth_msg"]="no API key"; self._emit("no Deribit credentials -> signals only"); return
        try:
            acc=self.dx.account()
            self.state["auth_ok"]=True
            self.state["equity_btc"]=acc.get("equity"); self.state["avail_btc"]=acc.get("available_funds")
            self._emit(f"Auth OK -> equity {acc.get('equity'):.4f} BTC (testnet={self.cfg['testnet']})")
            if self.cfg["trading_enabled"]:
                try:
                    self.dx.cancel_all()
                    for p in self.dx.positions():
                        sz = p.get("size", 0)
                        if sz < -1e-9:
                            self.dx.buy(p["instrument_name"], abs(sz), price=None, reduce_only=True); self._emit(f"startup flatten {p['instrument_name']} {sz}")
                        elif sz > 1e-9:
                            self.dx.sell(p["instrument_name"], abs(sz), price=None, reduce_only=True); self._emit(f"startup flatten {p['instrument_name']} {sz}")
                except Exception as e:
                    self._emit(f"startup cleanup: {e}")
        except Exception as e:
            self.state["auth_msg"]=str(e); self._emit(f"AUTH FAILED: {e} -> signals only")

    def _run(self):
        self._setup()
        with self.lock: self.state["status"]="running"
        while not self._stop:
            try:
                with self.lock: self._tick()
            except Exception as e: self._emit(f"tick error: {e}")
            with self.lock: self.state["last_update"]=_now().isoformat()
            time.sleep(self.cfg["poll_seconds"])

    def _pick_put(self, index):
        """Pick nearest expiry >= dte_min days, strike closest to index*(1-otm)."""
        insts=self.dx.instruments()
        puts=[x for x in insts if x.get("option_type")=="put"]
        now=time.time()*1000
        exps=sorted({x["expiration_timestamp"] for x in puts
                     if (x["expiration_timestamp"]-now)/86400000 >= self.cfg["dte_min"]})
        if not exps: return None,None
        exp=exps[0]
        target=index*(1-self.cfg["otm_pct"])
        cands=[x for x in puts if x["expiration_timestamp"]==exp]
        sell=min(cands,key=lambda x:abs(x["strike"]-target))
        wing=None
        if self.cfg["spread"]:
            wtgt=index*(1-self.cfg["otm_pct"]-self.cfg["spread_width"])
            below=[x for x in cands if x["strike"]<sell["strike"]]
            if below: wing=min(below,key=lambda x:abs(x["strike"]-wtgt))
        return sell,wing

    def _tick(self):
        index=self.dx.index_price(); self.state["index"]=round(index,2)
        live=self.state["trading_enabled"] and self.state["auth_ok"]
        if self.state["auth_ok"]:
            acc=self.dx.account(); self.state["equity_btc"]=round(acc.get("equity",0),6)
            self.state["avail_btc"]=round(acc.get("available_funds",0),6); self.state["equity_usd"]=round(acc.get("equity",0)*index,2)
        if not live: return
        # current open SHORT option position (our trade), if any
        pos = [p for p in self.dx.positions() if p.get("size", 0) < -1e-9
               and p["instrument_name"].endswith("-P")]
        cur = pos[0] if pos else None

        # ---- close detection (only if a fill was previously confirmed) ----
        if self._confirmed and cur is None:
            eq = self.dx.account().get("equity", 0)
            pnl = (eq - self._eq_entry) if self._eq_entry is not None else 0.0
            self.realized_btc += pnl
            (self.wins, self.losses) = (self.wins+1, self.losses) if pnl >= 0 else (self.wins, self.losses+1)
            tr = {"inst": self.short_inst, "pnl_btc": round(pnl, 6), "pnl_usd": round(pnl*index, 2), "closed": _now().strftime("%m-%d %H:%M")}
            self._all = [tr] + self._all
            self.state.update({"trades": self._all[:30], "realized_btc": round(self.realized_btc, 6),
                               "realized_usd": round(self.realized_btc*index, 2), "wins": self.wins, "losses": self.losses})
            self._save(); self._emit(f"CLOSED {self.short_inst} pnl={pnl:+.6f} BTC (~${pnl*index:+.2f})")
            self.short_inst=None; self._confirmed=False; self._eq_entry=None
            try: self.dx.cancel_all()
            except: pass

        # ---- manage open short put ----
        if cur is not None:
            self.short_inst = cur["instrument_name"]
            if not self._confirmed:
                self._confirmed = True
                self._emit(f"FILLED short {self.short_inst} size {cur['size']}")
            tk = self.dx.ticker(self.short_inst); mark = tk.get("mark_price", 0)
            entry_prem = getattr(self, "_entry_prem", None)
            self.state["position"] = {"inst": self.short_inst, "size": cur.get("size"),
                                      "entry_premium": entry_prem, "mark": mark,
                                      "delta": round(cur.get("delta", 0), 3),
                                      "upnl_btc": round(cur.get("floating_profit_loss", 0), 6)}
            if entry_prem and mark > 0 and mark <= entry_prem*(1-self.cfg["tp_pct"]):
                try:
                    self.dx.buy(self.short_inst, abs(cur["size"]), price=None, reduce_only=True)
                    self._emit(f"TAKE-PROFIT buy-back {self.short_inst} @mark {mark:.4f} (entry {entry_prem:.4f})")
                except DeribitError as e: self._emit(f"TP buyback failed: {e}")
            return

        # ---- flat: open a new short put (marketable so it actually fills) ----
        self.state["position"] = None
        try: self.dx.cancel_all()
        except: pass
        sell, wing = self._pick_put(index)
        if not sell: self._emit("no expiry >= dte_min found"); return
        tk = self.dx.ticker(sell["instrument_name"])
        bid = tk.get("best_bid_price") or 0
        mark = tk.get("mark_price") or 0
        px = bid if bid > 0 else mark
        if not px or px <= 0: self._emit(f"no price for {sell['instrument_name']}"); return
        self._eq_entry = self.dx.account().get("equity", 0)   # snapshot BEFORE selling
        try:
            if wing:
                self.dx.buy(wing["instrument_name"], self.cfg["contracts"], price=None)
            # marketable limit at the bid (post_only off) -> fills immediately
            self.dx.sell(sell["instrument_name"], self.cfg["contracts"], price=round(px, 4), post_only=False)
            self.short_inst = sell["instrument_name"]; self._entry_prem = px; self._confirmed = False
            self._emit(f"SELL PUT {sell['instrument_name']} x{self.cfg['contracts']} @ {px:.4f} BTC (strike {sell['strike']})"
                       + (f" + wing {wing['instrument_name']}" if wing else ""))
        except DeribitError as e:
            self._emit(f"sell put failed: {e}")
