# Phase 2 — PWA Deployment Rehberi

Phase 1 (güvenlik temeli: PIN girişi, şifreleme, OAuth) tamamlandı. Bu belge, Meil'i sabit bir yerde barındırarak İphone ve Android'de "uygulama gibi" kullanılabilir hale getirmek için adım adım talimatlar içerir.

## Hedef

- Alan adı + TLS sertifikası (https)
- Meil'i VPS veya sabit makineye kurma
- Caddy ters proxy'si ile otomatik SSL
- İPhone Safari → Ana Ekrana Ekle → Tam ekran uygulamada çalışması

## Ön Koşullar

- Alan adı (`meil.example.com` gibi) — DNS kontrolü gerekli
- VPS (DigitalOcean, Linode, Hetzner ~$5/ay) veya sabit IP'li makine
- SSH erişimi

---

## 1. VPS Seçimi ve Temel Kurulum

### Önerilen VPS'ler (TL hesaplı alternatifler)

| Sağlayıcı | Fiyat | Seçim Sebebi |
|---|---|---|
| **Hetzner Cloud** | ~$3/ay (CX11) | Türkiye dostu, hızlı |
| **DigitalOcean** | ~$5/ay (Basic) | Basit, iyi dokümantasyon |
| **Linode** | ~$5/ay (Nanode) | Stabil, Türkiye'de hız iyi |
| **Contabo** | ~$4/ay | Ucuz, ama yavaş destek |

### Temel Sistem Kurulumu (Ubuntu 22.04 LTS)

SSH'ye bağlandıktan sonra:

```bash
# Sistem güncellemesi
sudo apt update && sudo apt upgrade -y

# Python, pip, git
sudo apt install -y python3.10 python3-pip git wget curl

# Gerekli sistem paketleri (FFmpeg, libffi, vb.)
sudo apt install -y libffi-dev libssl-dev python3-dev build-essential

# Timezon ayarı
sudo timedatectl set-timezone Europe/Istanbul  # Kendi timezone'unuz

# Firewall (UFW)
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow http
sudo ufw allow https
sudo ufw enable
```

---

## 2. Alan Adı ve DNS Yapılandırması

Kayıt danışmanınıza (GoDaddy, Namecheap, Hepsiburada Alan Adı vb.) `A` kaydını VPS'nin IP'sine yönlendirin:

```
example.com    A    123.45.67.89    (VPS IP adresi)
```

DNS yayılması 5 dakika ile 48 saat arasında sürebilir. Kontrol etmek için:

```bash
nslookup example.com
# veya
dig example.com
```

`123.45.67.89` görülüyorsa hazır.

---

## 3. Caddy Kurulumu (Ters Proxy + Otomatik SSL)

Caddy, Let's Encrypt sertifikasını otomatik alır ve HTTPS'i ayarlar.

### Caddy Yükleme

```bash
# Resmi Caddy deposu
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl https://dl.caddy.community/apt/pubkey.gpg | gpg --dearmor | sudo tee /usr/share/keyrings/caddy-archive-keyring.gpg >/dev/null
echo "deb [signed-by=/usr/share/keyrings/caddy-archive-keyring.gpg] https://dl.caddy.community/apt generic01 main" | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install -y caddy
```

### Caddyfile Yapılandırması

```bash
sudo nano /etc/caddy/Caddyfile
```

İçeriği şu şekilde yazın:

```caddyfile
meil.example.com {
    # SSL otomatik — Let's Encrypt'den sertifika alır
    encode gzip

    # FastAPI'ye yönlendir (localhost:8000)
    reverse_proxy localhost:8000

    # Sabit dosyalara bypass (opsiyonel, Caddy zaten cacheler)
    # @static {
    #     path /static/*
    # }
    # file_server @static

    # Gizlilik başlıkları
    header X-Content-Type-Options "nosniff"
    header X-Frame-Options "DENY"
    header Referrer-Policy "strict-origin-when-cross-origin"
    header Permissions-Policy "geolocation=(), microphone=(), camera=()"

    # STS — HTTPS'e zorlama (opsiyonel, dikkat: domain numarasını tutun)
    # header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
}
```

**Not:** İlk kez aktivasyonda `max-age` kullanmayın; test ettikten sonra HSTS ekleyin.

### Caddy'yi Başlat ve Etkinleştir

```bash
# Caddyfile syntax kontrol
sudo caddy validate --config /etc/caddy/Caddyfile

# Başlat
sudo systemctl start caddy
sudo systemctl enable caddy

# Durum kontrol
sudo systemctl status caddy

# Loglar
sudo journalctl -u caddy -n 50
```

---

## 4. Meil'i VPS'ye Kurma

### Repository Clone

```bash
cd /opt
sudo git clone https://github.com/asedition02/meil.git
cd meil
sudo chown -R $USER:$USER .
```

### `.env` Dosyası

```bash
cp .env.example .env
nano .env
```

Gerekli değişkenleri doldurun:

```env
ANTHROPIC_API_KEY=sk-...
MS_CLIENT_ID=2fae9a13-5d84-42f9-bf8b-ff4085924a42  # (veya kendi OAuth app ID)
MEIL_SECRET_KEY=<16+ karakterlik güçlü şifre, veya: python3 -c "import secrets; print(secrets.token_urlsafe(32))">
USER_NAME=Adınız
SYNC_LIMIT=25
```

Şifre kuvvet ölçer: `openssl rand -base64 32`

### Python Ortamı ve Bağımlılıklar

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Veri Klasörleri ve İzinler

```bash
mkdir -p data
chmod 700 data  # Yalnızca sahip okuyabilir
```

---

## 5. Systemd Servisi (Sunucuyu Arka Planda Çalıştır)

### Meil Servisi Oluştur

```bash
sudo nano /etc/systemd/system/meil.service
```

İçeriği:

```ini
[Unit]
Description=Meil — E-posta Tasnif Asistanı
After=network.target

[Service]
Type=notify
User=meil
WorkingDirectory=/opt/meil
Environment="PATH=/opt/meil/venv/bin"
ExecStart=/opt/meil/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=on-failure
RestartSec=10

# Güvenlik
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

### Meil Kullanıcı Oluştur

```bash
sudo useradd -r -s /bin/bash -d /opt/meil meil
sudo chown -R meil:meil /opt/meil
```

### Servisi Etkinleştir

```bash
sudo systemctl daemon-reload
sudo systemctl start meil
sudo systemctl enable meil
sudo systemctl status meil

# Loglar
sudo journalctl -u meil -n 50 -f
```

---

## 6. Otomatik Yedekleme (Opsiyonel)

Günde bir kez `data/` klasörünü yedekle:

```bash
sudo nano /etc/cron.daily/meil-backup
```

```bash
#!/bin/bash
BACKUP_DIR="/opt/meil/backups"
mkdir -p "$BACKUP_DIR"
tar -czf "$BACKUP_DIR/meil_$(date +%Y-%m-%d).tar.gz" /opt/meil/data/
# 7 günden eski yedekleri sil
find "$BACKUP_DIR" -name "meil_*.tar.gz" -mtime +7 -delete
```

```bash
sudo chmod +x /etc/cron.daily/meil-backup
```

---

## 7. Cookies'e Secure Bayrağını Ekleme

Meil `app/auth.py` dosyasında session çerezini ayarlıyor. HTTPS üzerinde çalıştığınız için `Secure` bayrağını ekleyin:

**app/auth.py** içinde `set_session_token()` fonksiyonunu bulup:

```python
response.set_cookie(
    key="session_id",
    value=token,
    max_age=30 * 24 * 60 * 60,
    httponly=True,
    samesite="Lax",
    secure=True,  # ← HTTPS için zorunlu
    domain="meil.example.com",  # opsiyonel, alt domain'lerde çalışmasını istiyorsanız
)
```

Sonra Meil'i yeniden başlatın:

```bash
sudo systemctl restart meil
```

---

## 8. HTTPS Üzerinden Test

Tarayıcıda `https://meil.example.com` açın:

```bash
# Komut satırından da test edin
curl -I https://meil.example.com
```

`200 OK` veya `301` (PIN kurulumuna yönlendirme) bekleyin. Sertifika uyarısı yoksa başarılı.

---

## 9. iPhone PWA Kurulumu

### Safari'de

1. `https://meil.example.com` adresini Safari'ye yazın
2. Adres çubuğunun altındaki **Paylaş** düğmesine basın
3. Aşağı kaydırın → **Ana Ekrana Ekle**
4. Adı "Meil" olarak değiştirip **Ekle**

### Android Chrome'da

1. `https://meil.example.com` açın
2. Sağ üst menü (⋮) → **Yükleme seçenekleri** (Install app)
3. Onaylayın

---

## 10. İzleme ve Günlükler

### Real-time Loglar

```bash
# Meil
sudo journalctl -u meil -f

# Caddy
sudo journalctl -u caddy -f
```

### Let's Encrypt Sertifika Yenileme

Caddy otomatik yeniler, ama durumu kontrol etmek için:

```bash
sudo caddy renew --config /etc/caddy/Caddyfile
```

### Disk Kullanımı

```bash
du -sh /opt/meil/data/
du -sh /opt/meil/

# Veya
df -h /opt
```

---

## 11. Sorun Giderme

| Sorun | Çözüm |
|---|---|
| **Caddy sertifika almıyor** | DNS doğru mu? `dig meil.example.com` kontrol et. 24 saat beklemesi gerekebilir. |
| **"Connection refused"** | Meil çalışıyor mu? `sudo systemctl status meil` kontrol et. |
| **Cookies PWA'da çalışmıyor** | `Secure` bayrağı var mı? HTTP → HTTPS yönlendirmesi var mı? |
| **SSL/TLS hatası** | `/var/log/caddy/` loglarını kontrol et. `sudo caddy reload --config /etc/caddy/Caddyfile` yeniden yükle. |
| **"Method Not Allowed"** | Meil'in API versiyonunu kontrol et (Caddy loglarında 405 hatası mı?). Meil'i yeniden başlat. |

---

## 12. Sonraki Adımlar

- [ ] Günde bir kez `/api/sync` endpoint'ini çağırma (cron job) — tüm hesapları otomatik eşitle
- [ ] Uptime monitoring (Uptime Kuma, Betterstack)
- [ ] E-posta bildirimleri (hata durumunda)
- [ ] S3/wasabi gibi uzak depolama — dataroom'u ölçeklendir

---

## Kaynaklar

- [Caddy resmi dokümantasyonu](https://caddyserver.com)
- [Uvicorn üretime hazırlama](https://www.uvicorn.org)
- [PWA manifest spec](https://www.w3.org/TR/appmanifest/)
- [Let's Encrypt — Otomatik SSL](https://letsencrypt.org)
