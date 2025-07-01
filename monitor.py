#!/usr/bin/env python3

import time
import subprocess
from pathlib import Path

# Пути и настройки
trading_pairs_path = Path("trading_pairs.txt")
script_name = "bbot.py"
tmux_window = "bbot"
tmux_pane = "0.0"


def restart_bbot():
    """Функция для перезапуска bbot.py в указанной tmux панели."""
    # Отправляем Ctrl+C для завершения предыдущего процесса, если он есть
    stop_cmd = subprocess.run(["tmux", "send-keys", "-t", f"{tmux_window}:{tmux_pane}", "C-c"], check=False)
    if stop_cmd.returncode != 0:
        print("Ошибка: не удалось отправить Ctrl+C. Проверьте, что сессия tmux существует.")

    # Отправляем команду для запуска bbot.py
    start_cmd = subprocess.run(["tmux", "send-keys", "-t", f"{tmux_window}:{tmux_pane}", f"python3 {script_name}", "Enter"], check=False)
    if start_cmd.returncode != 0:
        print("Ошибка: не удалось запустить bbot.py. Проверьте, что сессия tmux существует.")


def monitor_file_changes():
    """Отслеживает изменения файла trading_pairs.txt и перезапускает bbot.py при изменении."""
    last_modified = trading_pairs_path.stat().st_mtime
    while True:
        try:
            current_modified = trading_pairs_path.stat().st_mtime
            if current_modified != last_modified:
                print(f"Изменения в {trading_pairs_path}. Перезапуск {script_name}...")
                restart_bbot()
                last_modified = current_modified
            time.sleep(5)  # Проверка каждые 5 секунд
        except FileNotFoundError:
            print(f"Файл {trading_pairs_path} не найден.")
            time.sleep(5)


def monitor_bbot_process():
    """Контролирует работу bbot.py и перезапускает его в случае остановки или ошибки."""
    while True:
        # Проверяем, запущен ли процесс bbot.py
        result = subprocess.run(["pgrep", "-f", script_name], capture_output=True)
        if result.returncode != 0:
            print(f"{script_name} не запущен. Перезапуск...")
            restart_bbot()
        time.sleep(5)  # Проверка каждые 5 секунд


if __name__ == "__main__":
    from multiprocessing import Process
    # Создаем два отдельных процесса для мониторинга файла и процесса
    file_monitor = Process(target=monitor_file_changes)
    process_monitor = Process(target=monitor_bbot_process)
    # Запускаем процессы
    file_monitor.start()
    process_monitor.start()
    # Ожидаем завершения
    file_monitor.join()
    process_monitor.join()
