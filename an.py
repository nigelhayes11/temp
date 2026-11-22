name: Update Live M3U Playlist

on:
  schedule:
    - cron: '*/30 * * * *'
  workflow_dispatch:

permissions:
  contents: write

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Depoyu Çek
        uses: actions/checkout@v4

      - name: Python Kurulumu
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Bağımlılıkları ve Playwright Tarayıcısını Kur
        run: |
          python -m pip install --upgrade pip
          pip install playwright
          playwright install chromium
          playwright install-deps chromium

      - name: Betiği Çalıştır
        run: python an.py

      - name: Güncellenen nba.m3u Dosyasını Repoya Kaydet
        run: |
          if [ -f "nba.m3u" ]; then
            git config --local user.email "github-actions[bot]@://github.com"
            git config --local user.name "github-actions[bot]"
            git add nba.m3u
            if ! git diff --staged --quiet; then
              git commit -m "chore: update nba.m3u playlist"
              git push
            else
              echo "Değişiklik yok, commit atılmadı."
            fi
          fi
