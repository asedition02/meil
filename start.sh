#!/usr/bin/env bash
# Meil'i günceller ve (yeniden) başlatır.
# Kullanım:  ./start.sh          → güncelle + başlat (port 8000)
#            ./start.sh 8080     → farklı portta başlat
set -e
cd "$(dirname "$0")"

PORT="${1:-8000}"

echo "── Meil başlatılıyor ──"

# 1) Güncellemeleri çek (git deposuysa)
if [ -d .git ]; then
  echo "• Güncellemeler çekiliyor..."
  git pull --ff-only || echo "  (git pull atlandı — yerel değişiklik olabilir)"
fi

# 2) Bağımlılıkları kur
echo "• Bağımlılıklar kontrol ediliyor..."
python3 -m pip install -q -r requirements.txt

# 3) Aynı portta çalışan eski Meil sürecini durdur
if command -v lsof >/dev/null 2>&1; then
  OLD_PID=$(lsof -ti tcp:"$PORT" 2>/dev/null || true)
  if [ -n "$OLD_PID" ]; then
    echo "• Port $PORT üzerindeki eski süreç durduruluyor (PID $OLD_PID)..."
    kill "$OLD_PID" 2>/dev/null || true
    sleep 1
  fi
fi

# 4) Başlat (--reload: kod güncellenince otomatik yeniden yüklenir)
echo "• Sunucu başlıyor → http://localhost:$PORT"
exec python3 -m uvicorn app.main:app --port "$PORT" --reload
