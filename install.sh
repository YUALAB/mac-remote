#!/bin/bash
# mac-remote ワンコマンドインストーラー
# 使い方: /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/YUALAB/mac-remote/main/install.sh)"
set -e

REPO_URL="https://github.com/YUALAB/mac-remote.git"
INSTALL_DIR="$HOME/mac-remote"
VENV_DIR="$HOME/mac-remote/.venv"
BIN_DIR="$HOME/bin"
SHELL_RC="$HOME/.zshrc"

echo ""
echo "================================"
echo "  mac-remote インストーラー"
echo "================================"
echo ""

# ─── macOSチェック ───
if [[ "$(uname)" != "Darwin" ]]; then
  echo "❌ このツールはmacOS専用です。"
  exit 1
fi
echo "✅ macOS 確認OK"

# ─── Homebrewチェック ───
if ! command -v brew &>/dev/null; then
  echo ""
  echo "📦 Homebrewが見つかりません。インストールします..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  # Apple Siliconの場合PATHを通す
  if [[ -f /opt/homebrew/bin/brew ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  fi
fi
echo "✅ Homebrew 確認OK"

# ─── Python3チェック ───
if ! command -v python3 &>/dev/null; then
  echo ""
  echo "📦 Python3をインストール中..."
  brew install python3
fi
echo "✅ Python3 確認OK: $(python3 --version)"

# ─── cloudflaredチェック ───
if ! command -v cloudflared &>/dev/null; then
  echo ""
  echo "📦 cloudflaredをインストール中..."
  brew install cloudflared
fi
echo "✅ cloudflared 確認OK"

# ─── gitチェック ───
if ! command -v git &>/dev/null; then
  echo ""
  echo "📦 Gitをインストール中..."
  brew install git
fi
echo "✅ Git 確認OK"

# ─── リポジトリclone / 更新 ───
echo ""
if [ -d "$INSTALL_DIR/.git" ]; then
  echo "📥 既存のインストールを更新中..."
  cd "$INSTALL_DIR"
  git pull origin main 2>/dev/null || true
else
  if [ -d "$INSTALL_DIR" ]; then
    echo "📥 既存ディレクトリをバックアップして再インストール..."
    mv "$INSTALL_DIR" "$INSTALL_DIR.bak.$(date +%s)"
  fi
  echo "📥 mac-remoteをダウンロード中..."
  git clone "$REPO_URL" "$INSTALL_DIR"
  cd "$INSTALL_DIR"
fi
echo "✅ mac-remote ダウンロード完了"

# ─── 仮想環境 & Python依存関係 ───
echo ""
if [ ! -d "$VENV_DIR" ]; then
  echo "📦 Python仮想環境を作成中..."
  python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"
echo "📦 Python依存関係をインストール中..."
pip install -r requirements.txt --quiet
echo "✅ 依存関係インストール完了"

# ─── yuatlコマンド作成 ───
mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/yuatl" << 'SCRIPT'
#!/bin/bash
cd ~/mac-remote && source .venv/bin/activate && python3 server.py --tunnel
SCRIPT
chmod +x "$BIN_DIR/yuatl"
echo "✅ yuatl コマンド作成完了"

# ─── PATHに~/binを追加 ───
if ! echo "$PATH" | tr ':' '\n' | grep -qx "$BIN_DIR"; then
  if [ -f "$SHELL_RC" ] && grep -q 'export PATH=.*\$HOME/bin' "$SHELL_RC"; then
    echo "✅ PATH設定済み（次回ターミナル起動時に反映）"
  else
    echo '' >> "$SHELL_RC"
    echo '# mac-remote' >> "$SHELL_RC"
    echo 'export PATH="$HOME/bin:$PATH"' >> "$SHELL_RC"
    echo "✅ PATHを.zshrcに追加しました"
  fi
  export PATH="$BIN_DIR:$PATH"
fi

echo ""
echo "================================"
echo "  ✅ インストール完了！"
echo "================================"
echo ""
echo "  使い方:"
echo "    1. 新しいターミナルを開く（またはこのまま実行）"
echo "    2. yuatl と入力してEnter"
echo "    3. 表示されたURLとPINをYUAに入力"
echo ""
echo "  今すぐ起動するには:"
echo "    yuatl"
echo ""
