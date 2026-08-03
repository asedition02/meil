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
- [ ] (İsteğe bağlı) Web Push bildirimleri — iOS 16.4+ PWA'larda destekleniyor

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

## App Store gönderim kontrol listesi (Capacitor iOS sarmalayıcı — `mobile/`)

Bu bölüm, tek kullanıcılı/kişisel dağıtım için Capacitor iOS sarmalayıcısının
mağazaya (App Store Connect üzerinden — açık liste veya TestFlight) gönderilmeye
hazır olup olmadığını izler.

### Tamamlanan teknik hazırlık

- [x] Xcode projesi (`mobile/ios/App`) mevcut; simülatörde temiz kurulumla
      derlendi ve test edildi (`xcodebuild ... -sdk iphonesimulator` başarılı).
- [x] `Info.plist`: `NSCameraUsageDescription`, `NSPhotoLibraryUsageDescription`,
      `NSFaceIDUsageDescription` dolu; `ITSAppUsesNonExemptEncryption = false`
      (yalnızca standart HTTPS/TLS kullanıldığından ihracat uyum sorusu boş kalmaz).
- [x] `PrivacyInfo.xcprivacy` eklendi (App hedefi) — Apple'ın 2024'ten beri
      zorunlu tuttuğu gizlilik bildirim dosyası; izleme yok, "required reason"
      API'lerden yalnızca `UserDefaults` (CA92.1) beyan edildi.
- [x] Gizlilik politikası (`static/privacy.html`, `meil.tr/privacy.html`) —
      tarih ve iletişim adresi dolduruldu (aagoksu02@gmail.com).
- [x] Destek sayfası eklendi (`static/support.html`, `meil.tr/support.html`) —
      App Store Connect'in zorunlu "Support URL" alanı için.
- [x] Temiz kurulumda telefon genişliğinde (402pt) doğrulandı: alt sekme
      çubuğu, tek panelli Posta görünümü ve PIN kilidi ekranı beklendiği gibi
      çalışıyor. (Not: aynı simülatörde önceden yapılmış eski bir test
      oturumundan kalan WKWebView önbelleği, bir kez masaüstü düzeni
      göstermişti — uygulamayı silip yeniden kurunca düzeldi; kod tarafında
      bir hata değildi.)
- [x] `mobile/package.json` içindeki `sync`/`open:ios` script'leri güncel;
      `npx cap sync ios` sonrası proje sorunsuz derleniyor.

### Kullanıcının (Ahmet) tamamlaması gereken adımlar

Bunlar bir ajanın yapamayacağı, hesap/karar gerektiren adımlardır:

1. **Apple Developer Program üyeliği** (99 $/yıl) — apple.com/developer üzerinden.
2. **Xcode imzalama**: `mobile/ios/App` içinde Xcode'da projeyi açıp
   (`npm run open:ios`), hedef → Signing & Capabilities → kendi Team'ini seçmek
   (şu an `CODE_SIGN_STYLE = Automatic`, Team boş).
3. **Bundle ID kaydı**: `tr.meil.app` Apple Developer portalında kayıtlı
   olmalı (Team seçilince Xcode otomatik önerir).
4. **App Store Connect kaydı**: Yeni uygulama oluştur (adı, kategori, birincil
   dil, fiyatlandırma — muhtemelen ücretsiz).
5. **Gizlilik "nutrition label"**: App Store Connect'te App Privacy formu —
   toplanan veri tipleri (e-posta içeriği, hesap kimlik bilgileri vb.) ve
   kullanım amaçları (uygulama işlevselliği; üçüncü taraf reklam/izleme yok)
   beyan edilmeli. `static/privacy.html` bu beyanla tutarlı olmalı.
6. **Ekran görüntüleri**: En az 6.7" (veya 6.9", cihaza göre) iPhone ekran
   görüntüleri gerekli. Gerçek/anlamlı veri içeren ekran görüntüleri Apple
   tarafından tercih edilir; **kendi hesabınızla** simülatörde veya cihazda
   çekilmeli (bu ajan, kişisel mail içeriğini ifşa etmemek için otomatik
   ekran görüntüsü üretmedi — yalnızca teknik doğrulama için görüntü aldı ve
   sildi).
7. **İnceleme notları / demo hesap**: Uygulama girişte parola/PIN istiyor.
   Apple incelemecisinin test edebilmesi için App Store Connect'in
   "App Review Information" bölümüne çalışan bir demo PIN'i veya test hesabı
   bilgisi eklenmeli.
8. **Guideline 4.2 (Minimum Functionality) riski**: Uygulama esasen
   `meil.tr` sunucusuna bağlanan bir WKWebView sarmalayıcısıdır. Face ID/PIN
   kilidi ve native splash/status bar gibi eklentiler bir miktar native değer
   katıyor, ama Apple incelemesi "sadece web sitesi" gerekçesiyle reddedebilir.
   Red gelirse itiraz metninde native eklentiler (biyometrik kilit, push
   bildirim potansiyeli vb.) vurgulanmalı.
9. **Guideline 5.1.1(v) (Hesap silme)**: Uygulama içinde "Meil hesabı" diye bir
   kayıt akışı yok (tek kullanıcı, sunucu sahibi zaten siz); yalnızca bağlı
   mail hesapları eklenip kaldırılabiliyor. İnceleme notlarında bu modelin
   (tek kullanıcılı, kendi sunucunuz) açıkça belirtilmesi reddi önleyebilir.
10. **Submit for Review** — yukarıdakiler tamamlanınca App Store Connect'ten
    gönderim.
