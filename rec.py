name: Update RecTV Live M3U

on:
  schedule:
    - cron: "0 */4 * * *"
  workflow_dispatch:

permissions:
  contents: write

jobs:
  build-rectv-m3u:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install Dependencies
        run: pip install httpx

      - name: Run RecTV Scraper
        run: python -u rectv.py

      - name: Commit and Push M3U
        run: |
          git config --local user.email "github-actions[bot]@://github.com"
          git config --local user.name "github-actions[bot]"
          git add rectv.m3u
          if ! git diff --staged --quiet; then
            git commit -m "chore: update rectv.m3u [skip ci]"
            git pull --rebase origin main
            git push
          else
            echo "rectv.m3u dosyasında değişiklik yok."
          fi
