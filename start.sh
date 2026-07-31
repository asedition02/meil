#!/usr/bin/env bash
# Meil'i günceller ve (yeniden) başlatır.
# Kullanım:  ./start.sh          → .env içindeki PORT (yoksa 8000)
#            ./start.sh 8080     → verilen port, .env değerini ezer
set -e
cd "$(dirname "$0")"

# Worktree'ye özel PORT dahil ortam ayarlarını yükle.
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

PORT="${1:-${PORT:-8000}}"

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
