# selftest.py — validate the public Deribit path (no API keys needed):
# index price, weekly OTM put selection, and option pricing/greeks.
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from deribit_client import Deribit

dx = Deribit("", "", testnet=True)
idx = dx.index_price()
print("BTC index (testnet):", idx)

insts = dx.instruments()
puts = [x for x in insts if x.get("option_type") == "put"]
now = time.time()*1000
exps = sorted({x["expiration_timestamp"] for x in puts if (x["expiration_timestamp"]-now)/86400000 >= 5})
print("put expiries >=5d:", [time.strftime("%d%b%y", time.gmtime(e/1000)) for e in exps[:5]])
exp = exps[0]
target = idx*0.95
cands = [x for x in puts if x["expiration_timestamp"] == exp]
sell = min(cands, key=lambda x: abs(x["strike"]-target))
print("picked ~5% OTM weekly put:", sell["instrument_name"], "strike", sell["strike"], "(target", round(target), ")")
tk = dx.ticker(sell["instrument_name"])
print("  bid:", tk.get("best_bid_price"), "mark:", tk.get("mark_price"), "mark_iv:", tk.get("mark_iv"),
      "delta:", round((tk.get("greeks") or {}).get("delta", 0), 3))
prem = tk.get("best_bid_price") or tk.get("mark_price")
if prem:
    print(f"  -> selling 0.1 BTC of this put collects ~{prem*0.1:.5f} BTC (~${prem*0.1*idx:.2f}) premium")
print("PUBLIC PATH OK")
