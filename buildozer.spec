[app]
title = Futbol Arena
package.name = futbolarena
package.domain = org.futbolarena
source.dir = .
source.include_exts = py,png,jpg,jpeg,webp,json,wav,ogg,mp3
source.include_patterns = assets/*,assets/*/*
source.exclude_dirs = .github,bin,__pycache__,.git
version = 1.0.0

# Saf Python + Kivy. certifi/openssl: fotoğrafları internetten indirmek için.
requirements = python3==3.11.5,hostpython3==3.11.5,kivy==2.3.0,certifi,openssl

orientation = landscape
fullscreen = 1

android.permissions = INTERNET
android.api = 33
android.minapi = 24
android.archs = arm64-v8a
android.accept_sdk_license = True
android.allow_backup = True

# Python 3.14'e geçilmesini engellemek için python-for-android sürümü sabit
p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 1
