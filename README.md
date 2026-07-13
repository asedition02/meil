# 📬 Meil — E-posta Tasnif & Yanıt Asistanı

Microsoft Teams görünümlü arayüzüyle **birden fazla mail hesabına** (Gmail, Outlook / Microsoft 365, Yahoo, Yandex veya şirket IMAP sunucusu) bağlanır ve:

1. **Tasnif eder** — Gelen mailleri Claude ile kategorilere ayırır (Önemli, İş, Kişisel, Fatura/Finans, Bülten, Tanıtım/Reklam, Spam, Diğer) ve öncelik atar. Modern posta deneyimi: okundu/okunmadı takibi, yıldızlama, erteleme (snooze), görünüm sekmeleri (Gelen · Yıldızlı · Yanıt Bekleyen · Ertelenen · Arşiv), sıfırdan mail yazma (✎ Yeni, "✨ AI ile Yaz" destekli, CC'li), klavye kısayolları (j/k gezin, e arşivle, s yıldızla, r yanıtla, c yeni mail) ve 5 dakikada bir otomatik eşitleme.
2. **Okur ve özetler** — Her mail için 1-3 cümlelik Türkçe özet çıkarır.
3. **Yanıt önerir** — Yanıt gerektiren mailler için gönderilmeye hazır taslak yazar. Taslağı düzenleyebilir, "Yeniden Öner" ile talimat verebilir ve **sizin onayınızla** gönderirsiniz. Onaysız hiçbir mail gönderilmez.
4. **Dataroom** — Mail ekleri otomatik saklanır; aynı zamanda tam donanımlı bir sanal veri odası: klasör ağacı ve taşıma, belge önizleme (PDF/görsel), not + etiket + favori, süreli paylaşım linkleri (indirme sayaçlı, iptal edilebilir), belgeyi doğrudan mail atma, toplu ZIP indirme/silme ve tüm işlemlerin kaydedildiği etkinlik günlüğü (audit trail).
5. **Takvim** — Apple iCloud (CalDAV) ve Google Takvim (gizli iCal adresi) entegrasyonlu ay görünümü. Claude, maillerdeki toplantı/randevu/son tarihleri otomatik tespit eder; tek tıkla yerel takvime veya iCloud takviminize eklersiniz.

## Kurulum

```bash
# 1. Bağımlılıkları yükleyin
pip install -r requirements.txt

# 2. Ayar dosyasını oluşturun
cp .env.example .env
# .env dosyasını düzenleyin (aşağıya bakın)

# 3. Başlatın (--reload: kod güncellemelerinde otomatik yeniden başlar)
uvicorn app.main:app --port 8000 --reload
```

> **Güncelleme sonrası:** `git pull` yaptıysanız `pip install -r requirements.txt` çalıştırın ve sunucuyu **yeniden başlatın** — aksi halde arayüz yenilenir ama API eski kalır ve "Method Not Allowed" benzeri hatalar görürsünüz (`--reload` ile başlattıysanız otomatik yenilenir).

Tarayıcıda **http://localhost:8000** adresini açın:

1. **Hesaplar** sekmesinden mail hesaplarınızı ekleyin — sağlayıcı seçin (Gmail, Outlook / Microsoft 365, Yahoo, Yandex) veya "Şirket / Özel" ile kendi IMAP/SMTP sunucunuzu girin. Uygulama kaydetmeden önce bağlantıyı test eder.
2. Sağ üstteki **"⟳ Eşitle"** butonuna tıklayın — tüm hesapların gelen kutuları taranır ve tasnif edilir.
3. Posta sekmesinde hesaba ve kategoriye göre filtreleyebilirsiniz. Yanıtlar, maili alan hesabın kendi SMTP sunucusundan gönderilir.

## `.env` ayarları

| Değişken | Açıklama |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API anahtarı — [platform.claude.com](https://platform.claude.com) (zorunlu) |
| `USER_NAME` | Yanıt taslaklarında imza olarak kullanılacak adınız |
| `SYNC_LIMIT` | Her eşitlemede hesap başına işlenecek en fazla mail sayısı (varsayılan 25) |
| `EMAIL_ADDRESS` vb. | İsteğe bağlı — ilk hesabı arayüz yerine buradan tanımlamak isterseniz |

## Takvim entegrasyonu

Takvim sekmesindeki **"Takvim Kaynakları"** bölümünden bağlanır:

| Kaynak | Nasıl | Yetki |
|---|---|---|
| **Apple iCloud** | Apple ID + **uygulama şifresi** ([appleid.apple.com](https://account.apple.com/account/manage) → Oturum Açma ve Güvenlik → Uygulama Şifreleri). Hesaptaki tüm takvimler bağlanır. | Okuma + **etkinlik ekleme** |
| **Google Takvim** | Google Takvim → Ayarlar → takviminiz → "Takvimi entegre et" → **iCal biçiminde gizli adres**i kopyalayın | Salt okunur |
| **Diğer ICS/webcal** | Outlook yayınlama bağlantısı, şirket takvimi vb. herhangi bir ICS adresi | Salt okunur |

Mailde tespit edilen etkinlikler mail detayındaki **"📅 Takvime Ekle"** kartıyla yerel "Meil" takvimine veya iCloud takvimlerinizden birine yazılır. "⟳ Takvimleri Eşitle" butonu harici kaynaklardan etkinlikleri yeniler (geçmiş 30 gün – gelecek 1 yıl).

### Hesap türlerine göre notlar

- **Gmail / Yahoo / Yandex:** Normal şifre çalışmaz; **uygulama şifresi** gerekir (Gmail: [buradan](https://myaccount.google.com/apppasswords), önce 2 Adımlı Doğrulama açık olmalı).
- **Şirket maili (Microsoft dışı):** IMAP/SMTP sunucu adreslerini ve portları BT ekibinizden öğrenin. IMAP genellikle 993 (SSL), SMTP 465 (SSL) veya 587 (STARTTLS) kullanır.
- **Outlook / Microsoft 365:** Aşağıdaki OAuth kurulumu gerekir — şifreyle giriş artık mümkün değil.

## Microsoft 365 / Outlook hesabı bağlama (OAuth)

Microsoft, **Nisan 2026'da** Exchange Online ve Outlook.com'da IMAP/SMTP için
şifreyle girişi (temel kimlik doğrulama) tamamen kapattı. Şifreniz doğru olsa
bile sunucu artık reddeder; tek yol OAuth 2.0'dır. Meil bunun için "Microsoft
ile giriş" (cihaz kodu) akışını destekler. Tek seferlik kurulum:

1. [portal.azure.com](https://portal.azure.com) → **Microsoft Entra ID** →
   **App registrations** → **New registration**.
2. Ad: `Meil` (herhangi bir şey olabilir). *Supported account types*:
   **"Accounts in any organizational directory and personal Microsoft
   accounts"** seçin. Redirect URI **boş** bırakın → **Register**.
3. Açılan sayfada **Application (client) ID** değerini kopyalayın.
4. Sol menü → **Authentication** → en altta **Advanced settings** →
   **"Allow public client flows"** anahtarını **Yes** yapın → **Save**.
5. Kopyaladığınız ID'yi `.env` dosyanıza yazın: `MS_CLIENT_ID=xxxxxxxx-...`
   ve sunucuyu yeniden başlatın.

Sonra uygulamada **Hesaplar → Sağlayıcı: "Outlook / Microsoft 365 (Microsoft
ile giriş)" → Microsoft ile Bağlan**. Ekranda çıkan kodu
[microsoft.com/devicelogin](https://microsoft.com/devicelogin) adresine girin;
giriş tamamlanınca hesap otomatik eklenir. Şifreniz hiçbir yerde saklanmaz —
yalnızca Microsoft'un verdiği (şifrelenmiş) erişim jetonu tutulur.

> **Şirket hesabı notu:** Kuruluşunuz "kullanıcı onayı"nı kapattıysa ilk
> girişte "admin approval required" görebilirsiniz — BT yöneticinizin bir
> kez onay vermesi yeterli. Ayrıca kiracıda IMAP erişimi ve "Authenticated
> SMTP" açık olmalıdır (uygulama kapalıysa anlaşılır bir hata gösterir).

## Nasıl çalışır?

```
Gmail (IMAP) ──► Mail çekilir ──► Ekler dataroom'a kaydedilir
                                   │
                                   ▼
                        Claude tasnif eder:
                        kategori + öncelik + özet + yanıt taslağı
                                   │
                                   ▼
                        Web arayüzünde incelersiniz
                                   │
                        "Onayla ve Gönder" ──► Gmail (SMTP)
```

- Mailler yalnızca **okunur** modda çekilir; gelen kutunuzda hiçbir şey değişmez (okundu işareti dahil).
- Aynı konudaki mailler `References`/`In-Reply-To` başlıklarına göre **konuşma dizisi** olarak gruplanır; listede tek satır görünür, detayda tüm yazışma sıralanır ve AI'ya dizinin tamamı özetletilebilir.
- **"AI'ya Sor"** ile gelen kutunuza soru sorabilirsiniz ("Ayşe'yle fiyat nede kalmıştı?", "bu hafta hangi faturalar geldi?"): ilgili mailler tam metin aramayla bulunur, yanıt yalnızca bu maillere dayanır ve kaynak mailler tıklanabilir bağlantı olarak gösterilir.
- Dataroom'da **içerik araması** vardır: PDF, Word, Excel, PowerPoint ve metin dosyalarından metin çıkarılır (pypdf + Office XML); arama kutusu dosya adına ek olarak belge içeriğinde de arar ve eşleşen parçayı vurgular. "AI Tara" butonu belgeleri sınıflandırır (fatura, sözleşme, dekont...), özet ve etiket üretir; faturalardan tutar ile son ödeme tarihini çıkarır.
- Yanıtlar yalnızca sizin onayınızla, sizin hesabınızdan `Re:` konusuyla ve doğru konu dizisi (thread) referansıyla gönderilir.
- Tüm veriler yerel `data/` klasöründe tutulur (SQLite + dosyalar).

## Güvenlik notları

- Hesap ve takvim şifreleri veritabanında **şifreli** (Fernet/AES) saklanır; düz metin tutulmaz. Eski kayıtlar ilk açılışta otomatik şifrelenir.
- Şifreleme anahtarı öncelikle `MEIL_SECRET_KEY` ortam değişkeninden okunur; tanımlı değilse `data/secret.key` otomatik üretilir. Anahtarı `.env`'e taşımanız önerilir — böylece `meil.db` dosyası tek başına sızsa bile şifreler çözülemez. **Anahtarı kaybederseniz** kayıtlı şifreler geri getirilemez; hesapları arayüzden yeniden eklemeniz gerekir.
- `.env` dosyası `.gitignore`'dadır — şifrelerinizi asla commit etmeyin.
- Uygulama şifresini istediğiniz an Google hesabınızdan iptal edebilirsiniz.
- Mail içerikleri tasnif için Anthropic API'ye gönderilir.
