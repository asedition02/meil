#!/bin/bash
# test_production.sh — Üretim ortamı ön kontrolü

set -e

echo "🔍 Meil Üretim Ön Kontrolü"
echo "==========================================="

# 1. Python ve bağımlılıklar
echo "✓ Python sürümü:"
python3 --version

echo "✓ Gerekli paketler:"
python3 -c "import fastapi, uvicorn, cryptography, anthropic, pypdf; print('  FastAPI, uvicorn, cryptography, anthropic, pypdf — OK')"

# 2. Veritabanı başlatma
echo "✓ Veritabanı işlemi test:"
python3 -c "from app import database; database.init_db(); print('  Veritabanı başlatıldı — OK')"

# 3. Ortam değişkenleri
echo "✓ Zorunlu ortam değişkenleri:"
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "  ⚠️  ANTHROPIC_API_KEY tanımlanmadı (isteğe bağlı — ilk başlangıçta sorun yok)"
else
    echo "  ANTHROPIC_API_KEY — OK"
fi

echo "✓ Üretim ayarları:"
if [ -z "$PRODUCTION" ]; then
    echo "  PRODUCTION tanımlanmadı (yerel geliştirme modunda)"
else
    echo "  PRODUCTION=$PRODUCTION"
fi

# 4. Dosya izinleri
echo "✓ Dosya izinleri:"
if [ ! -d "data" ]; then
    mkdir -p data
fi
ls -ld data/ || echo "  ⚠️  data/ klasörü yazılamıyor"

# 5. FastAPI başlatma (10 saniye test)
echo "✓ API başlama testi (10sn):"
timeout 10 python3 -m uvicorn app.main:app --port 8001 2>&1 | head -5 &
sleep 3
if curl -s http://localhost:8001/api/status >/dev/null 2>&1; then
    echo "  http://localhost:8001/api/status — OK"
else
    echo "  ⚠️  API yanıt vermedi"
fi

pkill -f "uvicorn.*8001" || true
sleep 1

echo ""
echo "✅ Ön kontrol tamamlandı!"
echo ""
echo "Adım 2: VPS'ye dağıtım için docs/PHASE2_DEPLOYMENT.md'ye bakın."
