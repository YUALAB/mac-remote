/* ===== Terminal Module (xterm.js + Socket.IO) ===== */
(function () {
    let term = null;
    let socket = null;
    let fitAddon = null;
    let resizeHandler = null;
    let viewportHandler = null;
    let visibilityHandler = null;

    const isMobile =
        'ontouchstart' in window || navigator.maxTouchPoints > 0;

    /* ---------- public: init ---------- */
    window.initTerminal = function () {
        if (term) return;

        const container = document.getElementById('terminal-container');
        const shell = document.getElementById('app-shell');
        const inputBar = document.getElementById('mobile-input-bar');

        /* ---- 1. Layout first: show input bar ---- */
        if (isMobile) {
            inputBar.classList.remove('hidden');
        }
        // Force synchronous reflow so container has final dimensions
        void container.offsetHeight;

        /* ---- 2. Create xterm.js ---- */
        const FitAddonClass =
            typeof FitAddon !== 'undefined'
                ? FitAddon.FitAddon || FitAddon
                : null;
        fitAddon = FitAddonClass ? new FitAddonClass() : null;

        term = new Terminal({
            cursorBlink: true,
            fontSize: isMobile ? 13 : 14,
            fontFamily: "'SF Mono','Menlo','Courier New',monospace",
            theme: {
                background: '#000000',
                foreground: '#e0e0e0',
                cursor: '#ffffff',
            },
            allowProposedApi: true,
            scrollback: 5000,
        });

        if (fitAddon) term.loadAddon(fitAddon);
        term.open(container);
        if (fitAddon) fitAddon.fit();

        /* ---- 3. Suppress xterm keyboard on mobile ---- */
        if (isMobile) {
            const ta = container.querySelector('.xterm-helper-textarea');
            if (ta) {
                ta.setAttribute('inputmode', 'none');
                ta.setAttribute('readonly', 'readonly');
            }
        }

        /* ---- 4. Socket.IO ---- */
        socket = io({
            reconnection: true,
            reconnectionDelay: 300,
            reconnectionDelayMax: 2000,
            reconnectionAttempts: Infinity,
        });

        socket.on('connect', function () {
            term.clear();
            term.write('\x1b[32m[Connected]\x1b[0m\r\n');
            if (fitAddon) fitAddon.fit();
            socket.emit('ready', { rows: term.rows, cols: term.cols });
        });

        // Track scroll state
        var userScrolledUp = false;
        var lockedScrollPos = 0;
        var outputVp = null;

        // Detect user scroll after terminal opens
        setTimeout(function () {
            outputVp = container.querySelector('.xterm-viewport');
            if (outputVp) {
                outputVp.addEventListener('scroll', function () {
                    var atBottom =
                        outputVp.scrollHeight - outputVp.scrollTop - outputVp.clientHeight < 30;
                    if (atBottom) {
                        userScrolledUp = false;
                    } else {
                        userScrolledUp = true;
                        lockedScrollPos = outputVp.scrollTop;
                    }
                });
            }
        }, 500);

        socket.on('output', function (data) {
            term.write(data);

            if (!outputVp) {
                outputVp = container.querySelector('.xterm-viewport');
            }
            if (!outputVp) return;

            // Apply scroll fix multiple times to override xterm.js
            var count = 0;
            function fixScroll() {
                if (userScrolledUp) {
                    outputVp.scrollTop = lockedScrollPos;
                } else {
                    outputVp.scrollTop = outputVp.scrollHeight;
                }
                if (++count < 5) {
                    requestAnimationFrame(fixScroll);
                }
            }
            requestAnimationFrame(fixScroll);
        });

        socket.on('disconnect', function () {
            term.write('\r\n\x1b[31m[Disconnected]\x1b[0m\r\n');
        });

        socket.io.on('reconnect_attempt', function () {
            term.write('\x1b[33m[Reconnecting...]\x1b[0m\r\n');
        });

        /* ---- 5. Input handling ---- */
        if (!isMobile) {
            // Desktop: xterm.js handles keyboard directly
            term.onData(function (data) {
                if (socket && socket.connected) socket.emit('input', data);
            });
        }

        // Paste on terminal container (both desktop & mobile fallback)
        container.addEventListener('paste', function (e) {
            var text = e.clipboardData && e.clipboardData.getData('text');
            if (text && socket && socket.connected) {
                socket.emit('input', text);
                e.preventDefault();
            }
        });

        /* ---- 6. Resize handling (debounced) ---- */
        var resizeTimer = null;
        var doFit = function () {
            if (!fitAddon || !term) return;
            fitAddon.fit();
            if (socket && socket.connected) {
                socket.emit('resize', { rows: term.rows, cols: term.cols });
            }
        };
        resizeHandler = function () {
            clearTimeout(resizeTimer);
            resizeTimer = setTimeout(doFit, 80);
        };
        window.addEventListener('resize', resizeHandler);

        /* ---- 7. iOS visualViewport (keyboard show/hide) ---- */
        if (window.visualViewport) {
            viewportHandler = function () {
                var vh = window.visualViewport.height;
                shell.style.height = vh + 'px';
                // Prevent iOS scroll offset when keyboard opens
                shell.style.top = window.visualViewport.offsetTop + 'px';
                window.scrollTo(0, 0);
                doFit();
            };
            window.visualViewport.addEventListener('resize', viewportHandler);
            window.visualViewport.addEventListener('scroll', viewportHandler);
            // Initial call to set correct size
            viewportHandler();
        }

        /* ---- 8. Background reconnect ---- */
        visibilityHandler = function () {
            if (
                document.visibilityState === 'visible' &&
                socket &&
                !socket.connected
            ) {
                socket.connect();
            }
        };
        document.addEventListener('visibilitychange', visibilityHandler);

        /* ---- 9. Mobile input bar ---- */
        if (isMobile) {
            setupMobileInput(socket);
        } else {
            term.focus();
        }
    };

    /* ---------- Mobile input bar ---------- */
    function setupMobileInput(sock) {
        var input = document.getElementById('mobile-input');
        var bar = document.getElementById('mobile-input-bar');
        var container = document.getElementById('terminal-container');
        var composing = false;

        function send(data) {
            if (data && sock && sock.connected) sock.emit('input', data);
        }

        // --- IME composition (Japanese / Chinese etc.) ---
        input.addEventListener('compositionstart', function () {
            composing = true;
        });
        input.addEventListener('compositionend', function () {
            composing = false;
            if (input.value) {
                send(input.value);
                input.value = '';
            }
        });

        // --- Each character as typed ---
        input.addEventListener('input', function () {
            if (composing) return;
            if (input.value) {
                send(input.value);
                input.value = '';
            }
        });

        // --- Special keys ---
        input.addEventListener('keydown', function (e) {
            var data = null;
            switch (e.key) {
                case 'Enter':
                    data = '\r';
                    break;
                case 'Backspace':
                    data = '\x7f';
                    break;
                case 'Escape':
                    data = '\x1b';
                    break;
                case 'ArrowUp':
                    data = '\x1b[A';
                    break;
                case 'ArrowDown':
                    data = '\x1b[B';
                    break;
                case 'ArrowLeft':
                    data = '\x1b[D';
                    break;
                case 'ArrowRight':
                    data = '\x1b[C';
                    break;
                case 'Tab':
                    data = '\x09';
                    break;
            }
            if (data) {
                send(data);
                e.preventDefault();
            }
        });

        // --- Paste ---
        input.addEventListener('paste', function (e) {
            var text = e.clipboardData && e.clipboardData.getData('text');
            if (text) {
                send(text);
                e.preventDefault();
            }
        });

        // --- Toolbar buttons (C-c, C-d, Esc, Tab, arrows etc.) ---
        var buttons = bar.querySelectorAll('.tool-btn');
        for (var i = 0; i < buttons.length; i++) {
            (function (btn) {
                btn.addEventListener('click', function (e) {
                    e.preventDefault();
                    var raw = btn.getAttribute('data-key');
                    if (raw) {
                        var decoded = raw.replace(
                            /\\x([0-9a-fA-F]{2})/g,
                            function (_, h) {
                                return String.fromCharCode(
                                    parseInt(h, 16)
                                );
                            }
                        );
                        send(decoded);
                    }
                    input.focus();
                });
            })(buttons[i]);
        }

        // Tap terminal → focus input bar
        container.addEventListener('click', function () {
            input.focus();
        });

        // Auto-focus
        setTimeout(function () {
            input.focus();
        }, 300);
    }

    /* ---------- public: destroy ---------- */
    window.destroyTerminal = function () {
        if (resizeHandler) {
            window.removeEventListener('resize', resizeHandler);
            resizeHandler = null;
        }
        if (viewportHandler && window.visualViewport) {
            window.visualViewport.removeEventListener(
                'resize',
                viewportHandler
            );
            window.visualViewport.removeEventListener(
                'scroll',
                viewportHandler
            );
            viewportHandler = null;
        }
        if (visibilityHandler) {
            document.removeEventListener('visibilitychange', visibilityHandler);
            visibilityHandler = null;
        }
        if (socket) {
            socket.disconnect();
            socket = null;
        }
        if (term) {
            term.dispose();
            term = null;
        }
        fitAddon = null;
        var bar = document.getElementById('mobile-input-bar');
        if (bar) bar.classList.add('hidden');
    };
})();
