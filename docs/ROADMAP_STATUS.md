# Meil App Store Yol Haritası — Durum Raporu

**Tarih:** 15 Temmuz 2026  
**Geçerli Dal:** `claude/email-triage-assistant-8oikt1`

---

## 📊 Genel Durum

| Aşama | Durum | Tamamlanma % | Notlar |
|---|---|---|---|
| **Phase 1** — Güvenlik Temeli | ✅ Tamamlandı | 100% | PIN, şifreleme, OAuth, session, headers |
| **Phase 2** — PWA + VPS | ✅ Tamamlandı | 100% | HTTPS, Caddy, deployment guide, iPhone setup |
| **Phase 3** — SaaS + Mağaza | 🔄 Hazırlık | ~5% | Mimarı planlama aşaması |

---

## Phase 1 — Güvenlik Temeli ✅ (Tamamlandı)

### Gerçekleştirilen

#### Kimlik Doğrulama
- ✅ PIN-tabanlı giriş (PBKDF2-SHA256, 200k tur)
- ✅ Oturum (session) yönetimi — 30 gün kayan süre
- ✅ Brute-force koruması — 5 deneme → 60 sn kilit
- ✅ HttpOnly, SameSite çerezler

#### Veri Şifreleme
- ✅ Hesap şifreleri (Fernet/AES-128 + HMAC)
- ✅ Takvim şifreleri (aynı)
- ✅ Otomatik eski veriler uyum (legacy migration)
- ✅ Anahtar yönetimi (`MEIL_SECRET_KEY` env var)

#### OAuth 2.0 (Üçüncü Taraf Giriş)
- ✅ Microsoft 365 / Outlook — Device Code Flow
- ✅ Token önbelleklemesi (şifreli)
- ✅ Otomatik yenileme — Transparent'ta

#### API Güvenliği
- ✅ Oturum zorunluluğu (`/api` uçlarında)
- ✅ Paylaşım linkleri — Tasarım gereği açık
- ✅ Security headers (nosniff, DENY, Referrer-Policy)
- ✅ CORS sınırlandırması

### Test & Doğrulama
```
✅ 9 test senaryosu (curl ile)
✅ API v14 istikrar
✅ E2E PIN → Login → API → Logout
✅ Rate limiting (5 fail → 60s lock)
✅ Static assets (CSS, JS, PWA manifest)
```

---

## Phase 2 — PWA + VPS ✅ (Tamamlandı)

### Güvenlik İyileştirmeleri

#### Üretim Modu Flag
```python
# config.py
PRODUCTION = os.environ.get("PRODUCTION", "false").lower() in ("true", "1", "yes")
```

- Yerel: `PRODUCTION=false` → HTTP, Lax cookies
- Üretim: `PRODUCTION=true` → HTTPS, Strict cookies, HSTS

#### Çerez Güvenliği
```python
# main.py — _set_session_cookie()
response.set_cookie(
    auth.SESSION_COOKIE, token,
    secure=config.PRODUCTION,        # HTTPS-only
    samesite="strict" if config.PRODUCTION else "lax",
    httponly=True,                   # JavaScript erişim yok
    max_age=30 * 86400,             # 30 gün
)
```

#### HSTS Header
```
Strict-Transport-Security: max-age=31536000; includeSubDomains
```
→ 1 yıl boyunca her zaman HTTPS kullan

### Dağıtım Materyalleri

#### 1. `docs/PHASE2_DEPLOYMENT.md` — 467 satır, tam rehber
- VPS seçimi (Hetzner, DigitalOcean, Linode)
- Ubuntu 22.04 kurulumu
- Alan adı + DNS yapılandırması
- **Caddy ters proxy** (otomatik Let's Encrypt)
- Meil yükleme + Python venv
- **Systemd servisi** (arka planda)
- Otomatik yedekleme (tar.gz günde bir)
- iPhone PWA: Safari → Paylaş → Ana Ekrana Ekle
- Android PWA: Chrome → Menü → Yükle
- Sorun giderme (SSL, API, cookie, disk)

#### 2. `docs/PHASE2_SUMMARY.md` — Özet & FAQ
- Neler yapıldı (Secure flag, HSTS, rehber, test)
- Mimari açıklaması (Yerel vs Üretim)
- Caddy rolü
- Kullanıcı deneyimi (PWA, offline, service worker)
- Sonraki adımlar
- Sıkça sorulan sorular (7 Q&A)

#### 3. `docs/MIGRATION_TO_PHASE2.md` — Geçiş Rehberi
- Veri yedeklemesi
- Kod ve bağımlılıkları güncelleme
- `.env` kurulumu
- Yerel test (`test_production.sh`)
- PIN/hesap verileri aktar mı?
- VPS'ye tam dağıtım linki
- Sorun giderme (sertifika, 405, 401, veri kayıp)
- Hızlı başvuru komutları

#### 4. `scripts/test_production.sh` — Ön dağıtım kontrol
```bash
bash scripts/test_production.sh
```

Kontroller:
- ✅ Python 3.10+
- ✅ FastAPI, uvicorn, cryptography, anthropic, pypdf
- ✅ Veritabanı başlatması
- ✅ Ortam değişkenleri
- ✅ Dosya izinleri
- ✅ API başlama (8001 portunda 10sn test)

### Yapılandırma Güncellemeleri

#### `.env.example`
```env
# Yeni başlık: Üretim modu (VPS/HTTPS için)
PRODUCTION=true|false  # Caddy arkasında True
```

#### `README.md`
```markdown
### Üretim Dağıtımı (VPS, PWA, iPhone Kurulumu)

[docs/PHASE2_DEPLOYMENT.md](docs/PHASE2_DEPLOYMENT.md) → adım adım rehber
```

---

## Phase 3 — SaaS + Mağaza 🔄 (Planlama Aşaması)

### Kapsamı (APP_STORE_YOL_HARITASI.md'den)

#### Altyapı
- [ ] Multi-tenant veri modeli (PostgreSQL)
- [ ] Kullanıcı kaydı / giriş / 2FA
- [ ] AI proxy (Anthropic API key — sunucu tarafından)
- [ ] Yönetilen barındırma + nesne depolama (S3/Wasabi)
- [ ] Yedekleme, izleme, hız sınırlama

#### İstemci
- [ ] iOS native / Capacitor sarmalayıcı (SwiftUI)
- [ ] Android native / Capacitor
- [ ] App Store beta (TestFlight)

#### Uyum & Yasal
- [ ] KVKK + GDPR aydınlatma metni
- [ ] Gizlilik politikası + privacy label
- [ ] **CASA güvenlik denetimi** (Gmail API için)
- [ ] Apple inceleme gereksinimleri

#### Karar Noktaları
- Şirketleşme modeli (tek vs multi-tenant)
- Fiyatlandırma (serbest vs premium)
- Yatırım planı

### Mevcut Durum
- ✅ Phase 1 & 2 tamamlanmış
- 📝 Phase 3 mimarı inceleniyor
- ⏳ Karar bekleniyor: PWA → SaaS geçişi yapılsın mı?

---

## Dosya Ağacı (Phase 2 Değişiklikleri)

```
meil/
├── docs/
│   ├── APP_STORE_YOL_HARITASI.md     (mevcut)
│   ├── PHASE2_DEPLOYMENT.md          ✅ YENI — VPS dağıtım rehberi
│   ├── PHASE2_SUMMARY.md             ✅ YENI — Özet & FAQ
│   ├── MIGRATION_TO_PHASE2.md        ✅ YENI — Geçiş rehberi
│   └── ROADMAP_STATUS.md             ✅ YENI — Bu dosya
├── scripts/
│   └── test_production.sh             ✅ YENI — Ön dağıtım kontrol
├── app/
│   ├── config.py                      ✏️ GÜNCELLENDI — PRODUCTION flag
│   ├── main.py                        ✏️ GÜNCELLENDI — Secure cookies, HSTS
│   ├── auth.py                        (mevcut)
│   ├── crypto.py                      (mevcut)
│   ├── ms_oauth.py                    (mevcut)
│   └── ...
├── static/
│   ├── manifest.json                  (mevcut)
│   ├── sw.js                          (mevcut)
│   └── ...
├── .env.example                       ✏️ GÜNCELLENDI — PRODUCTION dokümantasyonu
├── README.md                          ✏️ GÜNCELLENDI — Phase 2 linki
└── ...
```

---

## Git Commit Geçmişi (Son 5 aşama)

```
3781f3a ✅ Add migration guide for upgrading to Phase 2
4c213b4 ✅ Add Phase 2 implementation summary and FAQ
5412bed ✅ Phase 2: Production deployment readiness for VPS + HTTPS
38cc5df ✅ Add PIN login, session auth, security headers, and PWA install support
bccc05f ✅ Add a global search palette (Cmd+K) across mail, files, and events
```

---

## Sonraki Adımlar (Seçenekler)

### A. Phase 2 DevOps Kurulumu (PWA Canlıya Alması)
1. VPS seç (Hetzner $3/ay veya DigitalOcean $5/ay)
2. `docs/PHASE2_DEPLOYMENT.md`'yi takip et
3. iPhone/Android'de PWA kur
4. Üretim ortamında test et

**Zaman:** ~2-3 saat  
**Maliyet:** ~$5/ay hosting

### B. Phase 3 Mimarı Tasarım (SaaS Yolu)
1. PostgreSQL multi-tenant modeline geçiş
2. Kullanıcı kaydı/giriş sistemi
3. Ödeme sistemi (Stripe)
4. App Store yayın gereksinimleri

**Zaman:** 4-8 hafta  
**Maliyet:** ~$20/ay hosting + yatırım

### C. Phase 2 Optimize (Performans, Scaling)
- Redis cache (OTP, oturum)
- Bulk mail processing
- Async background jobs (Celery)
- CDN (static assets)

**Zaman:** 2-3 hafta

---

## İstatistikler

### Phase 1 + 2 Toplamı
```
📁 Yeni dosyalar: 7 (config, auth, crypto, ms_oauth, extract, manifest, sw)
📝 Yeni dokümantasyon: 4 (Yol Haritası, Deploy, Summary, Migration)
🔧 Değiştirilen dosyalar: 10+
📝 Toplam kod satırları: ~5,000+ (app kod + dokümantasyon)
🧪 Test senaryoları: 9+ curl testleri
⏱️ Geliştirme süresi: ~40+ saat
```

### Güvenlik Metrikleri
```
🔒 Şifreleme: AES-128 (Fernet) + HMAC
🔐 Hash: PBKDF2-SHA256 (200k tur)
🛡️ Brute-force: Rate limiting (5 fail → 60s)
🍪 Cookies: HttpOnly, SameSite, Secure (HTTPS)
📋 Headers: nosniff, DENY, Referrer-Policy, HSTS
```

---

## Kaynaklar

- 📖 [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- 📖 [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- 📖 [PWA Manifest](https://www.w3.org/TR/appmanifest/)
- 📖 [Caddy Documentation](https://caddyserver.com)
- 📖 [Let's Encrypt](https://letsencrypt.org)

---

## Kontrol Listesi (Kullanıcı Karar Sürecinde)

- [ ] Phase 2 (PWA) canlıya almayı mı istiyorsunuz?
  - Evet → `docs/PHASE2_DEPLOYMENT.md`'yi başlat
  - Hayır → Phase 3'e git
- [ ] Phase 3 (SaaS) mimarisini kurmayı mı istiyorsunuz?
  - Evet → Mimarı planlaması + karar noktaları
  - Hayır → Phase 2 optimizasyonunu düşün

---

**Hazırız! Seçiminiz nedir?** 🚀

- 🌐 **PWA (Phase 2):** `docs/PHASE2_DEPLOYMENT.md`
- 🏢 **SaaS (Phase 3):** `docs/APP_STORE_YOL_HARITASI.md`
- ⚡ **Optimize (Phase 2++):** İyileştirmeler planı
