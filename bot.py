import os
import requests
import time
from telegram import Bot
from dotenv import load_dotenv

# Загружаем переменные окружения из .env
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
COINGLASS_API_KEY = os.getenv("COINGLASS_API_KEY")  # не используется пока
INTERVAL = '1h'
CHECK_INTERVAL = 600  # раз в 10 минут
QUOTE_ASSET = 'USDT'

bot = Bot(token=TELEGRAM_TOKEN)

def calculate_rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, period + 1):
        change = closes[i] - closes[i - 1]
        gains.append(max(change, 0))
        losses.append(abs(min(change, 0)))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def get_usdt_symbols():
    r = requests.get('https://api.binance.com/api/v3/exchangeInfo')
    return [s['symbol'] for s in r.json()['symbols']
            if s['status'] == 'TRADING' and s['quoteAsset'] == QUOTE_ASSET and 'UP' not in s['symbol'] and 'DOWN' not in s['symbol']]

def get_ohlcv_and_rsi(symbol):
    url = f'https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1h&limit=20'
    r = requests.get(url)
    data = r.json()
    closes = [float(c[4]) for c in data]
    volumes = [float(c[5]) for c in data]
    if len(closes) < 15:
        return 0, 0, 0, 100
    prev_vol = volumes[-2]
    curr_vol = volumes[-1]
    price = closes[-1]
    rsi = calculate_rsi(closes[-15:])
    return prev_vol, curr_vol, price, rsi

def send_signal(symbol, prev_vol, curr_vol, price, rsi):
    msg = (f'📈 Сигнал по {symbol}!
'
           f'Объём: {prev_vol:.0f} → {curr_vol:.0f}
'
           f'Цена: {price:.4f}, RSI: {rsi:.1f}')
    bot.send_message(chat_id=CHAT_ID, text=msg)

def monitor():
    symbols = get_usdt_symbols()
    print(f"Мониторинг {len(symbols)} монет...")
    while True:
        for symbol in symbols:
            try:
                prev_vol, curr_vol, price, rsi = get_ohlcv_and_rsi(symbol)
                if curr_vol > prev_vol * 2 and curr_vol > 100000 and rsi and rsi < 70:
                    send_signal(symbol, prev_vol, curr_vol, price, rsi)
                    time.sleep(1)
            except Exception as e:
                print(f"Ошибка с {symbol}: {e}")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    bot.send_message(chat_id=CHAT_ID, text="✅ Бот запущен и работает на Render!")
    monitor()
