# Cuter

YouTube videolarını ve Shorts'ları **MP4** veya **MP3** olarak indiren, istersen sadece seçtiğin bölümü **kırpıp** indiren basit web uygulaması.

## Nasıl çalışır

1. Bağlantıyı yapıştır → **Getir** (başlık, kapak, süre gelir)
2. **Videoyu hazırla** → video sunucuya indirilir
3. Biçimi seç (MP4 / MP3) ve iki seçenekten birini kullan:
   - **Hepsini indir** — videonun tamamı
   - **Kırp ve indir** — önizleme oynatıcısında başlangıç/bitişi seç, sadece o bölümü indir
Arka uçta [yt-dlp](https://github.com/yt-dlp/yt-dlp) + ffmpeg, ön uçta tek bir HTML sayfası var.

## Yerelde çalıştırma

Gereksinim: Python 3.10+ ve `ffmpeg` (macOS: `brew install ffmpeg`, Ubuntu: `sudo apt install ffmpeg`).

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Tarayıcıda http://localhost:8000 adresini aç.

## Docker

```bash
docker build -t cuter .
docker run -p 8000:8000 cuter
```

## Ayarlar

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `PORT` | `8000` | Sunucu portu |
| `MAX_DURATION` | `3600` | İzin verilen en uzun video süresi (saniye) |
| `CACHE_TTL` | `3600` | Hazırlanan videoların sunucuda tutulma süresi (saniye) |
| `CACHE_DIR` | sistem geçici klasörü | Önbellek klasörü |

## Notlar

- MP4: en fazla 1080p, MP3: 192 kbps.
- Kırpma kare-hassas olsun diye kırpılan MP4 yeniden kodlanır (libx264, `veryfast`); uzun bölümlerde birkaç saniye sürebilir.
- YouTube sık sık değiştiği için indirmeler bozulursa `pip install -U yt-dlp` ile güncelle.
- Yalnızca hakkına sahip olduğun ya da indirilmesine izin verilen içerikler için kullan; YouTube Kullanım Şartları'nı göz önünde bulundur.
