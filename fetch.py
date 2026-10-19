#!/usr/bin/env python3
"""Refresh data/products.json from the feeds listed in sources.json.

Each source is a CSV or JSON feed URL (kept in an env var / repo secret, since
affiliate feed URLs often embed your ID). Fields are renamed with `map`.
Products are merged by id: feed values overwrite price/specs/url, anything you
add by hand to an existing product (extra fields) is kept. If no source is
enabled or all fail, the file is left untouched.
"""
import csv, io, json, os, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
PRODUCTS = ROOT / "data" / "products.json"
NUMERIC = {"price", "watt_hours", "output_watts", "weight_lbs", "solar_input_watts"}


def download(url):
    req = urllib.request.Request(url, headers={"User-Agent": "wattwise-fetch/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8-sig")


def rows(text, fmt):
    if fmt == "csv":
        return list(csv.DictReader(io.StringIO(text)))
    data = json.loads(text)
    return data["products"] if isinstance(data, dict) else data


def to_num(v):
    try:
        return float(str(v).replace("$", "").replace(",", "").strip())
    except ValueError:
        return None


def convert(row, src):
    out = {"brand": src.get("brand", "")}
    for field, col in src["map"].items():
        v = row.get(col)
        if v in (None, ""):
            continue
        out[field] = to_num(v) if field in NUMERIC else str(v).strip()
    needed = {"id", "name", "price", "watt_hours", "url"}
    if not needed <= out.keys() or None in (out["price"], out["watt_hours"]):
        return None
    out["id"] = out["id"].lower().replace(" ", "-")
    return out


def main():
    cfg = json.loads((ROOT / "sources.json").read_text())
    fetched = []
    for src in cfg["sources"]:
        if not src.get("enabled"):
            continue
        url = os.environ.get(src["url_env"])
        if not url:
            print(f"skip {src['name']}: env {src['url_env']} not set")
            continue
        try:
            items = [convert(r, src) for r in rows(download(url), src["format"])]
            items = [i for i in items if i]
            print(f"{src['name']}: {len(items)} products")
            fetched += items
        except Exception as e:  # keep going; one bad feed shouldn't wipe the site
            print(f"FAILED {src['name']}: {e}", file=sys.stderr)

    if not fetched:
        print("nothing fetched; products.json unchanged")
        return

    current = json.loads(PRODUCTS.read_text())
    by_id = {p["id"]: p for p in current["products"] if not p.get("sample")}
    for item in fetched:
        by_id.setdefault(item["id"], {}).update(item)
    current["products"] = sorted(by_id.values(), key=lambda p: (p["brand"], p["name"]))
    current["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    PRODUCTS.write_text(json.dumps(current, indent=2) + "\n")
    print(f"wrote {len(current['products'])} products")


if __name__ == "__main__":
    main()
