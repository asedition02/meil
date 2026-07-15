# Phase 2 — Üretim Dağıtımı Özeti

**Tarih:** 15 Temmuz 2026  
**Durum:** ✅ Tamamlandı — Meil, HTTPS üzerinde VPS'ye dağıtımda hazır

---

## Neler Yapıldı

### 1. Güvenlik İyileştirmeleri

#### Oturum Çerezleri (Secure Flag)
- **Yerel geliştirme:** `secure=False` (http://localhost üzerinde çalışması için)
- **Üretim:** `secure=True` (HTTPS-only, MITM saldırılarına karşı)
- **SameSite Politikası:**
  - Yerel: `lax` (test için daha esnek)
  - Üretim: `strict` (CSRF koruması)

#### HSTS (HTTP Strict-Transport-Security)
- Üretim modunda otomatik etkinleştirilir
- `max-age=31536000` (1 yıl) → tarayıcı her zaman HTTPS kullanır
- Preload listesine eklenebilir (opsiyonel)

#### Ortam Bayrakları
- Yeni `PRODUCTION` ortam değişkeni
- `.env` dosyasında ayarlanabilir: `PRODUCTION=true|false`
- Varsayılan: `false` (yerel test için güvenli)

---

### 2. Dağıtım Rehberi

**Dosya:** `docs/PHASE2_DEPLOYMENT.md`

Adım adım kurulum talimatları:

1. **VPS Seçimi** — Hetzner, DigitalOcean, Linode (~$5/ay)
2. **Sistem Kurulumu** — Ubuntu 22.04 LTS, firewall, Python
3. **Alan Adı & DNS** — DNS A kaydı VPS IP'sine yönlendir
4. **Caddy Kurulumu** — Otomatik Let's Encrypt SSL
5. **Meil Yükleme** — Git clone, venv, bağımlılıklar
6. **Systemd Servisi** — Arka planda ve otomatik yeniden başlatma
7. **Yedekleme** — Günde bir kez otomatik tar.gz yedeklemesi
8. **PWA Kurulumu**
   - **iPhone:** Safari → Paylaş → Ana Ekrana Ekle
   - **Android:** Chrome → Menü → Yükle

---

### 3. Test ve Doğrulama

**Dosya:** `scripts/test_production.sh`

Ön dağıtım kontrolü:
- ✅ Python sürümü (3.10+)
- ✅ Gerekli paketler (FastAPI, uvicorn, cryptography, anthropic, pypdf)
- ✅ Veritabanı başlatması
- ✅ Ortam değişkenleri
- ✅ Dosya izinleri
- ✅ API başlama testi

Çalıştırma:
```bash
bash scripts/test_production.sh
```

---

## Mimarisinin Açıklaması

### Yerel → Üretim Farkları

```
YEREL (Geliştirme)
├─ http://localhost:8000 (HTTP)
├─ Güvenlik çerezleri: secure=False, SameSite=lax
├─ HSTS başlığı yok
└─ PRODUCTION=false

ÜRETIM (VPS)
├─ https://meil.example.com (HTTPS)
├─ Caddy (Let's Encrypt SSL)
├─ Güvenlik çerezleri: secure=True, SameSite=strict
├─ HSTS: max-age=1 yıl
├─ Systemd servisi (uvicorn)
├─ Otomatik backup
└─ PRODUCTION=true
```

### Caddy'nin Rolü

Caddy, ters proxy (reverse proxy) olarak:
1. `https://meil.example.com` → http://127.0.0.1:8000 yönlendirir
2. Let's Encrypt sertifikasını otomatik alır ve günceller
3. Gzip sıkıştırması yapılır
4. Güvenlik başlıkları ekler

---

## Kullanıcı Deneyimi

### iPhone PWA
1. Safari → `https://meil.example.com`
2. Adres çubuğu → **Paylaş**
3. **Ana Ekrana Ekle**
4. Tam ekran "uygulama" gibi çalışır
5. İnternet bağlantısı kesilirse offline depo (service worker)

### Android PWA
1. Chrome → `https://meil.example.com`
2. Menü (⋮) → **Yükleme seçenekleri**
3. Tam ekran "uygulama" gibi çalışır

### Desktop
- Tarayıcı → https://meil.example.com
- Service worker tarafından önbelleğe alınır
- Offline çalışır (zaten indirilen sayfalar)

---

## Sonraki Adımlar

### Hemen Uygulanabilir
- [ ] VPS'yi seç ve `docs/PHASE2_DEPLOYMENT.md`'yi takip et
- [ ] Alan adını satın al
- [ ] Caddy konfigürasyonunu sınıysa (staging ortamı)
- [ ] iPhone/Android'de PWA'yı test et

### İyileştirmeler (İsteğe Bağlı)
- [ ] Otomatik eşitleme cronjob: `0 */6 * * * curl -s https://meil.example.com/api/sync`
- [ ] Uptime izleme: Uptime Kuma, Betterstack, Healthchecks.io
- [ ] S3/Wasabi depolama: Dataroom dosyalarını buluta taşı
- [ ] Web Push bildirimleri: iOS 16.4+ PWA'larda destekleniyor

### Phase 3'e Hazırlanma (Opsiyonel)
- Multi-tenant mimarisi (kullanıcı kayıt/giriş)
- PostgreSQL (SQLite yerine)
- Subscription / ödeme sistemi
- Apple App Store / Google Play yayını

---

## Dosyalar

| Dosya | Açıklama |
|---|---|
| `docs/PHASE2_DEPLOYMENT.md` | Detaylı VPS dağıtım rehberi |
| `docs/PHASE2_SUMMARY.md` | Bu dosya |
| `scripts/test_production.sh` | Ön dağıtım kontrol betiği |
| `app/config.py` | `PRODUCTION` bayrağı eklendi |
| `app/main.py` | Güvenlik çerezleri ve HSTS güncellenesi |
| `.env.example` | `PRODUCTION` dokümantasyonu |

---

## Sorular & Cevaplar

**S: HTTPS olmadan PWA kurulumu çalışır mı?**  
C: Hayır. PWA spec HTTPS gerektirir (localhost hariç). HTTP'de PWA özelikleri (service worker, offline) kısıtlanır.

**S: Let's Encrypt sertifikası ne sıklıkta güncellenir?**  
C: Caddy otomatik yeniler (90 günde bir). Manuel kontrol: `sudo caddy renew`.

**S: Şifreler güvenli mi?**  
C: Evet.
- Hesap şifreleri: Fernet (AES-128 + HMAC), `MEIL_SECRET_KEY` ile şifrelenir
- PIN: PBKDF2-SHA256, 200k tur, rastgele tuz
- Oturum tokenleri: HTTPS-only, HttpOnly, SameSite=Strict

**S: Dataroom dosyaları ne kadar yer tutar?**  
C: Değişken. Her dosya ~60k karakter sınırıyla metin olarak okunur. Binlerce dosya için S3/Wasabi önerilir.

**S: VPS'de arka planda otomatik eşitleme nasıl yapılır?**  
C: Cron job: `0 */6 * * * curl -s https://meil.example.com/api/sync` (6 saatte bir)

---

## Kaynaklar

- [Caddy Documentation](https://caddyserver.com)
- [Uvicorn Production Guide](https://www.uvicorn.org/deployment/)
- [PWA Manifest Specification](https://www.w3.org/TR/appmanifest/)
- [Mozilla PWA Guide](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps)
- [OWASP: Secure Cookie Attributes](https://owasp.org/www-project-web-security-testing-guide/)

---

**Hazır mısınız?** `docs/PHASE2_DEPLOYMENT.md`'yi açın ve adım 1'den başlayın. 🚀
