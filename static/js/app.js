/* ===== Core App Module ===== */
const App = {
    async apiJson(path, options = {}) {
        const resp = await fetch('/api' + path, {
            headers: { 'Content-Type': 'application/json', ...options.headers },
            ...options,
        });
        if (resp.status === 401) {
            this.showLogin();
            throw new Error('Unauthorized');
        }
        return resp.json();
    },

    async post(path, body) {
        return this.apiJson(path, {
            method: 'POST',
            body: JSON.stringify(body),
        });
    },

    toast(msg, duration = 2000) {
        const el = document.getElementById('toast');
        el.textContent = msg;
        el.classList.add('show');
        setTimeout(() => el.classList.remove('show'), duration);
    },

    showLogin() {
        document.getElementById('login-screen').style.display = 'flex';
        document.getElementById('app-shell').classList.remove('active');
        if (window.destroyTerminal) window.destroyTerminal();
        const inputs = document.querySelectorAll('.pin-digit');
        inputs.forEach(i => i.value = '');
        inputs[0]?.focus();
    },

    showApp() {
        document.getElementById('login-screen').style.display = 'none';
        document.getElementById('app-shell').classList.add('active');
        if (window.initTerminal) window.initTerminal();
    },

    async init() {
        this.setupPinInputs();
        document.getElementById('login-btn').addEventListener('click', () => this.login());
        document.getElementById('logout-btn').addEventListener('click', () => this.logout());

        // Check existing session
        try {
            const resp = await this.apiJson('/auth/check');
            if (resp.authenticated) {
                this.showApp();
                return;
            }
        } catch (e) { /* not authenticated */ }
        this.showLogin();
    },

    setupPinInputs() {
        const inputs = document.querySelectorAll('.pin-digit');
        inputs.forEach((input, i) => {
            input.addEventListener('input', () => {
                if (input.value.length === 1 && i < inputs.length - 1) {
                    inputs[i + 1].focus();
                }
                const pin = Array.from(inputs).map(x => x.value).join('');
                if (pin.length === inputs.length) {
                    this.login();
                }
            });
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Backspace' && !input.value && i > 0) {
                    inputs[i - 1].focus();
                }
                if (e.key === 'Enter') {
                    this.login();
                }
            });
            input.addEventListener('paste', (e) => {
                e.preventDefault();
                const text = (e.clipboardData || window.clipboardData).getData('text').trim();
                for (let j = 0; j < text.length && i + j < inputs.length; j++) {
                    inputs[i + j].value = text[j];
                }
                const next = Math.min(i + text.length, inputs.length - 1);
                inputs[next].focus();
                const pin = Array.from(inputs).map(x => x.value).join('');
                if (pin.length === inputs.length) {
                    this.login();
                }
            });
        });
    },

    async login() {
        const inputs = document.querySelectorAll('.pin-digit');
        const pin = Array.from(inputs).map(x => x.value).join('');
        const errorEl = document.getElementById('login-error');

        if (pin.length < inputs.length) {
            errorEl.textContent = 'Please enter all digits';
            return;
        }

        try {
            const resp = await fetch('/api/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ pin }),
            });
            const data = await resp.json();
            if (data.success) {
                errorEl.textContent = '';
                this.showApp();
            } else {
                errorEl.textContent = data.error || 'Login failed';
                inputs.forEach(i => i.value = '');
                inputs[0].focus();
            }
        } catch (e) {
            errorEl.textContent = 'Connection error';
        }
    },

    async logout() {
        try {
            await this.post('/logout', {});
        } catch (e) { /* ignore */ }
        this.showLogin();
    },
};

document.addEventListener('DOMContentLoaded', () => App.init());
