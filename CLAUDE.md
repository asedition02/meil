# Claude Code talimatları

Önce kökteki `AGENTS.md` dosyasını oku ve tüm kurallarına uy.

- Bu worktree'nin branch'ini doğrulamadan değişiklik yapma.
- `main` branch'ine geçme, commit atma veya push yapma.
- Yalnızca verilen görevin kapsamındaki dosyaları değiştir.
- Kullanıcının commit edilmemiş değişikliklerine dokunma.
- Uygulama davranışını değiştiren her işte test ekle/güncelle ve teslimden önce `python3 -m pytest` çalıştır.
- `.env`, `data/`, `*.db`, loglar, erişim anahtarları ve gerçek kullanıcı verilerini commit etme.
- Çalışma sonunda değişen dosyaları, çalıştırılan testleri ve kalan riskleri kısa biçimde raporla.
