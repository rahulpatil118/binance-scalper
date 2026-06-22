# app.py — Flask dashboard + entry point for the Deribit cash-secured-put bot.
import os, socket, logging
from flask import Flask, jsonify, render_template
from dotenv import load_dotenv
from engine import Engine

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

CFG = {
    "client_id": os.getenv("DERIBIT_CLIENT_ID", ""),
    "client_secret": os.getenv("DERIBIT_CLIENT_SECRET", ""),
    "testnet": os.getenv("DERIBIT_TESTNET", "1") == "1",
    "otm_pct": float(os.getenv("OTM_PCT", "0.05")),       # put strike % below index
    "dte_min": float(os.getenv("DTE_MIN", "5")),          # min days to expiry
    "contracts": float(os.getenv("CONTRACTS", "0.1")),    # BTC per trade (min 0.1)
    "tp_pct": float(os.getenv("TP_PCT", "0.5")),          # buy back at 50% of premium
    "spread": os.getenv("SPREAD", "0") == "1",            # defined-risk wing
    "spread_width": float(os.getenv("SPREAD_WIDTH", "0.05")),
    "poll_seconds": float(os.getenv("POLL_SECONDS", "60")),
    "trading_enabled": os.getenv("TRADING_ENABLED", "1") == "1",
}

engine = Engine(CFG)
app = Flask(__name__)

@app.route("/")
def index(): return render_template("index.html")

@app.route("/api/state")
def api_state(): return jsonify(engine.snapshot())

@app.route("/healthz")
def healthz(): return jsonify({"ok": True})

def _port_in_use(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try: s.bind(("0.0.0.0", port)); return False
    except OSError: return True
    finally: s.close()

def main():
    port = int(os.getenv("WEB_PORT", "5001"))
    if _port_in_use(port):
        logging.getLogger("app").error("port %s in use — another instance running, exiting", port); return
    engine.start()
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False, threaded=True)

if __name__ == "__main__":
    main()
