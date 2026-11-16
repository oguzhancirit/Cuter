#!/bin/bash
# Cuter'ı tek tıkla başlatır. Gerekli her şeyi (Python, ffmpeg, paketler) ilk açılışta kendisi kurar.
set -e
cd "$(dirname "$0")"

export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
  echo "→ uv kuruluyor (tek seferlik)…"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

PORT="${PORT:-8000}"
echo "→ Cuter başlatılıyor: http://localhost:$PORT  (kapatmak için Ctrl+C)"
( sleep 4; open "http://localhost:$PORT" 2>/dev/null || xdg-open "http://localhost:$PORT" 2>/dev/null || true ) &
exec uv run --python 3.12 --with-requirements requirements.txt app.py
