import time
import uuid
import functools
from flask import request, jsonify, session
from config import PIN, MAX_LOGIN_ATTEMPTS, LOGIN_WINDOW_SECONDS, SESSION_LIFETIME_HOURS

# Track login attempts: {ip: [timestamp, ...]}
_login_attempts: dict[str, list[float]] = {}
# Active sessions: {token: {"created": timestamp, "ip": ip}}
_sessions: dict[str, dict] = {}


def _get_client_ip():
    # Support X-Forwarded-For for cloudflared tunnel
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def _is_rate_limited(ip: str) -> bool:
    now = time.time()
    attempts = _login_attempts.get(ip, [])
    attempts = [t for t in attempts if now - t < LOGIN_WINDOW_SECONDS]
    _login_attempts[ip] = attempts
    return len(attempts) >= MAX_LOGIN_ATTEMPTS


def _record_attempt(ip: str):
    now = time.time()
    if ip not in _login_attempts:
        _login_attempts[ip] = []
    _login_attempts[ip].append(now)


def verify_pin(pin: str) -> tuple[bool, str]:
    """Verify PIN and return (success, message_or_token)."""
    ip = _get_client_ip()

    if _is_rate_limited(ip):
        return False, "Too many attempts. Please wait."

    _record_attempt(ip)

    if pin == PIN:
        token = uuid.uuid4().hex
        _sessions[token] = {
            "created": time.time(),
            "ip": ip,
        }
        return True, token

    return False, "Invalid PIN."


def is_authenticated() -> bool:
    """Check if the current request has a valid session."""
    token = session.get("auth_token")
    if not token:
        return False
    sess = _sessions.get(token)
    if not sess:
        return False
    # Check session expiry
    age_hours = (time.time() - sess["created"]) / 3600
    if age_hours > SESSION_LIFETIME_HOURS:
        del _sessions[token]
        session.clear()
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
    """Check if a raw token string is valid (for cross-origin / Socket.IO auth)."""
    if not token:
        return False
    sess = _sessions.get(token)
    if not sess:
        return False
    age_hours = (time.time() - sess["created"]) / 3600
    if age_hours > SESSION_LIFETIME_HOURS:
        del _sessions[token]
        return False
    return True


def logout():
    """Remove the current session."""
    token = session.get("auth_token")
    if token and token in _sessions:
        del _sessions[token]
    session.clear()
