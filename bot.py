import os
import logging
import pandas as pd
import requests
import asyncio
import threading

from datetime import datetime
from telegram import Bot
from flask import Flask


# WEB SERVER

app = Flask(__name__)

@app.route("/")
def home():
    return "ELITE BOT RUNNING"


def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


# LOGGING

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# SETTINGS

SYMBOLS = ["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT"]

INTERVAL = "30m"

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

last_alert = {}


# GET DATA FIXED

def get_data(symbol):

    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={INTERVAL}&limit=200"

    response = requests.get(url)

    data = response.json()

    if not isinstance(data, list):

        logger.error("Invalid Binance Data")

        return None


    df = pd.DataFrame(data)


    df.columns = [

        "time","open","high","low","close",

        "volume","ct","qav","trades",

        "tb","tq","ignore"

    ]


    df["close"] = df["close"].astype(float)

    df["high"] = df["high"].astype(float)

    df["low"] = df["low"].astype(float)

    df["volume"] = df["volume"].astype(float)


    return df


# RSI

def calculate_rsi(df):

    delta = df["close"].diff()

    gain = delta.clip(lower=0)

    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(14).mean()

    avg_loss = loss.rolling(14).mean()

    rs = avg_gain / avg_loss

    df["rsi"] = 100 - (100/(1+rs))

    return df


# SIGNAL

def detect_signal(df):

    df = calculate_rsi(df)

    price1 = df["close"].iloc[-6]

    price2 = df["close"].iloc[-1]

    rsi1 = df["rsi"].iloc[-6]

    rsi2 = df["rsi"].iloc[-1]


    entry = price2


    if price2 < price1 and rsi2 > rsi1:

        sl = df["low"].iloc[-6]

        target = entry + (entry-sl)*2

        return "BUY", entry, sl, target


    if price2 > price1 and rsi2 < rsi1:

        sl = df["high"].iloc[-6]

        target = entry - (sl-entry)*2

        return "SELL", entry, sl, target


    return None,None,None,None


# TELEGRAM

async def send_alert(symbol,side,entry,sl,target):

    bot = Bot(token=TELEGRAM_TOKEN)

    msg=f"""

🚨 CRYPTO CITY ELITE SIGNAL 🚨

Coin: {symbol}

Side: {side}

Entry: {round(entry,4)}

Stop Loss: {round(sl,4)}

Target: {round(target,4)}

Time: {datetime.now()}

"""

    await bot.send_message(

        chat_id=TELEGRAM_CHAT_ID,

        text=msg

    )


# LOOP

async def run_bot():

    logger.info("ELITE BOT RUNNING")


    while True:

        try:

            for symbol in SYMBOLS:


                df=get_data(symbol)


                if df is None:

                    continue


                side,entry,sl,target=detect_signal(df)


                if side:

                    if symbol not in last_alert:

                        await send_alert(symbol,side,entry,sl,target)

                        last_alert[symbol]=side


            await asyncio.sleep(60)


        except Exception as e:

            logger.error(e)

            await asyncio.sleep(30)


# START

if __name__=="__main__":

    threading.Thread(target=run_web).start()

    asyncio.run(run_bot())
