import os
import random
import string
import socket


PORT = int(os.environ.get("MAC_REMOTE_PORT", 8443))
PIN_LENGTH = 6
PIN = os.environ.get("MAC_REMOTE_PIN") or "".join(random.choices(string.digits, k=PIN_LENGTH))
SECRET_KEY = os.urandom(32).hex()
HOME_DIR = os.path.expanduser("~")
MAX_LOGIN_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 60
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
