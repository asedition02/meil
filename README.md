# 📬 Meil — E-posta Tasnif & Yanıt Asistanı

Gmail (veya herhangi bir IMAP) hesabınıza bağlanır ve:

1. **Tasnif eder** — Gelen mailleri Claude ile kategorilere ayırır (Önemli, İş, Kişisel, Fatura/Finans, Bülten, Tanıtım/Reklam, Spam, Diğer) ve öncelik atar.
2. **Okur ve özetler** — Her mail için 1-3 cümlelik Türkçe özet çıkarır.
3. **Yanıt önerir** — Yanıt gerektiren mailler için gönderilmeye hazır taslak yazar. Taslağı düzenleyebilir, "Yeniden Öner" ile talimat verebilir ve **sizin onayınızla** gönderirsiniz. Onaysız hiçbir mail gönderilmez.
4. **Ekleri dataroom'a kaydeder** — Tüm ekler `data/dataroom/GÖNDEREN/TARİH/` yapısında saklanır ve arayüzden indirilebilir.

## Kurulum

```bash
# 1. Bağımlılıkları yükleyin
pip install -r requirements.txt

# 2. Ayar dosyasını oluşturun
cp .env.example .env
# .env dosyasını düzenleyin (aşağıya bakın)

# 3. Başlatın
uvicorn app.main:app --port 8000
```

Tarayıcıda **http://localhost:8000** adresini açın ve **"Mailleri Getir"** butonuna tıklayın.

## `.env` ayarları

| Değişken | Açıklama |
|---|---|
| `EMAIL_ADDRESS` | Gmail adresiniz |
| `EMAIL_PASSWORD` | Gmail **uygulama şifresi** — normal şifreniz çalışmaz. [Buradan oluşturun](https://myaccount.google.com/apppasswords) (2 Adımlı Doğrulama açık olmalı) |
| `ANTHROPIC_API_KEY` | Claude API anahtarı — [platform.claude.com](https://platform.claude.com) |
| `USER_NAME` | Yanıt taslaklarında imza olarak kullanılacak adınız |
| `SYNC_LIMIT` | Her eşitlemede işlenecek en fazla mail sayısı (varsayılan 25) |
| `IMAP_HOST` / `SMTP_HOST` | Gmail dışı sağlayıcı için değiştirin |

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
