# Meil — App Store Metadata Taslağı

Bu belge task #6 kapsamında hazırlanan taslaklardır: App Privacy ("nutrition
label") beyanı, mağaza listeleme metni/anahtar kelimeler ve App Review
notları. Hepsi App Store Connect'e girilmeden önce elden geçirilmeli —
özellikle aşağıdaki **"Demo hesabı" uyarısı** çok önemli.

## ⚠️ Önce oku: Demo hesabı sorunu

Meil şu an **tek kullanıcılı, tek PIN'li** bir uygulama ve senin gerçek
Gmail/Outlook hesabına, gerçek takvimine ve gerçek dataroom dosyalarına
(iş sözleşmeleri, ödeme talepleri, faturalar) bağlı. App Store incelemesi
(hatta yalnızca TestFlight harici test bile) **çalışan bir giriş bilgisi**
ister — yani PIN'ini App Review notlarına yazman, Apple'ın incelemeci
ekibine gerçek iş yazışmalarını açman anlamına gelir.

**Bunu yapma.** Göndermeden önce şu iki seçenekten birini uygula:
1. **Ayrı bir demo örneği** — `meil.tr` yerine örn. `demo.meil.tr` alt
   alanında, boş bir `data/meil.db` ile, birkaç uydurma örnek mail/etkinlik
   eklenmiş, ayrı bir PIN'li ikinci bir Meil kurulumu çalıştır. Review
   notlarına bu ayrı demo bilgilerini yaz.
2. **Yalnızca TestFlight dahili test** — App Store'da hiç yayımlama;
   Apple hesabına dahili test kullanıcısı (kendi Apple ID'n) olarak ekleyip
   uygulamayı yalnızca kendi cihazına kur. Bu yolda tam inceleme/nutrition
   label/mağaza metni gerekmez, çok daha basittir ve tek kullanıcılı bir
   kişisel araç için muhtemelen en doğrusu budur.

Aşağıdaki metinler her iki yol için de hazır tutuluyor; TestFlight-dahili
yolunu seçersen çoğu adımı atlayabilirsin (bkz. checklist dokümanı).

## 1. App Privacy ("nutrition label") — App Store Connect beyanı

App Store Connect → App Privacy bölümünde sorulacak sorulara taslak
cevaplar (gerçek kurulumuna göre doğrula):

**Sizi veya cihazınızı takip etmek için kullanılan veri: Yok.**
Meil reklam/analitik SDK'sı içermez, üçüncü taraf reklam ağıyla veri
paylaşmaz.

**Kullanıcıyla ilişkilendirilen veri toplanıyor mu? Evet.**

| Kategori | Veri türü | Amaç | Kullanıcıyla ilişkili mi? |
|---|---|---|---|
| İletişim Bilgileri | E-posta adresi | Hesap işlevselliği (mail hesabı bağlama) | Evet |
| Kullanıcı İçeriği | E-postalar | Uygulamanın temel işlevi (okuma/tasnif/özet) | Evet |
| Kullanıcı İçeriği | Fotoğraf/video (isteğe bağlı ek) | Dataroom / mail eki | Evet |
| Kullanıcı İçeriği | Diğer kullanıcı içeriği (takvim etkinlikleri, dataroom belgeleri) | Uygulamanın temel işlevi | Evet |
| Tanımlayıcılar | Kullanıcı Kimliği (oturum çerezi) | Uygulama işlevselliği (giriş oturumu) | Evet |
| Hassas Bilgiler | — | Toplanmıyor (uygulama PIN'i düz metin saklanmaz, PBKDF2 özeti tutulur) | — |
| Kullanım Verisi | — | Toplanmıyor (analitik/telemetri yok) | — |
| Tanılama | — | Toplanmıyor (crash reporting/analytics SDK'sı yok) | — |
| Konum | — | Toplanmıyor | — |

Not: Mail/takvim/AI sağlayıcı entegrasyonları (Gmail, Outlook, iCloud,
Google Takvim, seçili AI sağlayıcısı) üçüncü taraf servislerdir; Meil
kendisi bu verileri **kendi sunucusu dışında hiçbir yere satmaz veya
reklam amaçlı paylaşmaz** — yalnızca kullanıcının doğrudan bağladığı
servislerle, kullanıcının talimatıyla konuşur. Bu, "Data Not Collected"
değil "Data collected but not used for tracking" olarak işaretlenmeli.

## 2. Mağaza listeleme metni

**Uygulama adı:** Meil

**Alt başlık (30 karakter sınırı):** AI destekli e-posta asistanı

**Tanıtım metni (170 karakter, sık güncellenebilir):**
Gelen kutunuz artık kendi kendini tasnif ediyor. Meil e-postalarınızı
okur, kategorilere ayırır, özetler ve yanıt taslağı hazırlar.

**Açıklama:**
```
Meil, e-postalarınızı yapay zekâ ile okuyan, tasnif eden, özetleyen ve
yanıt taslağı hazırlayan kişisel bir asistan uygulamasıdır.

• Gelen kutunuzu otomatik olarak kategorilere ayırır (Önemli, İş,
  Fatura/Finans, Bülten…)
• Uzun mailleri tek satırlık özetlere indirger
• Yanıt taslağı önerir — siz yalnızca onaylarsınız
• Takvim, dataroom (belge arşivi) ve global arama tek yerde
• Gmail, Outlook/Microsoft 365, Yahoo, Yandex ve kurumsal IMAP/SMTP
  hesaplarını destekler
• Verileriniz yalnızca sizin sunucunuzda kalır — üçüncü taraf bulut
  depolamaya kopyalanmaz
• PIN korumalı, AES ile şifrelenmiş hesap bilgileri

Meil, kendi sunucunuzda barındırdığınız tek kullanıcılı bir kişisel
asistandır.
```

**Anahtar kelimeler (100 karakter sınırı, virgülle ayrılmış):**
```
email,mail,ai,yapay zeka,gelen kutusu,takvim,asistan,özet,otomasyon,verimlilik
```

**Kategori:** Verimlilik (Productivity)

**Destek URL'si:** https://meil.tr (veya ayrı bir destek sayfası)

**Pazarlama URL'si (opsiyonel):** https://meil.tr

**Gizlilik Politikası URL'si:** https://meil.tr/privacy

## 3. App Review notları (taslak)

```
Meil, kişisel/kendi sunucunuzda barındırdığınız tek kullanıcılı bir
e-posta asistanıdır. Giriş ekranı bir PIN ister.

Test girişi:
  URL: https://<DEMO ALT ALAN ADI>/app
  PIN: <DEMO PIN — gerçek hesap PIN'i DEĞİL>

Not: Bu demo hesabı yalnızca örnek/uydurma veriler içerir, gerçek bir
kişiye ait değildir.

Uygulama; e-posta hesabı bağlama (IMAP/SMTP veya OAuth), takvim
senkronizasyonu (Apple iCloud / Google Takvim) ve dosya arşivi
(Dataroom) özelliklerini içerir. AI destekli tasnif/özet için mail
içeriği seçilen yapay zekâ sağlayıcısına (uygulama içi ayardan
seçilebilir) gönderilir.

ITSAppUsesNonExemptEncryption = false: Uygulama yalnızca standart
HTTPS/TLS kullanır, özel/uluslararası şifreleme algoritması içermez.
```

`<DEMO ALT ALAN ADI>` ve `<DEMO PIN>` kısımlarını, yukarıdaki "Demo
hesabı sorunu" bölümünde açıklanan ayrı demo kurulumunu hazırladıktan
sonra doldur.

## 4. Ekran görüntüleri

App Store Connect, en az 6.7" (iPhone 15/16 Pro Max) ekran görüntüsü
ister. `mobile/store-assets/` içinde ikon (1024) ve splash (2732) var,
ama gerçek uygulama ekran görüntüleri henüz yok — Simulator'dan
Bugün/Posta/Takvim/Dataroom ekranlarının görüntüsü alınmalı (bu, insan
adımları checklist'inde ayrı bir madde).
