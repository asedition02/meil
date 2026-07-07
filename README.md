# 📬 Meil — E-posta Tasnif & Yanıt Asistanı

Microsoft Teams görünümlü arayüzüyle **birden fazla mail hesabına** (Gmail, Outlook / Microsoft 365, Yahoo, Yandex veya şirket IMAP sunucusu) bağlanır ve:

1. **Tasnif eder** — Gelen mailleri Claude ile kategorilere ayırır (Önemli, İş, Kişisel, Fatura/Finans, Bülten, Tanıtım/Reklam, Spam, Diğer) ve öncelik atar.
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
- **Şirket maili:** IMAP/SMTP sunucu adreslerini ve portları BT ekibinizden öğrenin. IMAP genellikle 993 (SSL), SMTP 465 (SSL) veya 587 (STARTTLS) kullanır.
- **Microsoft 365:** Şirket kiracınızda (tenant) IMAP erişimi kapalıysa BT yöneticinizin açması gerekir.

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
- Yanıtlar yalnızca sizin onayınızla, sizin hesabınızdan `Re:` konusuyla ve doğru konu dizisi (thread) referansıyla gönderilir.
- Tüm veriler yerel `data/` klasöründe tutulur (SQLite + dosyalar).

## Güvenlik notları

- `.env` dosyası `.gitignore`'dadır — şifrelerinizi asla commit etmeyin.
- Uygulama şifresini istediğiniz an Google hesabınızdan iptal edebilirsiniz.
- Mail içerikleri tasnif için Anthropic API'ye gönderilir.
