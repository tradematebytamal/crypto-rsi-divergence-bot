import os
import logging
import pandas as pd
import requests
import asyncio
import threading

from datetime import datetime
from telegram import Bot
from flask import Flask


# =====================
# WEB SERVER FOR RENDER
# =====================

app = Flask(__name__)

@app.route("/")
def home():
    return "TEST BOT RUNNING"


def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


# =====================
# LOGGING
# =====================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("TEST BOT STARTED")


# =====================
# SETTINGS
# =====================

SYMBOLS = ["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT"]

TIMEFRAME = "30m"
LOOKBACK = 100

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


# =====================
# GET DATA
# =====================

def get_data(symbol):

    try:

        url = "https://api.binance.com/api/v3/klines"

        params = {

            "symbol": symbol,

            "interval": TIMEFRAME,

            "limit": LOOKBACK

        }

        response = requests.get(url, params=params)

        data = response.json()

        df = pd.DataFrame(data)

        df.columns = [

            "time","open","high","low","close",

            "volume","ct","qav","trades",

            "tb","tq","ignore"

        ]

        df["close"] = df["close"].astype(float)

        return df

    except Exception as e:

        logger.error(e)
        return None


# =====================
# TELEGRAM ALERT
# =====================

async def send_test_alert(symbol, price):

    bot = Bot(token=TELEGRAM_TOKEN)

    msg = f"""

✅ TEST SIGNAL FROM RENDER

Coin: {symbol}

Price: {price}

Time: {datetime.now()}

"""

    await bot.send_message(

        chat_id=TELEGRAM_CHAT_ID,

        text=msg

    )


# =====================
# MAIN LOOP
# =====================

async def run_bot():

    logger.info("TEST LOOP RUNNING")

    while True:

        try:

            for symbol in SYMBOLS:

                df = get_data(symbol)

                if df is None:
                    continue

                price = df["close"].iloc[-1]

                # FORCE SEND MESSAGE (TEST)
                await send_test_alert(symbol, price)

                logger.info(f"TEST MESSAGE SENT {symbol}")

            await asyncio.sleep(60)

        except Exception as e:

            logger.error(e)
            await asyncio.sleep(30)


# =====================
# START
# =====================

if __name__ == "__main__":

    threading.Thread(target=run_web).start()

    asyncio.run(run_bot())
