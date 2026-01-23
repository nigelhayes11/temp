import json

INPUT = "watchfty.json"
OUTPUT = "watchfty.m3u"

with open(INPUT, "r", encoding="utf-8") as f:
    data = json.load(f)

lines = ["#EXTM3U"]

for name, item in data.items():
    url = item.get("url")
    if not url:
        continue

    group = item.get("group", "LIVE")
    logo = item.get("logo", "")

    lines.append(
        f'#EXTINF:-1 group-title="{group}" tvg-logo="{logo}",{name}'
    )
    lines.append(url)

with open(OUTPUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print("M3U hazır")
