# 🎮 Minecraft Discord Bot (Aternos)

Bot Discord untuk kontrol server Minecraft di Aternos.

## Setup

### 1. Isi file `.env`
Copy `.env.example` → `.env`, lalu isi semua valuenya.

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Jalankan bot
```bash
python bot.py
```

## Deploy ke Render.com

1. Push folder ini ke GitHub
2. Buka render.com → New → Background Worker
3. Connect repo GitHub kamu
4. Build Command: `pip install -r requirements.txt`
5. Start Command: `python bot.py`
6. Tambahkan Environment Variables (isi dari `.env`)
7. Deploy!

## Environment Variables

| Variable | Keterangan |
|----------|------------|
| `DISCORD_TOKEN` | Token bot Discord |
| `CHANNEL_ID` | ID channel untuk embed status |
| `ATERNOS_USER` | Username akun Aternos |
| `ATERNOS_PASS` | Password akun Aternos |
| `SERVER_NAME` | Nama/subdomain server Aternos |
