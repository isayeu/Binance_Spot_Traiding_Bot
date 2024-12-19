# indicator_display.py

import urwid
import pandas as pd


def format_rsi_display(last_rsi):
    if last_rsi == "N/A":
        return ("default", "N/A")
    elif last_rsi < 40.0:
        return ("low_rsi", str(last_rsi))
    elif 40.0 <= last_rsi <= 60.0:
        return ("medium_rsi", str(last_rsi))
    else:
        return ("high_rsi", str(last_rsi))


def format_trend_display(last_trend):
    if last_trend == "N/A":
        return ("default", "N/A")
    elif last_trend == "flat":
        return ("flat", "N/A")
    elif last_trend == "growth":
        return ("growth", "growth")
    else:
        return ("fall", "fall")


def format_profit_display(profit, min_profit):
    if profit == "N/A":
        return ("default", "N/A")
    elif profit < 0:
        return ("loss", str(profit))
    elif 0 <= profit <= min_profit:
        return ("neutral_profit", str(profit))
    else:
        return ("positive_profit", str(profit))


def calculate_profit(current_price, buy_price, balance, commission_rate):
    if buy_price != 'N/A' and balance > 0:
        return round((current_price - buy_price) * balance - (current_price * balance * commission_rate), 2)
    return "N/A"


def display_indicators(trading_pairs, data, account_balances, bridge_balance,
                       btc_price, total_profit, trends, logger,
                       get_symbol_info_from_binance, min_profit, bridge,
                       commission_rate):
    # Стили urwid
    palette = [
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
    ]

    # Заголовок баланса и профита
    balance_text = urwid.Text([
        ('blue_text', f" Balance {bridge}:"),
        ('green_text', f"{bridge_balance}"),
        ('default', " | "),
        ('blue_text', "Profit:"),
        ('green_text', f"{total_profit}"),
        ('default', " | "),
        ('blue_text', f"1 BTC"),
        ('default', " = "),
        ('green_text', f"{btc_price} USDT")
    ])
    balance_box = urwid.LineBox(balance_text, title="Balances")

    # Заголовки таблицы
    table_header = urwid.AttrMap(
        urwid.Columns([
            urwid.Text("Symbol", align='left'),
            urwid.Text("RSI", align='left'),
            urwid.Text("Trend", align='left'),
            urwid.Text("Price", align='left'),
            urwid.Text("Bought for", align='left'),
            urwid.Text("Profit", align='left'),
            urwid.Text("Balance", align='left'),
        ]), 'default'
    )

    table_rows = [table_header, urwid.Divider('-')]  # Добавим заголовок и горизонтальный разделитель

    # Заполнение строк данными
    for symbol in trading_pairs:
        if symbol not in data:
            continue

        df = data[symbol]
        if df.empty:
            continue

        # Получаем данные для строки
        last_rsi = round(float(df['rsi'].iloc[-1]), 1) if pd.notna(df['rsi'].iloc[-1]) else "N/A"
        current_price = round(float(df['close'].iloc[-1]), 6) if pd.notna(df['close'].iloc[-1]) else "N/A"
        balance = round(account_balances.get(symbol.replace(bridge, ''), 0), 6)
        tb_balance = f"{balance:.8f}".rstrip('0').rstrip('.')
        last_trend = trends.get(symbol, "N/A")

        symbol_info = get_symbol_info_from_binance(symbol)
        buy_price = round(float(symbol_info['price']), 6) if symbol_info and 'price' in symbol_info and symbol_info['price'] is not None else 'N/A'
        profit = calculate_profit(current_price, buy_price, balance, commission_rate) if current_price != "N/A" and buy_price != "N/A" else "N/A"

        # Форматируем отображение с применением цветового стиля
        last_rsi_display = urwid.AttrMap(urwid.Text(format_rsi_display(last_rsi)), format_rsi_display(last_rsi)[0])
        last_trend_display = urwid.AttrMap(urwid.Text(format_trend_display(last_trend)), format_trend_display(last_trend)[0])
        profit_display = urwid.AttrMap(urwid.Text(format_profit_display(profit, min_profit)), format_profit_display(profit, min_profit)[0])

        row = urwid.Columns([
            urwid.Text([('symbol_text', f"{symbol.replace('USDT', '')}")]),
            last_rsi_display,
            last_trend_display,
            urwid.Text(str(current_price)),
            urwid.Text(str(buy_price)),
            profit_display,
            urwid.Text(tb_balance),
        ], dividechars=2)

        # Обернем строку в `AttrMap` и добавим горизонтальный разделитель
        table_rows.extend([row, urwid.Divider('-')])

    # Сборка виджетов
    table_list = urwid.Pile(table_rows)
    table_box = urwid.LineBox(table_list, title="Info")

    # Главный контейнер
    main_view = urwid.Pile([balance_box, table_box])

    # Возвращаем обернутый виджет для корректного отображения
    return urwid.Filler(main_view, valign='top')
