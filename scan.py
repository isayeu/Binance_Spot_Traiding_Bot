import urwid
import asyncio
import os
import numpy as np
import talib
import logging
from binance.client import Client
from config import load_config
import aiohttp
import nest_asyncio

# Настройка логирования
logging.basicConfig(
    filename='scan.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Загрузка конфигурации
config = load_config()
api_key = config['api_key']
api_secret = config['api_secret']
token = config['telegram_token']
chat_id = config['telegram_chat_id']

client = Client(api_key, api_secret)

PAIRS_TO_SCAN = 'scan_list'
TRADING_PAIRS_FILE = 'trading_pairs.txt'
interval = config['interval']
existing_pairs_limit = int(config['existing_pairs_limit'])
rsi_to_add = int(config['rsi_to_add'])
limit = 200
CACHE_TTL = 60  # Время жизни кэша в секундах

# Глобальный кэш для данных свечей
data_cache = {}


# Функция для отправки сообщения в Telegram
async def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'HTML'
    }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, data=payload) as response:
                if response.status == 200:
                    logging.info("Сообщение успешно отправлено в Telegram")
                else:
                    logging.error(f"Ошибка при отправке сообщения в Telegram: {response.status}")
        except Exception as e:
            logging.error(f"Ошибка при отправке сообщения в Telegram: {e}")


async def get_pairs_to_scan():
    """Чтение списка пар для сканирования."""
    if os.path.exists(PAIRS_TO_SCAN):
        with open(PAIRS_TO_SCAN, 'r') as f:
            pairs = [line.strip() for line in f if line.strip()]
            return pairs
    logging.warning("Файл со списком пар для сканирования не найден.")
    return []


def calculate_rsi(closes):
    """Рассчитывает RSI."""
    return talib.RSI(np.array(closes, dtype=float), timeperiod=14)[-1]


def calculate_sma(closes, period):
    """Рассчитывает простую скользящую среднюю (SMA)."""
    if len(closes) < period:
        return None
    return np.mean(closes[-period:])


async def fetch_klines(symbol):
    """Получает данные свечей для указанной пары с кэшированием."""
    current_time = asyncio.get_event_loop().time()
    if symbol in data_cache and current_time - data_cache[symbol]['timestamp'] < CACHE_TTL:
        return data_cache[symbol]['data']

    try:
        async with aiohttp.ClientSession() as session:
            url = f'https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}'
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    closes = [float(kline[4]) for kline in data]
                    data_cache[symbol] = {'data': closes, 'timestamp': current_time}
                    return closes
    except Exception as e:
        logging.error(f"Ошибка при получении данных для {symbol}: {e}")
        return []


async def process_pair(pair, existing_pairs_in_file, top_pairs):
    """Обрабатывает одну пару."""
    closes = await fetch_klines(pair)
    if closes:
        rsi = calculate_rsi(closes)
        sma_200 = calculate_sma(closes, 200)

        # Проверяем, что SMA рассчитана (не None) и последняя цена ниже SMA
        if sma_200 is not None and closes[-1] < sma_200:
            # Обновление топа
            existing_pair = next((p for p in top_pairs if p[0] == pair), None)
            if existing_pair:
                top_pairs.remove(existing_pair)
            top_pairs.append((pair, rsi))

            return pair, rsi
    return None


async def scan_and_update(pairs, widget, loop):
    """Сканирует пары параллельно и обновляет UI."""
    while True:
        # Загружаем уже существующие пары из файла
        existing_pairs_in_file = []
        if os.path.exists(TRADING_PAIRS_FILE):
            with open(TRADING_PAIRS_FILE, 'r') as f:
                existing_pairs_in_file = f.read().splitlines()

        # Проверяем лимит существующих пар
        while len(existing_pairs_in_file) >= existing_pairs_limit:
            await asyncio.sleep(10)  # Задержка перед повторной проверкой

            # Обновляем список существующих пар
            with open(TRADING_PAIRS_FILE, 'r') as f:
                existing_pairs_in_file = f.read().splitlines()

        top_pairs = []

        # Обработка всех пар
        tasks = [
            process_pair(pair, existing_pairs_in_file, top_pairs)
            for pair in pairs
        ]
        await asyncio.gather(*tasks)

        # Исключаем пары, которые уже добавлены в файл
        filtered_top_pairs_for_display = [
            (symbol, rsi) for symbol, rsi in top_pairs
            if symbol not in existing_pairs_in_file
        ]

        # Сортируем пары по RSI
        sorted_top_pairs = sorted(
            filtered_top_pairs_for_display,
            key=lambda x: x[1]
        )

        # Отбираем ограниченное количество пар для отображения
        pairs_to_display = sorted_top_pairs[:(existing_pairs_limit - len(existing_pairs_in_file))]

        # Фильтруем пары, которые соответствуют условиям для добавления в файл
        filtered_top_pairs = [
            (symbol, rsi) for symbol, rsi in sorted_top_pairs
            if rsi <= rsi_to_add
        ]

        # Добавляем самую топовую пару в файл trading_pairs.txt
        if filtered_top_pairs:
            top_pair = filtered_top_pairs[0]  # Самая топовая пара (с минимальным RSI)
            symbol, rsi = top_pair

            with open(TRADING_PAIRS_FILE, 'a') as f:
                f.write(f"{symbol}\n")
            logging.info(f"Добавлена новая пара: {symbol} с RSI {rsi:.2f}")
            existing_pairs_in_file.append(symbol)

            # Отправка уведомления в Telegram
            await send_telegram_message(f"🆕 Добавлена новая пара: {symbol} с RSI {rsi:.2f}")

        # Обновляем UI
        widget.body[:] = make_table(pairs_to_display).body
        loop.draw_screen()


def make_table(top_pairs):
    """Создает таблицу для отображения с использованием urwid."""
    # Стили urwid
    palette = [
        ('low_rsi', 'light green', 'default'),
        ('medium_rsi', 'yellow', 'default'),
        ('high_rsi', 'light red', 'default'),
        ('blue_text', 'light blue', 'default'),
        ('green_text', 'light green', 'default'),
        ('symbol_text', 'light cyan', 'default'),
        ('default', 'default', 'default'),
    ]

    rows = [urwid.Text([
        ('blue_text', "Топ пар с минимальным RSI. Порог: "),
        ('green_text', f"{rsi_to_add} ")
    ])]

    for symbol, rsi in top_pairs:
        # Определим стиль для RSI
        if rsi <= 30:
            rsi_style = 'low_rsi'
        elif 30 < rsi <= 70:
            rsi_style = 'medium_rsi'
        else:
            rsi_style = 'high_rsi'

        # Добавляем текст с использованием стилей
        rows.append(urwid.Text([
            ('symbol_text', f"{symbol:<10}"),  # Символ пары, выровненный по левому краю
            (rsi_style, f" RSI: {rsi:>5.2f}"),  # RSI, с применением стиля
        ]))

    return urwid.ListBox(urwid.SimpleFocusListWalker(rows))


async def main(loop):
    """Основная функция."""
    pairs = await get_pairs_to_scan()
    if not pairs:
        logging.error("Список пар для сканирования пуст.")
        return

    placeholder = urwid.Text("Загрузка...")
    widget = urwid.ListBox(urwid.SimpleFocusListWalker([placeholder]))

    # Передаем палитру в MainLoop
    palette = [
        ('low_rsi', 'light green', 'default'),
        ('medium_rsi', 'yellow', 'default'),
        ('high_rsi', 'light red', 'default'),
        ('blue_text', 'light blue', 'default'),
        ('green_text', 'light green', 'default'),
        ('symbol_text', 'light cyan', 'default'),
        ('default', 'default', 'default'),
    ]

    main_loop = urwid.MainLoop(widget, event_loop=loop, unhandled_input=exit_on_q, palette=palette)

    asyncio.ensure_future(scan_and_update(pairs, widget, main_loop))
    main_loop.run()


def display_top_pairs():
    """Отображает топ-5 пар с помощью urwid."""
    nest_asyncio.apply()
    loop = urwid.AsyncioEventLoop()
    try:
        asyncio.run(main(loop))
    except RuntimeError as e:
        logging.critical(f"Ошибка запуска интерфейса: {e}")


def exit_on_q(key):
    """Выход из приложения при нажатии 'q'."""
    if key in ('q', 'Q'):
        raise urwid.ExitMainLoop()


if __name__ == '__main__':
    try:
        logging.info("Запуск приложения.")
        display_top_pairs()
    except Exception as e:
        logging.critical(f"Критическая ошибка приложения: {e}")
