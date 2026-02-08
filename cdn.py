import requests
import sys
from datetime import datetime, timezone


API_URL = "https://api.cdn-live.tv/api/v1/events/sports"
OUTPUT_M3U = "cdn.m3u"
GROUP_TITLE = "CDN Spor"


def main():
    try:
        print("📡 CDN Live event listesi alınıyor...")

        r = requests.get(
            API_URL,
            params={"user": "cdnlivetv", "plan": "free"},
            timeout=10,
        )

        data = r.json().get("cdn-live-tv")

        if not data:
            print("⚠️ Event verisi boş")
            create_empty_m3u()
            return 0

        now = datetime.now(timezone.utc)

        lines = ["#EXTM3U"]
        count = 0

        for sport, events in data.items():
            if not isinstance(events, list):
                continue

            for ev in events:
                try:
                    start = datetime.fromisoformat(
                        ev["start"].replace("Z", "+00:00")
                    )

                    # canlıya yakın eventler
                    if abs((start - now).total_seconds()) > 3600:
                        continue

                    channels = ev.get("channels")
                    if not channels:
                        continue

                    name = f'{ev["awayTeam"]} vs {ev["homeTeam"]}'
                    stream_url = channels[0]["url"]

                    lines.append(
                        f'#EXTINF:-1 group-title="{GROUP_TITLE}",{name}'
                    )
                    lines.append(stream_url)

                    count += 1

                except Exception:
                    continue

        if count == 0:
            print("⚠️ Aktif yayın bulunamadı")
            create_empty_m3u()
            return 0

        with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        print(f"✅ cdn.m3u oluşturuldu ({count} canlı yayın)")
        return 0

    except Exception as e:
        print(f"❌ Hata: {e}")
        create_empty_m3u()
        return 0


def create_empty_m3u():
    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write("# Şu anda aktif yayın bulun
