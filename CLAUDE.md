# Deploy

Kullanıcı "deploy edelim" / "sunucuya yükleyelim" dediğinde, aşağıdaki komutu
olduğu gibi göster — tekrar sorup açıklama üretme:

```bash
cd /opt/meil && git pull origin claude/email-triage-assistant-8oikt1 && source venv/bin/activate && pip install -r requirements.txt && systemctl restart meil && sleep 15 && curl -s https://meil.tr/api/status
```
