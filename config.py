import os
import secrets
import string
import socket


PORT = int(os.environ.get("MAC_REMOTE_PORT", 8443))
PIN_LENGTH = 8
# 英数字8桁 = 62^8 ≈ 218兆通り（暗号的に安全なPRNG使用）
PIN_CHARS = string.digits + string.ascii_uppercase
PIN = os.environ.get("MAC_REMOTE_PIN") or "".join(secrets.choice(PIN_CHARS) for _ in range(PIN_LENGTH))
SECRET_KEY = secrets.token_hex(32)
HOME_DIR = os.path.expanduser("~")
# グローバルレート制限（IP問わず全体で制限）
MAX_GLOBAL_ATTEMPTS = 10
LOGIN_WINDOW_SECONDS = 60
LOCKOUT_MULTIPLIER = 2  # ロックアウト時間の倍率（連続失敗で指数増加）
SESSION_LIFETIME_HOURS = 24


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"
