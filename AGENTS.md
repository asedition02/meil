# Meil multi-agent çalışma kuralları

Bu kurallar bu repoda çalışan tüm coding agent'lar için geçerlidir.

## Git güvenliği

- `main` branch'ine doğrudan commit veya push yapma.
- Yalnızca sana atanmış feature/review branch'i ve worktree içinde çalış.
- Başka worktree'lerdeki dosyaları değiştirme.
- Kullanıcıya ait commit edilmemiş değişiklikleri silme, ezme, stash'leme veya taşıma.
- Rebase, force-push, hard reset ve toplu dosya silme işlemlerini açık onay olmadan yapma.

## Kapsam

- Yalnızca atanmış görevle ilgili dosyaları değiştir.
- Tesadüfen fark edilen ilgisiz sorunları düzeltme; bunları sonuç notunda bildir.
- Büyük yeniden adlandırmalar, biçimlendirme turları ve bağımlılık güncellemeleri görev açıkça gerektirmiyorsa yapılmamalıdır.
- Paylaşılan API, veritabanı şeması veya yapılandırma sözleşmesi değişirse bunu sonuç notunda açıkça belirt.

## Doğrulama

- Değişiklik yapmadan önce `git status --short --branch` çalıştır.
- Her davranış değişikliği için uygun testleri ekle veya güncelle.
- Teslimden önce en az `python3 -m pytest` çalıştır.
- Test çalıştırılamazsa nedeni ve denenmiş komutu açıkça bildir.
- Commit yalnızca ilgili değişiklikleri içermeli; `.env`, veritabanı, log, anahtar veya kullanıcı verisi commit edilmemelidir.

## Yerel izolasyon

- Her worktree kendi `.env`, `DATA_DIR`, `DB_PATH` ve `PORT` değerlerini kullanmalıdır.
- Gerçek API anahtarlarını veya hesap bilgilerini örnek dosyalara yazma.
- Yerel veriyi başka bir worktree'nin veri diziniyle paylaşma.
