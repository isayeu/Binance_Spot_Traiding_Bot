# bbot.py

import os
import time
import logging
from logging.handlers import RotatingFileHandler
import requests
import urwid
from concurrent.futures import ThreadPoolExecutor, as_completed
from binance.enums import SIDE_BUY, SIDE_SELL
from config import load_config
from indicator_display import display_indicators
from binance_client import (
    initialize_client, get_symbol_info_from_binance, get_account_balances,
    get_data, calculate_rsi, process_trading_pair, place_order, get_balance,
    adjust_quantity, get_min_lot_size, analyze_trends, get_symbol_ticker,
    get_btc_ticker, calculate_macd_histogram
)

# Настройка логирования
handler = RotatingFileHandler('trading_bot.log', maxBytes=5*1024*1024,
                              backupCount=5)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger = logging.getLogger()  # Получаем основной логгер
logger.setLevel(logging.INFO)  # Устанавливаем уровень логирования
logger.addHandler(handler)  # Добавляем обработчик в логгер

# Загрузка конфигурации
config = load_config()
initialize_client(config['api_key'], config['api_secret'])
trading_pairs = config['trading_pairs']
bridge = config['bridge']
rsi_oversold = int(config['rsi_oversold'])
rsi_overbought = int(config['rsi_overbought'])
interval = config['interval']
fine_interval = config['fine_interval']
limit = int(config['limit'])
qty_to_invest = float(config['qty_to_invest'])
cfg_min_profit = float(config['cfg_min_profit'])
min_profit = qty_to_invest * cfg_min_profit
commission_rate = 0.001

logging.info(f"Программа запущена")


# Функция информирования в Telegram
def send_telegram_message(message, retries=3):
    token = config.get('telegram_token')
    chat_id = config.get('telegram_chat_id')
    if not token or not chat_id:
        logging.error("Отсутствует токен или chat_id для Telegram.")
        return None
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': message, 'parse_mode': 'HTML'}

    for attempt in range(retries):
        try:
            response = requests.post(url, data=payload, timeout=10)
            if response.status_code == 429:  # Лимит запросов Telegram
                retry_after = int(response.headers.get("Retry-After", 1))
                logging.warning(f"Превышен лимит Telegram. Повтор через {retry_after} секунд.")
                time.sleep(retry_after)
                continue
            response.raise_for_status()
            response_json = response.json()
            if response_json.get('ok'):
                return response_json
            logging.error(f"Ошибка Telegram API: {response_json.get('description')}")
        except requests.exceptions.RequestException as e:
            logging.error(f"Попытка {attempt + 1}: Ошибка сети Telegram: {e}")
        except Exception as e:
            logging.error(f"Непредвиденная ошибка в send_telegram_message: {e}")
    return None


# Функция для сохранения общего профита в файл
def save_total_profit(total_profit, filename='total_profit'):
    with open(filename, 'w') as file:
        file.write(str(total_profit))


# Функция для загрузки общего профита из файла
def load_total_profit(filename='total_profit'):
    if not os.path.isfile(filename):
        return 0.0  # Если файл не найден, возвращаем 0
    with open(filename, 'r') as file:
        return float(file.read().strip())


# Функция для удаления торговой пары из файла
def remove_symbol_from_file(symbol, filename='trading_pairs.txt'):
    # Считываем все пары из файла
    with open(filename, 'r') as file:
        pairs = [line.strip() for line in file if line.strip()]

    # Удаляем символ, если он есть в списке
    if symbol in pairs:
        pairs.remove(symbol)
        # Записываем оставшиеся пары обратно в файл
        with open(filename, 'w') as file:
            for pair in pairs:
                file.write(pair + '\n')
        logging.info(f"Торговая пара {symbol} удалена из файла {filename}.")
    else:
        logging.error(f"Торговая пара {symbol} не найдена в файле {filename}.")


# monitoring 30>пара>70 RSI
def monitoring():
    data = {}
    num_trading_pairs = len(trading_pairs)
    # Динамическое определение количества потоков
    cpu_count = os.cpu_count() or 4  # Получаем число ядер, по умолчанию 4
    max_threads = min(num_trading_pairs, cpu_count)  # Ограничиваем количество потоков
    if max_threads == 0:
        while max_threads == 0:
            time.sleep(5)
    with ThreadPoolExecutor(max_threads) as executor:
        futures = {executor.submit(get_data,
                                   symbol,
                                   interval,
                                   limit): symbol for symbol in trading_pairs}
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                df = future.result()
                if df.empty:
                    logging.warning(f"Пустой DataFrame для {symbol}. Пропускаем.")
                    continue
                # Обрабатываем индикаторы
                df = calculate_rsi(df)
                df = calculate_macd_histogram(df)
                data[symbol] = df
            except Exception as e:
                logging.error(f"Ошибка получения данных для {symbol}: {e}")

    for symbol, df in data.items():
        try:
            last_rsi = df['rsi'].iloc[-1]
            if last_rsi < rsi_oversold or last_rsi > rsi_overbought:
                fine_df = get_data(symbol, fine_interval, limit)
                if fine_df.empty:
                    continue
                    fine_df = calculate_macd_histogram(fine_df)
                fine_df = calculate_macd_histogram(fine_df)
                trends = analyze_trends([symbol], {symbol: fine_df})
                bridge_balance = get_balance(bridge)
                execute_trade_logic(symbol, df, fine_df, trends,
                                    bridge_balance, min_profit,
                                    load_total_profit())
        except Exception as e:
            logger.error(f"Ошибка обработки данных {symbol}: {str(e)}")


# Функция для выполнения торговой логики
def execute_trade_logic(symbol, df, fine_df, trends, bridge_balance,
                        min_profit, total_profit):
    try:
        next_move = trends.get(symbol)
        last_rsi = round(df['rsi'].iloc[-1])

        min_qty, step_size = get_min_lot_size(symbol)
        if min_qty is None:
            logging.error(f"Не удалось получить минимальный лот для {symbol}")
            return total_profit

        # Получаем информацию о позиции напрямую с Binance
        symbol_info = get_symbol_info_from_binance(symbol)

        # Проверка условий для покупки
        if last_rsi <= rsi_oversold and next_move == 'growth' and symbol_info['free'] < min_qty:
            bridge_balance = get_balance(bridge)
            if bridge_balance < qty_to_invest:
                logger.error(f"Недостаточно средств для покупки {symbol} на {qty_to_invest} {bridge}")
                return total_profit

            current_price = fine_df['close'].iloc[-1]
            quantity = qty_to_invest / current_price
            quantity = adjust_quantity(quantity, step_size)

            if quantity < min_qty:
                logging.error(f"Количество для торговли {quantity} меньше минимального размера {min_qty} для {symbol}.")
                return total_profit

            buy(symbol, quantity, current_price, qty_to_invest, min_profit)

        # Проверка условий для продажи
        elif last_rsi >= rsi_overbought and next_move == 'fall' and symbol_info['free'] >= min_qty:
            quantity = symbol_info['free']
            last_buy_price = symbol_info['price']

            if last_buy_price is None:
                logging.error(f"Нет данных о покупке для {symbol}")
                return total_profit

            successful_sale = sell(symbol, quantity, min_profit)

            if successful_sale:
                current_price = fine_df['close'].iloc[-1]
                profit = (current_price - last_buy_price) * quantity - (current_price * quantity * commission_rate)
                total_profit += profit
                save_total_profit(total_profit)
                remove_symbol_from_file(symbol, filename='trading_pairs.txt')
            else:
                logging.error(f"Продажа {symbol} не удалась или была пропущена.")

    except Exception as e:
        logging.error(f"Ошибка выполнения торговой логики для {symbol}: {e}")
    return total_profit


# Функция покупки
def buy(symbol, quantity, current_price, qty_to_invest, min_profit):

    # Корректируем количество с учетом шага лота
    min_qty, step_size = get_min_lot_size(symbol)
    quantity = adjust_quantity(quantity, step_size)

    order = place_order(symbol, quantity, SIDE_BUY)
    if order:
        price = float(order['fills'][0]['price'])
        send_telegram_message(f"📈 Покупка {quantity} {symbol.replace('USDT', '')} по цене {price}")
        logger.warning(f"Покупка {quantity} {symbol.replace('USDT', '')} по цене {price}")
        return True
    else:
        return False


# Функция продажи с проверкой профита и удалением пары из файла
def sell(symbol, quantity, min_profit, filename='trading_pairs.txt'):
    # Получаем текущую цену актива
    current_price = float(get_symbol_ticker(symbol)['price'])

    # Получаем информацию о последней покупке и количестве напрямую с Binance
    symbol_info = get_symbol_info_from_binance(symbol)
    last_buy_price = symbol_info['price'] if symbol_info else None

    if last_buy_price is None:
        logging.error(f"Нет данных о покупке для {symbol}")
        return False  # Возвращаем False, если не было данных о покупке

    # Рассчитываем профит
    profit = (current_price - last_buy_price) * quantity - (current_price * quantity * commission_rate)

    # Проверяем, что профит больше минимального
    if profit < min_profit:
        logging.error(f"Профит для продажи {symbol.replace('USDT', '')} составляет {profit:.2f} {bridge}, что меньше минимального профита {min_profit} {bridge}.")
        return False  # Возвращаем False, если профит меньше минимального

    # Корректируем количество с учетом шага лота
    min_qty, step_size = get_min_lot_size(symbol)
    quantity = adjust_quantity(quantity, step_size)

    # Продажа
    order = place_order(symbol, quantity, SIDE_SELL)
    if order:
        price = float(order['fills'][0]['price'])
        send_telegram_message(f"📉 Продано {quantity} {symbol.replace('USDT', '')} по {price} с профитом {profit:.2f} {bridge}")
        logger.warning(f"Продано {quantity} {symbol.replace('USDT', '')} по {price} с профитом {profit:.2f} {bridge}")

        return True  # Возвращаем True при успешной продаже
    else:
        return False  # Если не удалось продать, возвращаем False


# Функция обновления данных для интерфейса
def update_interface(loop, user_data):
    monitoring()  # Вызов функции мониторинга
    trading_pairs = user_data["trading_pairs"]
    interval = user_data["interval"]
    limit = user_data["limit"]
    logger = user_data["logger"]
    get_account_balances = user_data["get_account_balances"]
    process_trading_pair = user_data["process_trading_pair"]
    analyze_trends = user_data["analyze_trends"]
    display_indicators = user_data["display_indicators"]
    get_symbol_info_from_binance = user_data["get_symbol_info_from_binance"]
    min_profit = user_data["min_profit"]
    bridge = user_data["bridge"]
    commission_rate = user_data["commission_rate"]
    total_profit = user_data["total_profit"]

    # Получение балансов аккаунта
    account_balances = get_account_balances()
    bridge_balance = account_balances.get(bridge, 0)
    btc_price = float(get_btc_ticker()['price'])

    data = {}

    # Получение данных по всем торговым парам
    with ThreadPoolExecutor() as executor:
        futures = {executor.submit(process_trading_pair, symbol, interval,
                                   limit): symbol for symbol in trading_pairs}
        for future in futures:
            symbol = futures[future]
            try:
                df = future.result()
                data[symbol] = df
            except Exception as e:
                logger.error(f"Error processing {symbol}: {str(e)}")

    trends = analyze_trends(trading_pairs, data)

    # Обновляем интерфейс, вызывая display_indicators и обновляя main.widget
    updated_view = display_indicators(
        trading_pairs, data, account_balances, bridge_balance, btc_price,
        total_profit, trends, logger, get_symbol_info_from_binance, min_profit,
        bridge, commission_rate)

    # Устанавливаем обновленное представление
    loop.widget = updated_view
    loop.set_alarm_in(5, update_interface, user_data={"total_profit": total_profit, **user_data})


# Основная функция бота
def trading_bot():
    total_profit = load_total_profit()
    account_balances = get_account_balances()
    bridge_balance = account_balances.get(bridge, 0)
    btc_price = float(get_btc_ticker()['price'])

    # Загружаем данные торговых пар перед запуском интерфейса
    initial_data = {}
    for symbol in trading_pairs:
        df = get_data(symbol, interval, limit)
        if not df.empty:
            df = calculate_rsi(df)
            initial_data[symbol] = df

    # Создаем главный виджет для интерфейса urwid
    main_view = display_indicators(
        trading_pairs, initial_data, account_balances,
        bridge_balance, btc_price, total_profit, trends={}, logger=logger,
        get_symbol_info_from_binance=get_symbol_info_from_binance,
        min_profit=min_profit, bridge=bridge, commission_rate=commission_rate)

    # Запуск urwid.MainLoop
    main = urwid.MainLoop(main_view, palette=[
        ('low_rsi', 'dark red', 'default'),
        ('medium_rsi', 'yellow', 'default'),
        ('high_rsi', 'light green', 'default'),
        ('growth', 'light green', 'default'),
        ('fall', 'dark red', 'default'),
        ('positive_profit', 'light green', 'default'),
        ('neutral_profit', 'yellow', 'default'),
        ('loss', 'dark red', 'default'),
        ('blue_text', 'light blue', 'default'),
        ('green_text', 'light green', 'default'),
        ('symbol_text', 'light cyan', 'default'),
        ('default', 'default', 'default'),
    ], screen=urwid.raw_display.Screen())

    # Запуск основного цикла с обновлением интерфейса
    main.set_alarm_in(0, update_interface, user_data={
        "total_profit": total_profit,
        "trading_pairs": trading_pairs,
        "interval": interval,
        "limit": limit,
        "logger": logger,
        "get_account_balances": get_account_balances,
        "process_trading_pair": process_trading_pair,
        "analyze_trends": analyze_trends,
        "execute_trade_logic": execute_trade_logic,
        "display_indicators": display_indicators,
        "get_symbol_info_from_binance": get_symbol_info_from_binance,
        "min_profit": min_profit,
        "bridge": bridge,
        "commission_rate": commission_rate
    })

    main.run()


if __name__ == "__main__":
    trading_bot()
