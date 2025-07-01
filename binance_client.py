# binance_client.py

from binance.client import Client
from binance.enums import ORDER_TYPE_MARKET
import math
import logging
import pandas as pd
import talib
import requests
from config import load_config

config = load_config()

client = None  # Объявим клиент как глобальный объект, инициализируем его позже
bridge = config['bridge']


# Инициализация клиента Binance
def initialize_client(api_key, api_secret):
    if not api_key or not api_secret:
        raise ValueError("API ключи не найдены. Проверьте конфигурацию.")
    global client
    client = Client(api_key, api_secret, {"timeout": 60})
    client.futures_time()


# Получаем информацию о позиции конкретного символа напрямую с Binance
def get_symbol_info_from_binance(symbol):
    try:
        account_balances = client.get_account()['balances']
        for asset in account_balances:
            asset_symbol = asset['asset']
            if asset_symbol == symbol.replace(bridge, ''):
                free_to_sell = float(asset['free'])
                trades = client.get_my_trades(symbol=symbol, limit=10)
                last_buy_price = None
                # Проверяем наличие сделок и ищем последнюю покупку
                if trades:
                    for trade in reversed(trades):
                        if trade['isBuyer']:
                            last_buy_price = float(trade['price'])
                            break
                return {
                    'free': free_to_sell if free_to_sell else 0.0,
                    'price': last_buy_price if last_buy_price else None
                }
        logging.warning(f"Символ {symbol} не найден в балансах.")
        return {'free': 0.0, 'price': None}  # Возврат безопасных значений
    except requests.exceptions.Timeout:
        logging.error(f"Таймаут при получении информации о символе {symbol}.")
        return {'free': 0.0, 'price': None}  # Возврат безопасных значений
    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка сети при запросе информации о символе {symbol}: {e}")
        return {'free': 0.0, 'price': None}  # Возврат безопасных значений
    except Exception as e:
        logging.error(f"Неизвестная ошибка при обработке {symbol}: {e}")
        return {'free': 0.0, 'price': None}  # Возврат безопасных значений


# Функция получения актуальных балансов
def get_account_balances():
    account = client.get_account()
    balances = {}
    for balance in account['balances']:
        asset = balance['asset']
        free = float(balance['free'])
        locked = float(balance['locked'])
        total = free + locked
        if total > 0:
            balances[asset] = total
    return balances


# Получение исторических данных по свечам с обработкой ошибок
def get_data(symbol, interval, limit):
    try:
        candles = client.get_klines(symbol=symbol, interval=interval, limit=limit)
        if not candles:
            logging.warning(f"Нет данных по свечам для {symbol}")
            return pd.DataFrame()  # Пустой DataFrame для обработки
        df = pd.DataFrame(candles, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time',
            'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume',
            'taker_buy_quote_asset_volume', 'ignore'
        ])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
        return df
    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка сети при запросе данных {symbol}: {e}")
        return pd.DataFrame()
    except Exception as e:
        logging.error(f"Неизвестная ошибка при обработке данных {symbol}: {e}")
        return pd.DataFrame()


# Подсчет RSI
def calculate_rsi(df, period=14):
    if df.empty or 'close' not in df.columns:
        logging.error("Пустой DataFrame или отсутствует колонка 'close' для расчета RSI.")
        return df
    df['rsi'] = talib.RSI(df['close'].values, timeperiod=period)
    return df


# функция для расчета MACD и гистограммы
def calculate_macd_histogram(df, fastperiod=12, slowperiod=26, signalperiod=9):
    close_prices = df['close'].values
    macd, signal, histogram = talib.MACD(
        close_prices,
        fastperiod=fastperiod,
        slowperiod=slowperiod,
        signalperiod=signalperiod
    )
    df['macd'] = macd
    df['signal'] = signal
    df['histogram'] = histogram
    return df


# рассчет данных по конкретной торговой паре
def process_trading_pair(symbol, interval, limit):
    df = get_data(symbol, interval, limit)
    df = calculate_rsi(df)
    df = calculate_macd_histogram(df)
    return df


# Размещаем ордер
def place_order(symbol, quantity, side):
    try:
        if quantity <= 0:
            logging.error("Попытка разместить ордер с нулевым или отрицательным объемом.")
            return None
        order = client.create_order(symbol=symbol, side=side, type=ORDER_TYPE_MARKET, quantity=quantity)
        logging.info(f"Ордер размещен: {side} {quantity} {symbol}")
        return order
    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка сети при размещении ордера {symbol}: {e}")
    except Exception as e:
        logging.error(f"Неизвестная ошибка при размещении ордера {symbol}: {e}")
    return None


# Получение текущего баланса конкретного актива
def get_balance(asset):
    balance = client.get_asset_balance(asset)
    if balance:
        return float(balance['free'])
    return 0.0


# Корректировка объема (quantity) торгового ордера на бирже в соответствии с шагом лота (step size)
def adjust_quantity(quantity, step_size):
    precision = int(round(-math.log(step_size, 10), 0))  # Определяем количество знаков после запятой на основе step_size
    factor = 10 ** precision  # Преобразуем для работы с целыми числами
    quantity = math.floor(quantity * factor) / factor  # Округляем в меньшую сторону
    quantity = max(quantity, step_size)  # Убеждаемся, что количество не меньше минимального лота
    return quantity  # Возвращаем как float


# Находим мимальный (lot size) и (step size)
def get_min_lot_size(symbol):
    info = client.get_symbol_info(symbol)
    for filter in info['filters']:
        if filter['filterType'] == 'LOT_SIZE':
            min_qty = float(filter['minQty'])
            step_size = float(filter['stepSize'])
            return min_qty, step_size
    return None, None


# вычисляем тренд для каждой пары
def analyze_trends(trading_pairs, data):
    trends = {}
    for symbol in trading_pairs:
        # Текущая гистограмма для последней свечи
        current_histogram = data[symbol]['histogram'].iloc[-1]
        # Получаем гистограмму предыдущей свечи
        previous_histogram = data[symbol]['histogram'].iloc[-2] if len(data[symbol]) > 1 else current_histogram
        # Сравниваем текущую и предыдущую гистограмму для определения тренда
        if current_histogram > previous_histogram:
            trends[symbol] = "growth"
        elif current_histogram == previous_histogram:
            trends[symbol] = "flat"
        else:
            trends[symbol] = "fall"
    return trends


# Функция для получения текущей цены символа
def get_symbol_ticker(symbol):
    return client.get_symbol_ticker(symbol=symbol)


# Функция для получения текущей цены BTC
def get_btc_ticker():
    return client.get_symbol_ticker(symbol='BTCUSDT')
