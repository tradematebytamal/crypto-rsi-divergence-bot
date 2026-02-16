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
# WEB SERVER
# =====================

app = Flask(__name__)

@app.route("/")
def home():
    return "INSTITUTIONAL BOT RUNNING"


def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


# =====================
# LOGGING
# =====================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("INSTITUTIONAL BOT STARTED")


# =====================
# SETTINGS
# =====================

COINS = {
"bitcoin":"BTCUSDT",
"ethereum":"ETHUSDT",
"solana":"SOLUSDT",
"ripple":"XRPUSDT"
}

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

last_alert = {}


# =====================
# GET SAFE DATA
# =====================

def get_data(coin, days):

    url=f"https://api.coingecko.com/api/v3/coins/{coin}/ohlc?vs_currency=usd&days={days}"

    response=requests.get(url,timeout=10)

    data=response.json()

    if not isinstance(data,list) or len(data)<30:
        return None

    df=pd.DataFrame(data,columns=["time","open","high","low","close"])

    df["close"]=df["close"].astype(float)
    df["high"]=df["high"].astype(float)
    df["low"]=df["low"].astype(float)

    return df


# =====================
# RSI
# =====================

def rsi(df):

    delta=df["close"].diff()

    gain=delta.clip(lower=0)

    loss=-delta.clip(upper=0)

    avg_gain=gain.rolling(14).mean()

    avg_loss=loss.rolling(14).mean()

    rs=avg_gain/avg_loss

    df["rsi"]=100-(100/(1+rs))

    return df


# =====================
# EMA TREND FILTER
# =====================

def ema(df):

    df["ema"]=df["close"].ewm(span=50).mean()

    return df


# =====================
# SIGNAL ENGINE
# =====================

def signal_engine(df_small, df_big):

    df_small=rsi(df_small)
    df_small=ema(df_small)

    df_big=ema(df_big)


    price1=df_small["close"].iloc[-6]
    price2=df_small["close"].iloc[-1]

    rsi1=df_small["rsi"].iloc[-6]
    rsi2=df_small["rsi"].iloc[-1]

    trend_small=df_small["close"].iloc[-1] > df_small["ema"].iloc[-1]

    trend_big=df_big["close"].iloc[-1] > df_big["ema"].iloc[-1]


    entry=price2


    # INSTITUTIONAL BUY

    if price2<price1 and rsi2>rsi1 and trend_big:

        sl=df_small["low"].iloc[-6]

        target=entry+(entry-sl)*2

        confidence=90

        return "BUY",entry,sl,target,confidence


    # INSTITUTIONAL SELL

    if price2>price1 and rsi2<rsi1 and not trend_big:

        sl=df_small["high"].iloc[-6]

        target=entry-(sl-entry)*2

        confidence=90

        return "SELL",entry,sl,target,confidence


    return None,None,None,None,None


# =====================
# TELEGRAM
# =====================

async def send_alert(symbol,side,entry,sl,target,confidence):

    bot=Bot(token=TELEGRAM_TOKEN)

    msg=f"""

🏦 INSTITUTIONAL SIGNAL

Coin: {symbol}

Side: {side}

Entry: {round(entry,2)}

Stop Loss: {round(sl,2)}

Target: {round(target,2)}

Confidence: {confidence}%

Time: {datetime.now()}

"""

    await bot.send_message(

        chat_id=TELEGRAM_CHAT_ID,
        text=msg

    )


# =====================
# LOOP
# =====================

async def run_bot():

    logger.info("INSTITUTIONAL LOOP RUNNING")

    while True:

        try:

            for coin in COINS:

                symbol=COINS[coin]

                df_small=get_data(coin,1)

                df_big=get_data(coin,7)

                if df_small is None or df_big is None:
                    continue


                side,entry,sl,target,confidence=signal_engine(df_small,df_big)


                if side:

                    if coin not in last_alert or last_alert[coin]!=side:

                        await send_alert(symbol,side,entry,sl,target,confidence)

                        last_alert[coin]=side


            await asyncio.sleep(60)


        except Exception as e:

            logger.error(e)

            await asyncio.sleep(30)


# =====================
# START
# =====================

if __name__=="__main__":

    threading.Thread(target=run_web).start()

    asyncio.run(run_bot())
