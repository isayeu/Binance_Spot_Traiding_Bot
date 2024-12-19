# Binance_Spot_Traiding_Bot
## Binance Traiding Bot on spot
This is a Python-based Binance trading bot that automates cryptocurrency trading using technical analysis indicators such as RSI (Relative Strength Index) and MACD (Moving Average Convergence Divergence). The bot is equipped with Telegram notifications and logging for easy monitoring.

Features:  
  Automated Trading: Executes buy and sell orders based on market trends and configurable indicators.  
  Technical Indicators: Includes RSI and MACD calculations for trend analysis.  
  Dynamic Monitoring: Monitors trading pairs using optimized multithreading for performance.  
  Telegram Notifications: Sends real-time updates on executed trades.  
  Profit Tracking: Saves and loads total profit data to persist across sessions.  
  Configurable: Easily adjustable settings via a configuration file.

### Prerequisites
  Python: Ensure you have Python 3.8+ installed.  
  Binance API Keys: Obtain API and secret keys from your Binance account.  

### You also have to install:
     tmux
     inotify-tools
     python3-dev
     build-essential
### Follow This commands to install ta-lib:
     wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
     tar -xzvf ta-lib-0.4.0-src.tar.gz
     cd ta-lib
     ./configure --prefix=/usr
     make
     sudo make install
### Dependencies: Install the required Python libraries using the command: pip install (lib)
     pip install requests
     pip install pandas
     pip install python-binance
     pip install colorama
     pip install urwid
     pip install numpy==1.26.3
     pip install ta-lib
     pip install tqdm
### Installation
Clone this repository:  
```
  git clone https://github.com/your_username/binance-trading-bot.git
```

Navigate to the bot's directory:
Change user.cfg at yor discretion based on the provided template.

Usage

    Edit the configuration file to include:
        Binance API key and secret.
        Telegram bot token and chat ID for notifications.
        Trading pairs, intervals, and other parameters.

## Run the bot:
```
tmux new -s bbot
```
Split screen at least for 2 panels. (4 for me is the best way)  
ctrl+b % - for vertical split  
ctrl+b " - for horisontal split  

Monitor the logs in trading_bot.log and check Telegram for trade updates.

Configuration

The bot uses a JSON-based configuration file with the following fields:

    api_key and api_secret: Binance API credentials.
    trading_pairs: List of trading pairs to monitor (e.g., ["BTCUSDT", "ETHUSDT"]).
    interval: Candlestick interval (e.g., 15m, 1h).
    rsi_oversold and rsi_overbought: RSI thresholds for buy/sell signals.
    telegram_token and telegram_chat_id: Telegram bot credentials for notifications.

Features in Detail
Indicators

    RSI (Relative Strength Index): Determines oversold or overbought conditions.
    MACD Histogram: Identifies momentum changes and potential reversals.

Logging

All events, including trades and errors, are logged in trading_bot.log for troubleshooting and analysis.
Multithreading

Efficiently monitors multiple trading pairs by leveraging multithreading, optimizing for your system's CPU cores.
Future Improvements

    Expand to other exchanges.
    Add more indicators like Bollinger Bands or SMA.
    Integrate a web dashboard for real-time monitoring.

Disclaimer

This bot is for educational purposes only. Trading cryptocurrencies involves significant risk, and the bot's performance is not guaranteed. Use at your own risk.
License
