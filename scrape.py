"""Build sessions.json from the public AI Summit Barcelona schedule.

Source: https://aisummitbarcelona.com/schedule (JSON-LD event data plus the
rendered session cards for stage, track and type). Run again to refresh.
"""
import html
import json
import re
import urllib.request

URL = "https://aisummitbarcelona.com/schedule"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=60).read().decode("utf-8")


def main():
    page = fetch(URL)

    # 1. JSON-LD: id, title, description, ISO times, speakers.
    ld = None
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', page, re.S):
        data = json.loads(html.unescape(block))
        if isinstance(data, dict) and data.get("@type") == "Event":
            ld = data["subEvent"]
    assert ld, "JSON-LD event list not found; the page layout changed"

    # 2. Rendered cards: stage, track and type live only in the HTML.
    meta = {}
    for m in re.finditer(r'<h3 class="mt-2[^"]*">(.*?)</h3>', page, re.S):
        title = html.unescape(m.group(1)).strip()
        pre = page[max(0, m.start() - 2500):m.start()]
        text = re.sub("<[^>]+>", " ", pre).upper()
        stage = re.findall(r"</svg>([A-Za-z ]+Stage|Workshop Room [AB])</span>", pre)
        track = re.findall(r'text-linen/65">([^<]+)</span>', pre)
        kind = re.findall(r"(KEYNOTE|USE CASE|PANEL|FIRESIDE CHAT|DEBATE|DEMO|WORKSHOP)", text)
        meta.setdefault(title, {
            "stage": stage[-1] if stage else "",
            "track": track[-1] if track else "",
            "type": kind[-1].title() if kind else "",
        })

    # 3. Companies: only the /speakers cards carry them, 25 per page.
    companies = {}
    page_no = 1
    while True:
        cards = re.findall(r'text-cinnabar-600">([^<]+)</p>.*?</div><h3[^>]*>([^<]+)</h3>',
                           fetch(f"{URL.rsplit('/', 1)[0]}/speakers?page={page_no}"), re.S)
        if not cards:
            break
        for company, name in cards:
            companies.setdefault(html.unescape(name).strip(), html.unescape(company).strip())
        page_no += 1

    # 4. Speaker photos (avatar <span title="Name"><img src=...>).
    photos = {}
    for m in re.finditer(r'title="([^"]+)"[^>]*>\s*<img src="([^"]+)"', page):
        photos.setdefault(html.unescape(m.group(1)), m.group(2))

    sessions = []
    for ev in ld:
        title = ev["name"].strip()
        m = meta.get(title, {})
        sessions.append({
            "id": ev["@id"].split("#")[-1][:8],
            "title": title,
            "description": ev.get("description", "").strip(),
            "start": ev["startDate"],
            "end": ev["endDate"],
            "stage": m.get("stage", ""),
            "track": m.get("track", ""),
            "type": m.get("type", ""),
            "speakers": [p["name"] for p in ev.get("performer", [])],
            "url": ev["url"],
        })
    sessions.sort(key=lambda s: (s["start"], s["stage"]))

    missing = [s["title"] for s in sessions if not s["stage"]]
    print(f"{len(sessions)} sessions, {len(missing)} without stage")
    for t in missing[:10]:
        print("  no stage:", t)
    used = {n for s in sessions for n in s["speakers"]}
    print(f"{len(used - set(companies))} speakers without company")
    json.dump({"source": URL, "sessions": sessions,
               "photos": {n: u for n, u in photos.items() if n in used},
               "companies": {n: c for n, c in companies.items() if n in used}}, open("sessions.json", "w"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
