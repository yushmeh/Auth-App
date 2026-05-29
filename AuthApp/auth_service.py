# auth_service.py — бизнес-логика: регистрация, авторизация, защита от брутфорса

import json
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Final

from config import USERS_FILE, MAX_LOGIN_ATTEMPTS, LOCKOUT_DURATION_SEC
from logger_config import setup_logger

logger = setup_logger()


# ---------------------------------------------------------------------------
# Перечисления результатов операций
# ---------------------------------------------------------------------------

class RegisterResult(Enum):
    SUCCESS     = auto()
    LOGIN_TAKEN = auto()


class LoginResult(Enum):
    SUCCESS        = auto()
    WRONG_PASSWORD = auto()
    JUST_LOCKED    = auto()   # лимит только что исчерпан → начало блокировки
    ALREADY_LOCKED = auto()   # блокировка ещё активна → попытка отклонена


# ---------------------------------------------------------------------------
# Трекер попыток + блокировок (без sleep — только timestamps)
# ---------------------------------------------------------------------------

@dataclass
class _AttemptTracker:
    attempts:     dict[str, int]   = field(default_factory=dict)
    locked_until: dict[str, float] = field(default_factory=dict)

    def increment(self, login: str) -> int:
        self.attempts[login] = self.attempts.get(login, 0) + 1
        return self.attempts[login]

    def reset(self, login: str) -> None:
        """Полный сброс: счётчик + блокировка."""
        self.attempts.pop(login, None)
        self.locked_until.pop(login, None)

    def reset_attempts_only(self, login: str) -> None:
        """Сбросить только счётчик попыток (таймер блокировки остаётся)."""
        self.attempts.pop(login, None)

    def get(self, login: str) -> int:
        return self.attempts.get(login, 0)

    def lock(self, login: str, duration: int) -> None:
        self.locked_until[login] = time.monotonic() + duration

    def seconds_left(self, login: str) -> float:
        until = self.locked_until.get(login)
        if until is None:
            return 0.0
        return max(until - time.monotonic(), 0.0)

    def is_locked(self, login: str) -> bool:
        return self.seconds_left(login) > 0


# ---------------------------------------------------------------------------
# Сервис аутентификации
# ---------------------------------------------------------------------------

class AuthService:
    """
    Вся бизнес-логика пользователей.
    Блокировка реализована через timestamp — без time.sleep,
    поэтому сервер возвращает ответ мгновенно.
    """

    _LOCKOUT_DURATION: Final[int] = LOCKOUT_DURATION_SEC

    def __init__(self) -> None:
        self._tracker = _AttemptTracker()
        self._users: dict[str, str] = self._load_users()

    # ------------------------------------------------------------------
    # Хранилище
    # ------------------------------------------------------------------

    def _load_users(self) -> dict[str, str]:
        if not USERS_FILE.exists():
            return {}
        try:
            text = USERS_FILE.read_text(encoding="utf-8").strip()
            if not text:
                return {}
            data = json.loads(text)
            if not isinstance(data, dict):
                raise ValueError("Корневой элемент JSON должен быть объектом.")
            return data
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error("Не удалось прочитать %s: %s. Начинаем с пустой базой.", USERS_FILE, exc)
            return {}

    def _save_users(self) -> None:
        USERS_FILE.write_text(
            json.dumps(self._users, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # Публичный API
    # ------------------------------------------------------------------

    def register(self, login: str, password: str) -> RegisterResult:
        if login in self._users:
            return RegisterResult.LOGIN_TAKEN
        self._users[login] = password
        self._save_users()
        logger.info("Новый пользователь зарегистрирован: '%s'.", login)
        return RegisterResult.SUCCESS

    def login(self, login: str, password: str) -> LoginResult:
        """
        SUCCESS        — вход выполнен.
        WRONG_PASSWORD — неверный пароль, попытки ещё есть.
        JUST_LOCKED    — эта попытка исчерпала лимит; блокировка только началась.
        ALREADY_LOCKED — аккаунт уже заблокирован; ждите.
        """
        # Блокировка ещё активна — мгновенный отказ
        if self._tracker.is_locked(login):
            secs = self._tracker.seconds_left(login)
            logger.warning(
                "Попытка входа в заблокированный аккаунт '%s' (осталось %.0f с).", login, secs
            )
            return LoginResult.ALREADY_LOCKED

        # Проверяем пароль
        if login not in self._users or self._users[login] != password:
            attempts = self._tracker.increment(login)
            logger.warning(
                "Неудачная попытка входа для '%s' (%d/%d).", login, attempts, MAX_LOGIN_ATTEMPTS
            )

            if attempts >= MAX_LOGIN_ATTEMPTS:
                self._tracker.lock(login, self._LOCKOUT_DURATION)
                self._tracker.reset_attempts_only(login)
                logger.warning(
                    "Превышен лимит попыток для '%s'. Блокировка на %d с.",
                    login, self._LOCKOUT_DURATION,
                )
                return LoginResult.JUST_LOCKED

            return LoginResult.WRONG_PASSWORD

        # Успех
        self._tracker.reset(login)
        logger.info("Успешный вход: '%s'.", login)
        return LoginResult.SUCCESS

    def seconds_locked(self, login: str) -> float:
        """Секунд до снятия блокировки (передаётся клиенту для таймера)."""
        return self._tracker.seconds_left(login)

    def attempts_left(self, login: str) -> int:
        return MAX_LOGIN_ATTEMPTS - self._tracker.get(login)
