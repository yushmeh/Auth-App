# logger_config.py — единственная точка настройки логирования

import logging

from config import LOG_FILE, LOG_FORMAT, LOG_DATE_FORMAT


def setup_logger(name: str = "auth_app") -> logging.Logger:
    """
    Создаёт и возвращает настроенный logger.
    Пишет одновременно в файл и в stdout (уровень WARNING и выше).
    """
    logger = logging.getLogger(name)

    # Не добавляем обработчики повторно при повторном вызове
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    # --- Файловый обработчик (все уровни) ---
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # --- Консольный обработчик (WARNING и выше, чтобы не мешать UI) ---
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
