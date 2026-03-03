import time
import secrets
import functools
from flask import request, jsonify, session
from config import (
    PIN, MAX_GLOBAL_ATTEMPTS, LOGIN_WINDOW_SECONDS,
    SESSION_LIFETIME_HOURS, LOCKOUT_MULTIPLIER,
)

# グローバルレート制限（IPベースではなくサーバー全体）
_global_attempts: list[float] = []
_consecutive_failures: int = 0
_lockout_until: float = 0.0

# Active sessions: {token: {"created": timestamp}}
_sessions: dict[str, dict] = {}


def _get_client_ip() -> str:
    """Cloudflare Tunnel経由の場合、CF-Connecting-IPを優先使用。"""
    # CF-Connecting-IP: Cloudflareが設定する信頼できるヘッダー
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip.strip()
    # ローカル接続の場合
    return request.remote_addr or "unknown"


def _is_rate_limited() -> tuple[bool, int]:
    """グローバルレート制限チェック。(制限中か, 残り秒数)を返す。"""
    now = time.time()

    # ロックアウト中チェック
    if now < _lockout_until:
        remaining = int(_lockout_until - now) + 1
        return True, remaining

    # ウィンドウ内の試行回数をカウント
    global _global_attempts
    _global_attempts = [t for t in _global_attempts if now - t < LOGIN_WINDOW_SECONDS]
    if len(_global_attempts) >= MAX_GLOBAL_ATTEMPTS:
        return True, LOGIN_WINDOW_SECONDS

    return False, 0


def _record_failure():
    """失敗を記録し、連続失敗で指数バックオフ。"""
    global _consecutive_failures, _lockout_until
    now = time.time()
    _global_attempts.append(now)
    _consecutive_failures += 1

    # 5回連続失敗でロックアウト開始、以降倍々で増加
    if _consecutive_failures >= 5:
        lockout_seconds = LOGIN_WINDOW_SECONDS * (
            LOCKOUT_MULTIPLIER ** (_consecutive_failures - 5)
        )
        # 最大30分
        lockout_seconds = min(lockout_seconds, 1800)
        _lockout_until = now + lockout_seconds


def _reset_failures():
    """認証成功時にカウンターリセット。"""
    global _consecutive_failures, _lockout_until
    _consecutive_failures = 0
    _lockout_until = 0.0


def verify_pin(pin: str) -> tuple[bool, str]:
    """Verify PIN and return (success, message_or_token)."""
    limited, remaining = _is_rate_limited()
    if limited:
        return False, f"試行回数上限です。{remaining}秒後に再試行してください。"

    # タイミング攻撃対策: secrets.compare_digestで一定時間比較
    if secrets.compare_digest(pin.upper(), PIN.upper()):
        token = secrets.token_hex(32)
        _sessions[token] = {
            "created": time.time(),
        }
        _reset_failures()
        return True, token

    _record_failure()
    return False, "PINが正しくありません。"


def is_authenticated() -> bool:
    """Check if the current request has a valid session."""
    token = session.get("auth_token")
    if not token:
        return False
    return _validate_token(token)


def _validate_token(token: str) -> bool:
    """トークンの有効性チェック。"""
    sess = _sessions.get(token)
    if not sess:
        return False
    age_hours = (time.time() - sess["created"]) / 3600
    if age_hours > SESSION_LIFETIME_HOURS:
        del _sessions[token]
        return False
    return True


def require_auth(f):
    """Decorator to require authentication for an endpoint."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not is_authenticated():
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


def is_authenticated_by_token(token: str) -> bool:
    """Check if a raw token string is valid (for Socket.IO auth)."""
    if not token:
        return False
    return _validate_token(token)


def logout():
    """Remove the current session."""
    token = session.get("auth_token")
    if token and token in _sessions:
        del _sessions[token]
    session.clear()
