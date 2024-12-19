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
![Example](https://github.com/isayeu/Binance_Spot_Traiding_Bot/blob/main/Screenshot_20241219_193040.png)
My panels config is:  
1. Bot panel
2. Scanner panel
3. Monitoring panel
4. Log panel

Run monitor.py in 3rd panel, it will automatically runs bot in 1st panel
```
python monitor.py
```
Change scan_list file at your opinion,and run scanner.py in 2nd panel
```
python scan.py
```
4th panel i use for logs
```
tail -f trading_bot.log | awk '{$1=$2=$3=""; sub(/^ +/, ""); $1=""; print substr($0, 3)}'
```

Monitor the logs in trading_bot.log and check Telegram for trade updates.
# Hello
## I invite enthusiasts to take part in the development.
# If you want to support the developer...

