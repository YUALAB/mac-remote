import os
import pty
import select
import struct
import fcntl
import termios
import signal as sig
import subprocess
from flask import request
from flask_socketio import emit, disconnect

# Single persistent shell — survives WebSocket disconnects
_shell = None       # {"fd": master_fd, "proc": Popen} or None
_active_sid = None  # WebSocket sid currently attached
_reader_running = False


def register_handlers(socketio):

    @socketio.on("connect")
    def on_connect(auth_data=None):
        from auth import is_authenticated, is_authenticated_by_token
        # Try token auth first (cross-origin from YUA)
        if auth_data and isinstance(auth_data, dict):
            token = auth_data.get("token")
            if token and is_authenticated_by_token(token):
                return
        # Fall back to cookie-based session auth
        if not is_authenticated():
            disconnect()
            return

    @socketio.on("ready")
    def on_ready(data):
        global _shell, _active_sid, _reader_running
        sid = request.sid
        rows = int(data.get("rows") or 24)
        cols = int(data.get("cols") or 80)

        alive = _shell is not None and _shell["proc"].poll() is None

        if alive:
            # Reattach to existing shell
            _active_sid = sid
            try:
                winsize = struct.pack("HHHH", rows, cols, 0, 0)
                fcntl.ioctl(_shell["fd"], termios.TIOCSWINSZ, winsize)
                # SIGWINCH to process group → TUI apps redraw
                os.killpg(_shell["proc"].pid, sig.SIGWINCH)
            except OSError:
                pass
        else:
            # Create new shell
            if _shell:
                try:
                    os.close(_shell["fd"])
                except OSError:
                    pass

            shell_cmd = os.environ.get("SHELL", "/bin/zsh")
            master_fd, slave_fd = pty.openpty()

            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, winsize)
            fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)

            env = os.environ.copy()
            env["TERM"] = "xterm-256color"

            proc = subprocess.Popen(
                [shell_cmd, "-l"],
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                preexec_fn=os.setsid,
                cwd=os.path.expanduser("~"),
                env=env,
            )
            os.close(slave_fd)

            _shell = {"fd": master_fd, "proc": proc}
            _active_sid = sid

        # Ensure reader loop is running
        if not _reader_running:
            socketio.start_background_task(_read_loop, socketio)

    @socketio.on("disconnect")
    def on_disconnect():
        global _active_sid
        if _active_sid == request.sid:
            _active_sid = None
        # Shell stays alive — don't close fd or kill process

    @socketio.on("input")
    def on_input(data):
        if _shell and _active_sid == request.sid:
            try:
                os.write(_shell["fd"], data.encode())
            except OSError:
                pass

    @socketio.on("resize")
    def on_resize(data):
        if _shell and _active_sid == request.sid:
            try:
                winsize = struct.pack(
                    "HHHH", int(data["rows"]), int(data["cols"]), 0, 0
                )
                fcntl.ioctl(_shell["fd"], termios.TIOCSWINSZ, winsize)
            except OSError:
                pass


def _read_loop(socketio):
    """Continuously read PTY output. Emit to client if connected, discard otherwise."""
    global _reader_running
    _reader_running = True
    try:
        while _shell and _shell["proc"].poll() is None:
            try:
                r, _, _ = select.select([_shell["fd"]], [], [], 0.1)
                if r:
                    data = os.read(_shell["fd"], 4096)
                    if not data:
                        break
                    sid = _active_sid
                    if sid:
                        socketio.emit(
                            "output",
                            data.decode(errors="replace"),
                            to=sid,
                        )
            except (OSError, IOError):
                break
    finally:
        _reader_running = False
