"""YouTube / Shorts -> MP4 / MP3 dönüştürücü (kırpma destekli).

Akış:
  1. /api/info     -> başlık, kapak, süre
  2. /api/prepare  -> videoyu sunucuya indirir (önbellek), bir iş kimliği döner
  3. /api/media/ID -> önizleme için hazırlanan MP4
  4. /api/export/ID?format=mp4|mp3[&start=&end=] -> tamamı ya da kırpılmış hali
"""

from __future__ import annotations

import os
import re
import secrets
import shutil
import subprocess
import tempfile
import time
from urllib.parse import urlparse

import yt_dlp
from flask import Flask, abort, jsonify, request, send_file, send_from_directory

app = Flask(__name__, static_folder="static")

ALLOWED_HOSTS = {
    "youtube.com", "www.youtube.com", "m.youtube.com",
    "music.youtube.com", "youtu.be",
}
MAX_DURATION = int(os.environ.get("MAX_DURATION", 60 * 60))   # saniye
CACHE_TTL = int(os.environ.get("CACHE_TTL", 60 * 60))          # saniye
CACHE_DIR = os.environ.get("CACHE_DIR", os.path.join(tempfile.gettempdir(), "yt-donusturucu"))
JOB_ID = re.compile(r"^[a-f0-9]{32}$")

os.makedirs(CACHE_DIR, exist_ok=True)


def find_ffmpeg() -> str:
    """Sistemde ffmpeg varsa onu, yoksa imageio-ffmpeg ile gelen hazır ikiliyi kullan."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


FFMPEG = find_ffmpeg()


# ---------- yardımcılar ----------

def clean_url(raw: str | None) -> str | None:
    """Sadece YouTube adreslerini kabul et."""
    raw = (raw or "").strip()
    if not raw:
        return None
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    host = (urlparse(raw).hostname or "").lower()
    return raw if host in ALLOWED_HOSTS else None


def base_opts() -> dict:
    return {"quiet": True, "no_warnings": True, "noprogress": True, "noplaylist": True,
            "ffmpeg_location": FFMPEG}


def sweep_cache() -> None:
    """Süresi dolmuş işleri sil."""
    now = time.time()
    for name in os.listdir(CACHE_DIR):
        path = os.path.join(CACHE_DIR, name)
        if os.path.isdir(path) and now - os.path.getmtime(path) > CACHE_TTL:
            shutil.rmtree(path, ignore_errors=True)


def job_dir(job_id: str) -> str:
    path = os.path.join(CACHE_DIR, job_id)
    if not JOB_ID.match(job_id) or not os.path.isfile(os.path.join(path, "video.mp4")):
        abort(404)
    return path


def safe_name(title: str) -> str:
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "", title).strip()
    return (name or "video")[:120]


def fmt_ts(sec: float) -> str:
    m, s = divmod(int(sec), 60)
    return f"{m:02d}m{s:02d}s"


def send_and_delete(path: str, download_name: str):
    """Dosyayı aç, diskten sil, açık tanıtıcıyı gönder (POSIX'te güvenli)."""
    fh = open(path, "rb")
    try:
        os.remove(path)
    except OSError:
        pass  # Windows'ta silinemezse sweep_cache sonra temizler
    return send_file(fh, as_attachment=True, download_name=download_name)


# ---------- rotalar ----------

@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/info")
def info():
    url = clean_url(request.args.get("url"))
    if not url:
        return jsonify(error="Geçerli bir YouTube bağlantısı gir."), 400
    try:
        with yt_dlp.YoutubeDL(base_opts()) as ydl:
            data = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError:
        return jsonify(error="Video bulunamadı ya da erişilemiyor."), 404

    return jsonify(
        title=data.get("title"),
        channel=data.get("channel") or data.get("uploader"),
        thumbnail=data.get("thumbnail"),
        duration=data.get("duration"),
        is_short="/shorts/" in url or 0 < (data.get("duration") or 999) <= 60,
    )


@app.post("/api/prepare")
def prepare():
    url = clean_url((request.get_json(silent=True) or {}).get("url"))
    if not url:
        return jsonify(error="Geçerli bir YouTube bağlantısı gir."), 400

    sweep_cache()
    job_id = secrets.token_hex(16)
    workdir = os.path.join(CACHE_DIR, job_id)
    os.makedirs(workdir)
    opts = base_opts() | {
        "outtmpl": os.path.join(workdir, "video.%(ext)s"),
        "format": "bv*[ext=mp4][height<=1080]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b",
        "merge_output_format": "mp4",
        "match_filter": yt_dlp.utils.match_filter_func(f"duration <=? {MAX_DURATION} & !is_live"),
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            data = ydl.extract_info(url, download=True)
        if not os.path.isfile(os.path.join(workdir, "video.mp4")):
            raise FileNotFoundError
    except Exception:
        shutil.rmtree(workdir, ignore_errors=True)
        return jsonify(error="Video hazırlanamadı (çok uzun, canlı yayın ya da kısıtlı olabilir)."), 500

    title = safe_name(data.get("title") or "video")
    with open(os.path.join(workdir, "title.txt"), "w", encoding="utf-8") as f:
        f.write(title)
    return jsonify(id=job_id, title=title, duration=data.get("duration"))


@app.get("/api/media/<job_id>")
def media(job_id):
    # conditional=True -> Range istekleri; <video> içinde ileri/geri sarma çalışır
    return send_file(os.path.join(job_dir(job_id), "video.mp4"), mimetype="video/mp4", conditional=True)


@app.get("/api/export/<job_id>")
def export(job_id):
    workdir = job_dir(job_id)
    os.utime(workdir)  # kullanımda olan işi taze tut
    fmt = request.args.get("format", "mp4")
    if fmt not in ("mp4", "mp3"):
        return jsonify(error="Geçersiz biçim."), 400

    src = os.path.join(workdir, "video.mp4")
    with open(os.path.join(workdir, "title.txt"), encoding="utf-8") as f:
        title = f.read()

    try:
        start = float(request.args["start"]) if "start" in request.args else None
        end = float(request.args["end"]) if "end" in request.args else None
    except ValueError:
        return jsonify(error="Geçersiz zaman aralığı."), 400
    trimmed = start is not None or end is not None
    start = max(0.0, start or 0.0)
    if end is not None and end - start < 0.5:
        return jsonify(error="Kırpılan bölüm en az 0,5 saniye olmalı."), 400

    # Tamamı + MP4: hazır dosyayı doğrudan gönder
    if fmt == "mp4" and not trimmed:
        return send_file(src, as_attachment=True, download_name=f"{title}.mp4")

    cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y"]
    if trimmed:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", src]
    if end is not None:
        cmd += ["-t", f"{end - start:.3f}"]
    if fmt == "mp3":
        cmd += ["-vn", "-c:a", "libmp3lame", "-b:a", "192k"]
    else:
        # Kare-hassas kesim için yeniden kodla
        cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]
    out = os.path.join(workdir, f"out-{secrets.token_hex(4)}.{fmt}")
    cmd.append(out)

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not os.path.isfile(out):
        app.logger.error("ffmpeg: %s", result.stderr[-500:])
        return jsonify(error="Dönüştürme başarısız oldu."), 500

    suffix = f" ({fmt_ts(start)}-{fmt_ts(end) if end is not None else 'son'})" if trimmed else ""
    return send_and_delete(out, f"{title}{suffix}.{fmt}")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), debug=False, threaded=True)
