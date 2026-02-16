import os
import time
import logging
import pandas as pd
import numpy as np
import requests
from datetime import datetime
from binance.client import Client
from telegram import Bot
import asyncio

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT']
TIMEFRAME = Client.KLINE_INTERVAL_30MINUTE
RSI_PERIOD = 14
LOOKBACK = 100  # Candles to fetch
PIVOT_WINDOW = 3 # Window for pivot high/low detection

# Environment Variables
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Initialize Binance Client (Public data only, no API key needed for klines)
binance_client = Client()

def get_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def find_pivots(df, window=3):
    df['pivot_low'] = df['low'].rolling(window=window*2+1, center=True).apply(lambda x: x[window] == min(x), raw=True)
    df['pivot_high'] = df['high'].rolling(window=window*2+1, center=True).apply(lambda x: x[window] == max(x), raw=True)
    return df

def check_divergence(df):
    if len(df) < 50:
        return None

    # Get the last two pivot lows and highs
    pivot_lows = df[df['pivot_low'] == 1].tail(2)
    pivot_highs = df[df['pivot_high'] == 1].tail(2)
    
    current_price = df['close'].iloc[-1]
    current_rsi = df['rsi'].iloc[-1]
    current_vol = df['volume'].iloc[-1]
    prev_vol = df['volume'].iloc[-2]
    
    # Support/Resistance Zone (last 50 candles)
    recent_min = df['low'].tail(50).min()
    recent_max = df['high'].tail(50).max()
    
    # Volume Filter
    vol_confirmed = current_vol > prev_vol

    # 1. Bullish Divergence (Regular)
    if len(pivot_lows) == 2:
        p1, p2 = pivot_lows.iloc[0], pivot_lows.iloc[1]
        # Price: Lower Low, RSI: Higher Low
        if p2['low'] < p1['low'] and p2['rsi'] > p1['rsi'] and p2['rsi'] < 30:
            if current_price <= recent_min * 1.01 and vol_confirmed:
                return "Regular Bullish Divergence"
        
        # 2. Hidden Bullish Divergence
        # Price: Higher Low, RSI: Lower Low
        if p2['low'] > p1['low'] and p2['rsi'] < p1['rsi'] and p2['rsi'] < 30:
            if current_price <= recent_min * 1.01 and vol_confirmed:
                return "Hidden Bullish Divergence"

    # 3. Bearish Divergence (Regular)
    if len(pivot_highs) == 2:
        p1, p2 = pivot_highs.iloc[0], pivot_highs.iloc[1]
        # Price: Higher High, RSI: Lower High
        if p2['high'] > p1['high'] and p2['rsi'] < p1['rsi'] and p2['rsi'] > 70:
            if current_price >= recent_max * 0.99 and vol_confirmed:
                return "Regular Bearish Divergence"
        
        # 4. Hidden Bearish Divergence
        # Price: Lower High, RSI: Higher High
        if p2['high'] < p1['high'] and p2['rsi'] > p1['rsi'] and p2['rsi'] > 70:
            if current_price >= recent_max * 0.99 and vol_confirmed:
                return "Hidden Bearish Divergence"

    return None

async def send_telegram_alert(symbol, div_type, price, rsi, vol_status, sr_zone):
    message = (
        f"🚨 *HIGH PROBABILITY RSI DIVERGENCE*\n\n"
        f"*Coin:* {symbol}\n"
        f"*Timeframe:* 30m\n"
        f"*Divergence Type:* {div_type}\n"
        f"*Current Price:* {price}\n"
        f"*RSI:* {rsi:.2f}\n"
        f"*Volume Status:* {vol_status}\n"
        f"*Support/Resistance:* {sr_zone}\n"
        f"*Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC"
    )
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode='Markdown')
        logger.info(f"Alert sent for {symbol}")
    except Exception as e:
        logger.error(f"Error sending Telegram message: {e}")

async def run_bot():
    last_processed_time = {symbol: None for symbol in SYMBOLS}
    last_alert_type = {symbol: None for symbol in SYMBOLS}

    logger.info("Bot started. Monitoring symbols...")
    
    while True:
        try:
            for symbol in SYMBOLS:
                # Fetch Klines
                klines = binance_client.get_klines(symbol=symbol, interval=TIMEFRAME, limit=LOOKBACK)
                df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_av', 'trades', 'tb_base_av', 'tb_quote_av', 'ignore'])
                df['close'] = df['close'].astype(float)
                df['high'] = df['high'].astype(float)
                df['low'] = df['low'].astype(float)
                df['volume'] = df['volume'].astype(float)
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                
                # Check if candle is closed
                current_candle_time = df['timestamp'].iloc[-1]
                if last_processed_time[symbol] == current_candle_time:
                    continue
                
                # Calculate Indicators
                df['rsi'] = get_rsi(df['close'], RSI_PERIOD)
                df = find_pivots(df, PIVOT_WINDOW)
                
                # Detect Divergence
                div_type = check_divergence(df)
                
                if div_type and div_type != last_alert_type[symbol]:
                    recent_min = df['low'].tail(50).min()
                    recent_max = df['high'].tail(50).max()
                    sr_zone = f"Near Support ({recent_min:.4f})" if "Bullish" in div_type else f"Near Resistance ({recent_max:.4f})"
                    
                    await send_telegram_alert(
                        symbol, 
                        div_type, 
                        df['close'].iloc[-1], 
                        df['rsi'].iloc[-1], 
                        "Higher than Previous" if df['volume'].iloc[-1] > df['volume'].iloc[-2] else "Normal",
                        sr_zone
                    )
                    last_alert_type[symbol] = div_type
                
                last_processed_time[symbol] = current_candle_time
                
            # Wait for next check (e.g., every 1 minute to check for candle close)
            await asyncio.sleep(60)
            
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            await asyncio.sleep(30)

if __name__ == "__main__":
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error("TELEGRAM_TOKEN or TELEGRAM_CHAT_ID not set in environment variables.")
    else:
        asyncio.run(run_bot())
