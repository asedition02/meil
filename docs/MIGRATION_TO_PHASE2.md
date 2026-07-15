# Phase 2'ye Geçiş Rehberi

Yerel geliştirme ortamınızdan bir VPS'de çalışan, HTTPS'li PWA uygulamasına geçmek için bu rehberi izleyin.

## Ön Koşullar

- ✅ Meil'in en yeni sürümü (`git pull`)
- ✅ Var olan PIN ve hesap verileri yedeklemek isteyen kullanıcılar

---

## 1. Yerel Veriyi Yedekle (İsteğe Bağlı)

Eğer PIN ayarlamış ve hesaplar eklemişseniz, eski ortamı yedekleyin:

```bash
# Meil dizininde
tar -czf ~/Desktop/meil_backup_$(date +%Y%m%d).tar.gz data/

# veya sadece veritabanı
cp data/meil.db ~/Desktop/meil_$(date +%Y%m%d).db
```

---

## 2. Kodu Güncelle

```bash
git fetch origin
git pull origin claude/email-triage-assistant-8oikt1
```

---

## 3. Bağımlılıkları Güncelle

```bash
source venv/bin/activate
pip install -r requirements.txt
```

---

## 4. .env Dosyasını Güncelle

```bash
cp .env.example .env
# Mevcut değişkenleri yeni .env dosyasına kopyala:
# - ANTHROPIC_API_KEY
# - USER_NAME
# - MS_CLIENT_ID (varsa)
# - MEIL_SECRET_KEY (varsa)

nano .env
# Gerekli alanları doldurmaya devam et
```

**Sadece yerel geliştirme kullanıyorsanız:**
- `PRODUCTION` boş bırakın (varsayılan: false)

**VPS'ye dağıtıyorsanız:**
- `PRODUCTION=true` ekleyin

---

## 5. Yerel Test (VPS'ye Dağıtmadan Önce)

```bash
# API versiyonunu kontrol et
curl -s http://localhost:8000/api/status | jq '.api_version'

# Ön dağıtım kontrol
bash scripts/test_production.sh
```

Çıktıda ✅ görmeli ve API başlaması OK olmalı.

---

## 6. PIN ve Hesaplar: Eski Veriyi Aktar mı?

### Seçenek A: Eski Veriyi Taşı (Hızlı)

Yedeklenmiş veritabanınız varsa:

```bash
# Eski sunucudan
scp data/meil.db user@vps.example.com:/opt/meil/data/

# VPS'de
sudo chown meil:meil /opt/meil/data/meil.db
sudo chmod 600 /opt/meil/data/meil.db
sudo systemctl restart meil
```

⚠️ **Uyarı:** Şifre şifreleme anahtarı (`MEIL_SECRET_KEY`) aynı olmalıdır. Farklıysa şifreler çözülemez.

### Seçenek B: Taze Başla (Önerilen)

```bash
# VPS'de: Yeni PIN koyma
# Tarayıcı → https://meil.example.com → PIN belirle
# Hesaplar sekmesi → Mail hesaplarını tek tek yeniden ekle
```

---

## 7. VPS'ye Dağıtım

`docs/PHASE2_DEPLOYMENT.md` dosyasını **tam olarak** takip edin:

1. VPS seç
2. DNS ayarla
3. Caddy kur
4. Meil'i klone et ve `.env` kur
5. Systemd servisi ayarla
6. Test et: `https://meil.example.com`

---

## 8. PWA Kurulumu (iPhone / Android)

### iPhone

1. Safari → `https://meil.example.com`
2. **Adres çubuğunda sağa kaydır** veya **Paylaş** düğmesi
3. **Ana Ekrana Ekle**
4. Tam ekran uygulamada çalışır

### Android

1. Chrome → `https://meil.example.com`
2. Sağ üstteki **menü (⋮)**
3. **Yükleme seçenekleri** veya **Install app**
4. Onayla

---

## 9. Sorun Giderme

### "Sertifika hatası" (SSL/TLS)

- DNS doğru mu? `dig meil.example.com`
- Caddy loglarını kontrol et: `sudo journalctl -u caddy -n 50`
- Let's Encrypt belki 24 saat beklemesi gerekebilir

### "Method Not Allowed" (405)

- Meil API sürümü mi eski?
  ```bash
  curl -s https://meil.example.com/api/status | jq '.api_version'
  ```
- API v14 olmalı
- Sunucu yeniden başlat: `sudo systemctl restart meil`

### "Giriş gerekli" (401) PWA'da

- HTTPS kullanıyor musunuz? PWA HTTPS gerektirir
- Çerez ayarları kontrol et: `PRODUCTION=true` mı?
- Tarayıcı cache'ini temizle (Settings → Clear Cache)

### Veri Kayboldu

Yedekle dosyası varsa geri yükle:
```bash
scp ~/meil_*.db user@vps.example.com:/tmp/
ssh user@vps.example.com
sudo mv /tmp/meil_*.db /opt/meil/data/
sudo chown meil:meil /opt/meil/data/meil.db
sudo systemctl restart meil
```

---

## 10. Sonrası

✅ Başarılı dağıtım sonrasında:

- [ ] Günde bir eşitleme cronjob kur (isteğe bağlı)
- [ ] Uptime monitoring (Betterstack, Uptime Kuma)
- [ ] Otomatik yedekleme kontrol et
- [ ] Periodictask: Let's Encrypt yenileme (`sudo caddy renew`)

---

## Hızlı Başvuru Komutları

```bash
# VPS'ye SSH bağlan
ssh user@meil.example.com

# Sunucu durumu
sudo systemctl status meil
sudo systemctl status caddy

# Loglar (real-time)
sudo journalctl -u meil -f
sudo journalctl -u caddy -f

# Meil'i yeniden başlat
sudo systemctl restart meil

# Caddy'yi yeniden yükle (.env değişti)
sudo caddy reload --config /etc/caddy/Caddyfile

# Disk kullanımı
du -sh /opt/meil/data/

# Sertifika bilgisi
sudo caddy validate --config /etc/caddy/Caddyfile
```

---

## İletişim

Sorularınız varsa:
- 📄 `docs/PHASE2_DEPLOYMENT.md` tam rehberi
- 📋 `docs/PHASE2_SUMMARY.md` FAQ'lar
- 💻 GitHub Issues

Başarılar! 🚀
