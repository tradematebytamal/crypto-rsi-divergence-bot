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
    return "Crypto City PRO Bot Running"


def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


# LOGGING
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("CRYPTO CITY PRO BOT STARTED")


SYMBOLS = ["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT"]

TIMEFRAME = "30m"
LOOKBACK = 150

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


# GET DATA
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
        df["high"] = df["high"].astype(float)
        df["low"] = df["low"].astype(float)

        return df

    except:

        return None


# RSI
def rsi(series, period=14):

    delta = series.diff()

    gain = delta.clip(lower=0)

    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()

    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss

    return 100 - (100/(1+rs))


# SIGNAL DETECTION
def detect_signal(df):

    if df is None:
        return None

    df["rsi"] = rsi(df["close"])

    price1 = df["close"].iloc[-10]
    price2 = df["close"].iloc[-1]

    rsi1 = df["rsi"].iloc[-10]
    rsi2 = df["rsi"].iloc[-1]


    entry = df["close"].iloc[-1]

    atr = df["high"].iloc[-14:].max() - df["low"].iloc[-14:].min()

    stop = entry - atr*0.5

    target = entry + atr


    confidence = round(abs(rsi2-rsi1)*2)


    if price2 < price1 and rsi2 > rsi1:

        return "Bullish", entry, stop, target, confidence


    if price2 > price1 and rsi2 < rsi1:

        stop = entry + atr*0.5

        target = entry - atr

        return "Bearish", entry, stop, target, confidence


    return None


# TELEGRAM ALERT
async def send_signal(symbol, signal):

    bot = Bot(token=TELEGRAM_TOKEN)

    direction, entry, stop, target, confidence = signal


    msg = f"""

🚨 CRYPTO CITY PRO SIGNAL 🚨

Coin: {symbol}

Signal: {direction} Divergence

Entry: {round(entry,2)}

Stop Loss: {round(stop,2)}

Target: {round(target,2)}

Confidence: {confidence}%

Timeframe: 30m

"""

    await bot.send_message(

        chat_id=TELEGRAM_CHAT_ID,

        text=msg

    )


# MAIN LOOP
async def run_bot():

    logger.info("PRO BOT LOOP RUNNING")

    while True:

        try:

            for symbol in SYMBOLS:

                df = get_data(symbol)

                signal = detect_signal(df)

                if signal:

                    await send_signal(symbol, signal)

                    logger.info(f"{symbol} SIGNAL SENT")

            await asyncio.sleep(60)

        except Exception as e:

            logger.error(e)

            await asyncio.sleep(30)


# START
if __name__ == "__main__":

    threading.Thread(target=run_web).start()

    asyncio.run(run_bot())
