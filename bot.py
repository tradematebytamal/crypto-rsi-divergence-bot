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
# WEB SERVER (IMPORTANT FOR RENDER)
# =====================

app = Flask(__name__)

@app.route("/")
def home():

    return "Crypto Bot Running"


def run_web():

    port = int(os.environ.get("PORT", 10000))

    app.run(host="0.0.0.0", port=port)



# =====================
# BOT SETTINGS
# =====================

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)


SYMBOLS = ["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT"]

TIMEFRAME = "30m"

LOOKBACK = 100


TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


# =====================
# GET DATA
# =====================

def get_klines(symbol):

    url = "https://api.binance.com/api/v3/klines"

    params = {

        "symbol": symbol,

        "interval": TIMEFRAME,

        "limit": LOOKBACK

    }

    response = requests.get(url, params=params)

    data = response.json()

    if not isinstance(data, list):

        logger.error("Invalid data")

        return None


    df = pd.DataFrame(data, columns=[

        "time",

        "open",

        "high",

        "low",

        "close",

        "volume",

        "ct",

        "qav",

        "trades",

        "tb",

        "tq",

        "ignore"

    ])


    df["close"] = df["close"].astype(float)

    return df


# =====================
# TELEGRAM
# =====================

async def send_alert(symbol,price):


    bot = Bot(token=TELEGRAM_TOKEN)


    msg = f"""

🚨 Divergence Alert


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


    logger.info("Bot Started")


    while True:


        try:


            for symbol in SYMBOLS:


                df = get_klines(symbol)


                price = df["close"].iloc[-1]


                await send_alert(

                    symbol,

                    price

                )


            await asyncio.sleep(300)


        except Exception as e:


            logger.error(e)


            await asyncio.sleep(30)



# =====================
# START
# =====================

if __name__ == "__main__":


    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:


        threading.Thread(

            target=run_web

        ).start()


        asyncio.run(run_bot())


    else:


        print("Telegram not set")
