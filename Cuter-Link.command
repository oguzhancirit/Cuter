#!/bin/bash
# Cuter'ı başlatır ve her yerden (telefon vb.) açılabilen bir link verir.
# Link, Mac açık ve bu pencere açıkken çalışır. Kapatmak için Ctrl+C.
cd "$(dirname "$0")"
export PATH="$HOME/.local/bin:$PATH"
PORT="${PORT:-8000}"

# uv (Python + paketler): ilk seferde kurulur
if ! command -v uv >/dev/null 2>&1; then
  echo "→ uv kuruluyor (tek seferlik)…"
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi

# cloudflared (tünel): ilk seferde indirilir
CF=.tools/cloudflared
if [ ! -x "$CF" ]; then
  echo "→ cloudflared indiriliyor (tek seferlik)…"
  mkdir -p .tools
  BASE=https://github.com/cloudflare/cloudflared/releases/latest/download
  if [ "$(uname -m)" = "arm64" ]; then
    curl -fsSL "$BASE/cloudflared-darwin-arm64.tgz" | tar -xz -C .tools
  else
    curl -fsSL "$BASE/cloudflared-darwin-amd64.tgz" | tar -xz -C .tools
  fi
  chmod +x "$CF"
fi

trap 'kill $(jobs -p) 2>/dev/null' EXIT

echo "→ Cuter başlatılıyor…"
PORT=$PORT uv run -q --python 3.12 --with-requirements requirements.txt app.py >/dev/null 2>&1 &
until curl -s -o /dev/null "http://localhost:$PORT"; do sleep 1; done

echo "→ Link oluşturuluyor…"
"$CF" tunnel --no-autoupdate --url "http://localhost:$PORT" > .tools/tunnel.log 2>&1 &
URL=""
until [ -n "$URL" ]; do
  sleep 1
  URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' .tools/tunnel.log | head -1)
done

printf '%s' "$URL" | pbcopy 2>/dev/null
echo
echo "  ✅ Cuter hazır:  $URL   (panoya kopyalandı)"
echo "     Telefondan açmak için QR kodu okut:"
uv run -q --python 3.12 --with qrcode python -c \
  "import qrcode,sys; q=qrcode.QRCode(border=1); q.add_data(sys.argv[1]); q.print_ascii(invert=True)" "$URL" 2>/dev/null
echo "  Kapatmak için Ctrl+C."
wait
