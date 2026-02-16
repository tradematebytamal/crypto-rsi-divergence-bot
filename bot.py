import os
import time
import logging
import pandas as pd
import numpy as np
import requests
from datetime import datetime
from telegram import Bot
import asyncio

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT']
TIMEFRAME = "30m"
RSI_PERIOD = 14
LOOKBACK = 100
PIVOT_WINDOW = 3

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Binance REST API function (NO RESTRICTION)
def get_klines(symbol):

    url = "https://api.binance.com/api/v3/klines"

    params = {

        "symbol": symbol,

        "interval": TIMEFRAME,

        "limit": LOOKBACK

    }

    response = requests.get(url, params=params)

    data = response.json()

    df = pd.DataFrame(data, columns=[

        'timestamp', 'open', 'high', 'low', 'close', 'volume',

        'close_time', 'quote_av', 'trades',

        'tb_base_av', 'tb_quote_av', 'ignore'

    ])

    df['close'] = df['close'].astype(float)

    df['high'] = df['high'].astype(float)

    df['low'] = df['low'].astype(float)

    df['volume'] = df['volume'].astype(float)

    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

    return df


# RSI Function
def get_rsi(series, period=14):

    delta = series.diff()

    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()

    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

    rs = gain / loss

    return 100 - (100 / (1 + rs))


# Pivot Detection
def find_pivots(df, window=3):

    df['pivot_low'] = df['low'].rolling(

        window=window*2+1,

        center=True

    ).apply(lambda x: x[window] == min(x), raw=True)

    df['pivot_high'] = df['high'].rolling(

        window=window*2+1,

        center=True

    ).apply(lambda x: x[window] == max(x), raw=True)

    return df


# Divergence Detection
def check_divergence(df):

    pivot_lows = df[df['pivot_low'] == 1].tail(2)

    pivot_highs = df[df['pivot_high'] == 1].tail(2)

    current_price = df['close'].iloc[-1]

    current_rsi = df['rsi'].iloc[-1]

    recent_min = df['low'].tail(50).min()

    recent_max = df['high'].tail(50).max()

    if len(pivot_lows) == 2:

        p1, p2 = pivot_lows.iloc[0], pivot_lows.iloc[1]

        if p2['low'] < p1['low'] and p2['rsi'] > p1['rsi'] and current_rsi < 35:

            return "Bullish Divergence"

    if len(pivot_highs) == 2:

        p1, p2 = pivot_highs.iloc[0], pivot_highs.iloc[1]

        if p2['high'] > p1['high'] and p2['rsi'] < p1['rsi'] and current_rsi > 65:

            return "Bearish Divergence"

    return None


# Telegram Alert
async def send_alert(symbol, div_type, price, rsi):

    bot = Bot(token=TELEGRAM_TOKEN)

    message = f"""

🚨 RSI DIVERGENCE ALERT

Coin: {symbol}

Type: {div_type}

Price: {price}

RSI: {rsi:.2f}

Time: {datetime.now()}

"""

    await bot.send_message(

        chat_id=TELEGRAM_CHAT_ID,

        text=message

    )

    logger.info(f"Alert sent for {symbol}")


# Main Loop
async def run_bot():

    logger.info("Bot started...")

    while True:

        try:

            for symbol in SYMBOLS:

                df = get_klines(symbol)

                df['rsi'] = get_rsi(df['close'])

                df = find_pivots(df)

                div = check_divergence(df)

                if div:

                    await send_alert(

                        symbol,

                        div,

                        df['close'].iloc[-1],

                        df['rsi'].iloc[-1]

                    )

            await asyncio.sleep(60)

        except Exception as e:

            logger.error(e)

            await asyncio.sleep(30)


# Start
if __name__ == "__main__":

    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:

        asyncio.run(run_bot())

    else:

        logger.error("Telegram credentials missing")
