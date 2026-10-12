# ⚽ Futbolum

Saf Python + Kivy ile yazılmış mobil futbol quiz & penaltı oyunu.

## 📦 APK Alma (GitHub Actions)

1. Bu klasördeki **TÜM dosyaları** yeni bir GitHub deposuna yükle:
   - `.py` dosyaları (8 adet)
   - `logo.png` (ana klasörde)
   - `.github/` klasörü (workflow)
   - `assets/` klasörü (varsa)

2. GitHub → **Actions** sekmesi → **"Build APK"** otomatik çalışır (ilk derleme ~20-30 dk).

3. Bitince **Actions → çalışma → Artifacts → futbolum-apk** içinden APK'yı indir.

## 🖥️ Masaüstünde Deneme

```bash
pip install kivy certifi
python main.py