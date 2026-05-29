# server.py — Flask REST API. Бизнес-логика живёт только в auth_service.py.

import random
from flask import Flask, request, jsonify, session, send_from_directory

from auth_service import AuthService, LoginResult, RegisterResult
from logger_config import setup_logger
from config import FLASK_HOST, FLASK_PORT, SECRET_KEY, MAX_LOGIN_ATTEMPTS, LOCKOUT_DURATION_SEC

logger = setup_logger()
app = Flask(__name__, static_folder="static")
app.secret_key = SECRET_KEY

service = AuthService()

# ── helpers ────────────────────────────────────────────────────────────────

def _ok(**kwargs):
    return jsonify({"ok": True, **kwargs})

def _err(message: str, code: int = 400, **kwargs):
    return jsonify({"ok": False, "error": message, **kwargs}), code

# ── static ─────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

# ── auth endpoints ─────────────────────────────────────────────────────────

@app.route("/api/register", methods=["POST"])
def register():
    body     = request.get_json(silent=True) or {}
    login    = (body.get("login")    or "").strip()
    password = (body.get("password") or "").strip()

    if not login or not password:
        return _err("Логин и пароль не могут быть пустыми.")

    match service.register(login, password):
        case RegisterResult.SUCCESS:
            return _ok(message=f"Пользователь «{login}» зарегистрирован.")
        case RegisterResult.LOGIN_TAKEN:
            return _err(f"Логин «{login}» уже занят.")


@app.route("/api/login", methods=["POST"])
def login():
    body     = request.get_json(silent=True) or {}
    login    = (body.get("login")    or "").strip()
    password = (body.get("password") or "").strip()

    if not login or not password:
        return _err("Заполните оба поля.")

    match service.login(login, password):
        case LoginResult.SUCCESS:
            session["user"] = login
            return _ok(message=f"Добро пожаловать, {login}!")

        case LoginResult.WRONG_PASSWORD:
            left = service.attempts_left(login)
            return _err(f"Неверный пароль. Осталось попыток: {left}.")

        case LoginResult.JUST_LOCKED:
            # Блокировка только что началась — возвращаем точное количество секунд
            secs = int(service.seconds_locked(login))
            return _err(
                f"Превышен лимит попыток ({MAX_LOGIN_ATTEMPTS}). "
                f"Аккаунт заблокирован на {secs} с.",
                code=429,
                locked_for=secs,
            )

        case LoginResult.ALREADY_LOCKED:
            # Повторная попытка во время блокировки
            secs = int(service.seconds_locked(login)) + 1   # +1 чтобы не показывать 0
            return _err(
                f"Аккаунт заблокирован. Подождите ещё {secs} с.",
                code=423,
                locked_for=secs,
            )


@app.route("/api/logout", methods=["POST"])
def logout():
    session.pop("user", None)
    return _ok(message="Сессия завершена.")

# ── protected zone ─────────────────────────────────────────────────────────

@app.route("/api/status", methods=["GET"])
def status():
    if "user" not in session:
        return _err("Доступ запрещён. Выполните вход.", code=401)

    return _ok(
        cpu     = random.randint(5, 95),
        ram     = random.randint(20, 90),
        disk    = random.randint(10, 99),
        uptime  = random.randint(1, 1440),
        net_in  = random.randint(0, 500),
        net_out = random.randint(0, 200),
        user    = session["user"],
    )

# ── entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("Flask-сервер запущен на http://%s:%s", FLASK_HOST, FLASK_PORT)
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False)
