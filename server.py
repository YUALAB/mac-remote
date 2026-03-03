#!/usr/bin/env python3
"""Mac Remote Control - Web server for controlling Mac from iPhone."""

import os
import sys
import re
import signal
import subprocess
import threading
import shutil

# Ensure we're running from the project directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, request, jsonify, session
from flask_socketio import SocketIO
from flask_cors import CORS
from config import PORT, PIN, SECRET_KEY, get_local_ip

from auth import verify_pin, logout as auth_logout

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.secret_key = SECRET_KEY
app.config["SESSION_COOKIE_SAMESITE"] = "None"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SECURE"] = True

CORS(app, origins="*", supports_credentials=True)

socketio = SocketIO(app, cors_allowed_origins="*")

# Track tunnel process for cleanup
_tunnel_proc = None


@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.route("/")
def index():
    return app.send_static_file("index.html")


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()
    pin = data.get("pin", "")
    success, result = verify_pin(pin)
    if success:
        session["auth_token"] = result
        return jsonify({"success": True, "token": result})
    return jsonify({"success": False, "error": result}), 401


@app.route("/api/logout", methods=["POST"])
def logout_route():
    auth_logout()
    return jsonify({"success": True})


@app.route("/api/auth/check")
def auth_check():
    from auth import is_authenticated
    return jsonify({"authenticated": is_authenticated()})


# Register terminal WebSocket handlers
from api.terminal import register_handlers
register_handlers(socketio)


def start_tunnel(port):
    """Start cloudflared quick tunnel and return the public URL."""
    if not shutil.which("cloudflared"):
        print("  [!] cloudflared not found. Tunnel disabled.")
        print("      Install: brew install cloudflared\n")
        return None

    proc = subprocess.Popen(
        ["cloudflared", "tunnel", "--url", f"http://localhost:{port}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    global _tunnel_proc
    _tunnel_proc = proc

    public_url = None

    def read_output():
        nonlocal public_url
        for line in iter(proc.stdout.readline, ""):
            match = re.search(r"(https://[^\s]+\.trycloudflare\.com)", line)
            if match and not public_url:
                public_url = match.group(1)
                print("\n" + "=" * 50)
                print("  REMOTE ACCESS (share this URL)")
                print("=" * 50)
                print(f"\n  URL:  {public_url}")
                print(f"  PIN:  {PIN}")
                print(f"\n  Open on your iPhone from anywhere.")
                print("=" * 50)
                # QRコード表示
                try:
                    import qrcode
                    qr = qrcode.QRCode(box_size=1, border=1)
                    qr.add_data(public_url)
                    qr.make(fit=True)
                    print()
                    qr.print_ascii(invert=True)
                    print()
                except ImportError:
                    pass

    t = threading.Thread(target=read_output, daemon=True)
    t.start()
    return proc


def cleanup(signum=None, frame=None):
    global _tunnel_proc
    if _tunnel_proc:
        _tunnel_proc.terminate()
        _tunnel_proc = None
    sys.exit(0)


def main():
    local_ip = get_local_ip()
    use_tunnel = "--tunnel" in sys.argv or os.environ.get("MAC_REMOTE_TUNNEL") == "1"

    print("\n" + "=" * 50)
    print("  Mac Remote Control")
    print("=" * 50)
    print(f"\n  Local: http://{local_ip}:{PORT}/")
    print(f"  PIN:   {PIN}")

    if use_tunnel:
        print("\n  Starting tunnel...")
        start_tunnel(PORT)
    else:
        print(f"\n  For remote access: python3 server.py --tunnel")

    print("=" * 50 + "\n")

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    socketio.run(
        app,
        host="0.0.0.0",
        port=PORT,
        debug=False,
        allow_unsafe_werkzeug=True,
    )


if __name__ == "__main__":
    main()
