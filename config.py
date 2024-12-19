import configparser


def load_config():
    config = configparser.ConfigParser()
    config.read('user.cfg')
    return {
        'api_key': config['binance_user_config']['api_key'],
        'api_secret': config['binance_user_config']['api_secret_key'],
        'telegram_token': config['binance_user_config']['telegram_token'],
        'telegram_chat_id': config['binance_user_config']['telegram_chat_id'],
        'rsi_oversold': config['binance_user_config']['rsi_oversold'],
        'rsi_overbought': config['binance_user_config']['rsi_overbought'],
        'interval': config['binance_user_config']['interval'],
        'fine_interval': config['binance_user_config']['fine_interval'],
        'limit': config['binance_user_config']['limit'],
        'bridge': config['binance_user_config']['bridge'],
        'qty_to_invest': config['binance_user_config']['qty_to_invest'],
        'cfg_min_profit': config['binance_user_config']['cfg_min_profit'],
        'trading_pairs': load_trading_pairs('trading_pairs.txt'),
        'existing_pairs_limit': config['scan_config']['existing_pairs_limit'],
        'rsi_to_add': config['scan_config']['rsi_to_add'],
    }


def load_trading_pairs(filename):
    with open(filename, 'r') as file:
        return [line.strip() for line in file if line.strip()]
