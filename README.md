# Futbol Arena (saf Python + Kivy)

## APK alma (GitHub)
1. Bu klasördeki TÜM dosyaları (`.github` klasörü dahil) yeni bir GitHub deposuna yükle.
2. Depo > Actions > "Build APK" çalışır (ilk derleme ~20-30 dk).
3. Bitince Actions > çalışma > Artifacts > `futbol-arena-apk` içinden APK'yı indir.

## Masaüstünde deneme
    pip install kivy certifi
    python main.py

## Fotoğraflar
Fotoğraf sırası: `assets/players/<slug>.jpg|png` -> önbellek -> Wikipedia'dan indirme.
Dosya adı = isim küçük harf, boşluk `_`, aksansız. Örn: `lionel_messi.jpg`, `kylian_mbappe.jpg`.
İnternet yoksa ve dosya yoksa varsayılan futbolcu görseli gösterilir.

## Kaleci görseli
`assets/goalkeeper/buffon.png` (şeffaf PNG) koyarsan çizim yerine o kullanılır.

## Sesler (isteğe bağlı)
`assets/sounds/` içine correct, wrong, goal, save, buy (.wav/.ogg/.mp3) koy.
