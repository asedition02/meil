# Meil — App Store: Yalnızca Senin Yapabileceğin Adımlar

Kod tarafı (Capacitor iskeleti, ikonlar/splash, Info.plist izinleri,
gizlilik sayfası, mağaza metni taslağı — bkz. `APP_STORE_METADATA.md`)
tamamlandı. Geri kalanlar Apple hesabı, ödeme ve kimlik doğrulaması
gerektirdiği için yalnızca sen yapabilirsin. Sırayla:

## 0. Önce karar ver: TestFlight-dahili mi, tam App Store mu?

Meil şu an tek kullanıcılı, kişisel bir araç. İki yol var:

- **A) Sadece kendi telefonuna kurmak istiyorsan** → TestFlight'ta
  "Internal Testing" yeterli. Apple Developer üyeliği yine de gerekir
  ama **tam inceleme, nutrition label formu, mağaza açıklaması,
  anahtar kelime, ekran görüntüsü gerekmez** — çok daha hızlı.
- **B) Herkese açık App Store'da yayımlamak istiyorsan** → Tam inceleme
  süreci, `APP_STORE_METADATA.md`'deki tüm metinler, ve özellikle
  **ayrı bir demo hesabı** (gerçek maillerini Apple'a açmamak için)
  gerekir.

Bu belgede her iki yol da işaretli; A'yı seçersen "(yalnızca B)" ile
işaretli adımları atlayabilirsin.

## 1. Apple Developer Program'a kaydol

- https://developer.apple.com/programs/enroll/ adresinden, Apple ID'nle
  başvur.
- Bireysel (Individual, 99 $/yıl) yeterli — şirket adına yayımlamayacaksan
  Organization'a gerek yok.
- Kimlik doğrulama 24-48 saat sürebilir (Apple bazen ek belge ister).

## 2. Bundle ID'yi Apple Developer portalında kaydet

- developer.apple.com → Certificates, IDs & Profiles → Identifiers → "+"
- Bundle ID: `tr.meil.app` (bu `mobile/capacitor.config.json`'da zaten
  tanımlı, portalda da aynısını kaydetmen gerekiyor — değiştirme).
- Capabilities: şimdilik ek bir şey işaretlemene gerek yok (push
  bildirimleri ileride eklenirse o zaman işaretlenir).

## 3. App Store Connect'te uygulamayı oluştur

- https://appstoreconnect.apple.com → My Apps → "+" → New App
- Platform: iOS, İsim: Meil, Ana dil: Türkçe, Bundle ID: `tr.meil.app`,
  SKU: örn. `meil-ios-001` (senin seçtiğin, sadece senin göreceğin bir kod)

## 4. Xcode'da imzalama (signing)

- `mobile/ios/App/App.xcworkspace` dosyasını Xcode'da aç
  (`.xcodeproj` değil, `.xcworkspace`!)
- Signing & Capabilities sekmesinde "Team" olarak Apple Developer
  hesabını seç, "Automatically manage signing" işaretli kalsın.
- Bir iPhone/USB ile bağlıysa ya da Simulator'da "Any iOS Device" seçip
  derlemeyi bir kez dene — imzalama hatası çıkarsa Xcode genelde tek
  tıkla düzeltmeyi öneriyor ("Try Again").

## 5. (yalnızca B) Demo hesabını hazırla

`APP_STORE_METADATA.md`'deki "⚠️ Demo hesabı sorunu" bölümünü oku —
gerçek PIN'ini/mailini Apple'a vermeden önce ayrı bir demo kurulumu
(ayrı alt alan adı + boş veritabanı + birkaç uydurma mail/etkinlik)
hazırlaman gerekiyor. Bu, sunucu tarafında yeni bir `systemd` servisi +
yeni bir domain/subdomain DNS kaydı gerektirir — istersen bu kurulumu
ben (Claude Code) senin onayınla yapabilirim, ama DNS kaydını ve
(varsa) yeni alt alan adının sertifikasını sen ya da barındırma
panelin üzerinden ayarlaman gerekebilir.

## 6. (yalnızca B) Ekran görüntülerini al

- Xcode → Simulator → iPhone 16 Pro Max (6.7") seç, uygulamayı çalıştır.
- Bugün, Posta, Takvim, Dataroom ekranlarından `Cmd+S` ile en az 3-5
  ekran görüntüsü al (Simulator otomatik Masaüstüne kaydeder).
- App Store Connect → uygulaman → App Store sekmesi → 6.7" Display
  bölümüne yükle.

## 7. (yalnızca B) Mağaza metnini gir

`APP_STORE_METADATA.md`'deki açıklama/anahtar kelime/alt başlık
metinlerini App Store Connect → App Store sekmesindeki ilgili alanlara
kopyala. Gizlilik Politikası URL'si: `https://meil.tr/privacy`.

## 8. App Privacy formunu doldur

App Store Connect → App Privacy → "Get Started". `APP_STORE_METADATA.md`
§1'deki tabloyu takip ederek soruları cevapla (bu form Apple'ın kendi
arayüzünde adım adım soru soruyor, kopyala-yapıştır değil, tabloyu
referans alarak elle işaretleyeceksin).

## 9. Export Compliance (şifreleme beyanı)

- Xcode Archive sırasında ya da App Store Connect'te sorulacak: "Does
  your app use encryption?" → **Evet, ama yalnızca standart HTTPS/TLS**
  (`ITSAppUsesNonExemptEncryption = false` zaten Info.plist'te ayarlı).
  Bu soruda "Uses only standard/exempt encryption" seçeneğini işaretle.

## 10. Archive + Upload

- Xcode → Product → Archive (Simulator değil, "Any iOS Device" hedefi
  seçiliyken).
- Archive bitince açılan Organizer penceresinde "Distribute App" →
  "App Store Connect" → "Upload".
- Yükleme birkaç dakika sürer, ardından App Store Connect'te "Processing"
  durumunu görürsün (genelde 15-60 dk).

## 11. TestFlight

- **(A yolu)** App Store Connect → TestFlight → Internal Testing →
  kendi Apple ID'ni test kullanıcısı olarak ekle → build'i seç → cihazına
  TestFlight uygulamasından indir. **Burada dur, 12. adıma geçme.**
- **(B yolu)** External Testing'e build ekleyip Beta App Review'a
  gönder (bu, tam incelemeden daha hafif ama yine de Apple onayı ister,
  1-2 gün sürebilir).

## 12. (yalnızca B) Submit for Review

- App Store Connect → uygulaman → "Submit for Review".
- Age Rating anketini doldur (Meil için çoğu soru "Yok/No" olacak —
  şiddet, yetişkin içerik vb. içermiyor).
- İnceleme genelde 1-3 gün sürer. Reddedilirse Apple neden yazar;
  çoğu red nedeni ya demo hesap bilgisi eksik/çalışmıyor ya da gizlilik
  formu ile gerçek davranış uyuşmuyor oluyor — her ikisi de yukarıdaki
  adımlarla önlenmiş olmalı.

---

Herhangi bir adımda (özellikle 5. adımdaki demo sunucusu kurulumunda)
yardım istersen söyle, o kısmı benimle birlikte ilerletebiliriz.
