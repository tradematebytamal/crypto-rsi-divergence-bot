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
    return "RSI Bot Running"


def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


# SETTINGS
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SYMBOLS = ["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT"]

TIMEFRAME = "30m"
LOOKBACK = 100

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


# GET DATA
def get_data(symbol):

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


# RSI
def calculate_rsi(series, period=14):

    delta = series.diff()

    gain = delta.clip(lower=0)

    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()

    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss

    rsi = 100 - (100/(1+rs))

    return rsi


# CHECK DIVERGENCE
def check_divergence(df):

    df["rsi"] = calculate_rsi(df["close"])

    price1 = df["close"].iloc[-5]

    price2 = df["close"].iloc[-1]

    rsi1 = df["rsi"].iloc[-5]

    rsi2 = df["rsi"].iloc[-1]


    if price2 < price1 and rsi2 > rsi1:

        return "Bullish Divergence"


    if price2 > price1 and rsi2 < rsi1:

        return "Bearish Divergence"


    return None


# TELEGRAM
async def send_alert(symbol, signal, price):

    bot = Bot(token=TELEGRAM_TOKEN)

    msg = f"""

🚨 RSI DIVERGENCE ALERT

Coin: {symbol}

Signal: {signal}

Price: {price}

Time: {datetime.now()}

"""

    await bot.send_message(

        chat_id=TELEGRAM_CHAT_ID,

        text=msg

    )


# BOT LOOP
async def run_bot():

    logger.info("RSI Bot Started")

    while True:

        try:

            for symbol in SYMBOLS:

                df = get_data(symbol)

                signal = check_divergence(df)

                if signal:

                    price = df["close"].iloc[-1]

                    await send_alert(symbol, signal, price)

                    logger.info(f"{symbol} {signal}")


            await asyncio.sleep(60)


        except Exception as e:

            logger.error(e)

            await asyncio.sleep(30)


# START
if __name__ == "__main__":

    threading.Thread(target=run_web).start()

    asyncio.run(run_bot())
