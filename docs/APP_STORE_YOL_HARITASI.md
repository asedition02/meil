# Meil — App Store Yol Haritası

Bu belge, Meil'i App Store'da yayımlamak için gereken güvenlik ve altyapı
adımlarını, mevcut durumla birlikte izler.

## Neden bugünkü mimari doğrudan mağazaya çıkamaz

1. **Meil bir Python sunucusudur** (FastAPI + SQLite). iOS App Store yalnızca
   native/hibrit uygulama paketleri kabul eder; sunucu ya kullanıcının kendi
   makinesinde kalır (PWA yolu) ya da barındırılan bir servise dönüşür (SaaS yolu).
2. **Anthropic API anahtarı istemciye gömülemez.** Mağaza dağıtımında anahtar
   binlerce cihaza kopyalanır ve çalınır. AI çağrıları mutlaka sunucu tarafında,
   kullanıcı başına kotayla yapılmalıdır (AI proxy).
3. **Çok kullanıcılılık yoktur.** Mağaza ürünü; kayıt/giriş, kullanıcı başına
   veri izolasyonu, hesap silme ve veri dışa aktarma gerektirir.

## Aşama 1 — Güvenlik temeli (TAMAMLANDI)

- [x] Hesap/takvim şifrelerinin veritabanında şifrelenmesi (Fernet, `MEIL_SECRET_KEY`)
- [x] Microsoft OAuth (şifresiz giriş; jeton önbelleği şifreli saklanır)
- [x] PIN'li uygulama girişi: PBKDF2-SHA256 (200k tur), HttpOnly oturum çerezi,
      30 gün kayan süre, 5 hatalı denemede 60 sn kilit
- [x] Tüm `/api` uçlarının oturum koruması (paylaşım linkleri hariç — tasarım gereği açık)
- [x] CORS'un yerelle sınırlanması, güvenlik başlıkları (nosniff, X-Frame-Options, Referrer-Policy)
- [x] PWA: manifest + service worker + ikonlar → telefona "uygulama gibi" kurulum

## Aşama 2 — Telefonda kullanım (PWA yolu; mağazasız)

- [ ] Sunucuyu sabit bir yere taşı: ofis makinesi (sabit IP/Tailscale) veya ~5$/ay VPS
- [ ] TLS: alan adı + ters proxy (Caddy önerilir — otomatik Let's Encrypt);
      çerezlere `Secure` bayrağı eklenir
- [ ] iPhone'da Safari → Paylaş → **Ana Ekrana Ekle** (uygulama ikonu ve tam ekran hazır)
- [x] (İsteğe bağlı) Web Push bildirimleri — iOS 16.4+ PWA'larda destekleniyor
      (VAPID anahtarları otomatik üretilir; hatırlatma/cevap-bekleme/otomasyon
      bildirimleri e-postanın yanı sıra push olarak da gönderilir — bkz.
      `app/push_notify.py`, Ayarlar menüsü → "Bildirimler")

## Aşama 3 — Ticari ürün (SaaS + mağaza uygulaması)

Sıralı ön koşullar; her biri ayrı iş kalemi:

**Altyapı**
- [ ] Çok kiracılı veri modeli (her tabloya `user_id`; SQLite → PostgreSQL)
- [ ] Kullanıcı kaydı/girişi: e-posta doğrulama, parola sıfırlama, 2FA, hesap silme
- [ ] AI proxy: Anthropic anahtarı yalnızca sunucuda; kullanıcı başına kota/faturalama
- [ ] Barındırma: yönetilen Postgres + uygulama sunucusu + nesne depolama (dataroom)
- [ ] Yedekleme, izleme (uptime/log/hata), hız sınırlama, sızma testi

**İstemci**
- [ ] Capacitor/React Native sarmalayıcı veya native SwiftUI istemci
- [ ] Apple Developer Program üyeliği (99 $/yıl), TestFlight beta süreci

**Uyum / hukuk**
- [ ] KVKK + GDPR: aydınlatma metni, veri işleme envanteri, veri ihlali prosedürü
- [ ] Gizlilik politikası URL'si + Apple "privacy nutrition label" beyanı
- [ ] Gmail desteği için Google API doğrulaması + **CASA güvenlik denetimi**
      (kısıtlı kapsam Gmail API/IMAP erişen ürünlere zorunlu, yıllık)
- [ ] Apple incelemesi gereksinimleri: çalışan demo hesabı, hesap silme akışı,
      üçüncü taraf giriş kuralları

## Notlar

- Aşama 2, Aşama 3'ün ön izlemesi gibidir: PWA'da yazılan hiçbir kod SaaS yolunda
  çöpe gitmez (aynı API, aynı arayüz).
- Aşama 3'e başlamadan önce ürün/fiyat kararı verilmelidir; CASA denetimi ve
  barındırma, yıllık sabit maliyet getirir.
