# config.py — централизованные константы приложения

from pathlib import Path

BASE_DIR = Path(__file__).parent
USERS_FILE = BASE_DIR / "users.json"
LOG_FILE   = BASE_DIR / "app.log"

MAX_LOGIN_ATTEMPTS:   int = 3
LOCKOUT_DURATION_SEC: int = 5

LOG_FORMAT      = "%(asctime)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Flask
FLASK_HOST   = "127.0.0.1"
FLASK_PORT   = 5000
SECRET_KEY   = "change-me-in-production-please"
