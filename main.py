import os
import requests
import time
import asyncio
import threading
from telegram import Bot
from dotenv import load_dotenv

# Загружаем .env
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
COINGLASS_API_KEY = os.getenv("COINGLASS_API_KEY")
QUOTE_ASSET = 'USDT'

bot = Bot(token=TELEGRAM_TOKEN)

def calculate_rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
    gains = [max(closes[i] - closes[i - 1], 0) for i in range(1, period + 1)]
    losses = [abs(min(closes[i] - closes[i - 1], 0)) for i in range(1, period + 1)]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def get_usdt_symbols():
    r = requests.get('https://api.binance.com/api/v3/exchangeInfo')
    if r.status_code != 200:
        return []
    return [s['symbol'] for s in r.json().get('symbols', [])
            if s['status'] == 'TRADING' and s['quoteAsset'] == QUOTE_ASSET and 'UP' not in s['symbol'] and 'DOWN' not in s['symbol']]

def get_ohlcv_and_rsi(symbol):
    url = f'https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1h&limit=20'
    r = requests.get(url)
    if r.status_code != 200:
        return 0, 0, 0, None
    data = r.json()
    closes = [float(c[4]) for c in data]
    volumes = [float(c[5]) for c in data]
    if len(closes) < 15:
        return 0, 0, 0, None
    return volumes[-2], volumes[-1], closes[-1], calculate_rsi(closes)

def get_open_interest(symbol):
    url = f'https://open-api.coinglass.com/public/v1/oi?symbol={symbol}'
    headers = {'Authorization': f'Bearer {COINGLASS_API_KEY}'}
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        return 0, 0
    data = r.json().get('data', [])
    if not data:
        return 0, 0
    oi_data = data[0]
    return oi_data.get('prevOI', 0), oi_data.get('currOI', 0)

async def send_signal(symbol, prev_vol, curr_vol, price, rsi, prev_oi, curr_oi):
    msg = (
        f'📈 Сигнал по {symbol}!\n'
        f'Объём: {prev_vol:.0f} → {curr_vol:.0f}\n'
        f'Цена: {price:.4f}, RSI: {rsi:.1f}\n'
        f'Рост OI: {curr_oi / prev_oi * 100 - 100:.2f}%'
    )
    await bot.send_message(chat_id=CHAT_ID, text=msg)

async def monitor():
    await bot.send_message(chat_id=CHAT_ID, text="✅ Бот запущен на Render (фоновой задачей)")
    symbols = get_usdt_symbols()
    while True:
        for symbol in symbols:
            try:
                prev_vol, curr_vol, price, rsi = get_ohlcv_and_rsi(symbol)
                prev_oi, curr_oi = get_open_interest(symbol)
                if (curr_vol > prev_vol * 2 and curr_vol > 100000 and
                    rsi is not None and rsi < 70 and
                    prev_oi > 0 and curr_oi > prev_oi * 1.1):
                    await send_signal(symbol, prev_vol, curr_vol, price, rsi, prev_oi, curr_oi)
                    await asyncio.sleep(1)
            except Exception as e:
                print(f"Ошибка с {symbol}: {e}")
        await asyncio.sleep(600)

def start_async_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(monitor())

if __name__ == '__main__':
    threading.Thread(target=start_async_loop).start()
