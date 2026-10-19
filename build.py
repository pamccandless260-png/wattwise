#!/usr/bin/env python3
"""Build the static site from data/products.json into dist/. Standard library only."""
import html, json, shutil
from datetime import datetime
from pathlib import Path
from string import Template

ROOT = Path(__file__).parent
OUT = ROOT / "dist"
cfg = json.loads((ROOT / "config.json").read_text())
raw = json.loads((ROOT / "data" / "products.json").read_text())
BASE = Template((ROOT / "templates" / "base.html").read_text())
SITE = cfg["site_name"]
URL = cfg["base_url"].rstrip("/")
UPDATED = datetime.fromisoformat(raw["updated"]).strftime("%B %-d, %Y")

products = raw["products"]
for p in products:
    p["price_per_wh"] = p["price"] / p["watt_hours"]
    p["slug"] = p["id"]
by_id = {p["id"]: p for p in products}
has_sample = any(p.get("sample") for p in products)

e = html.escape
money = lambda x: f"${x:,.0f}"
cents = lambda x: f"${x:,.2f}"
pages = []  # paths for sitemap


def write(path, title, description, body, nav=True):
    d = OUT / path.strip("/")
    d.mkdir(parents=True, exist_ok=True)
    links = "".join(f'<a href="/best/{c["slug"]}/">{e(c["short"])}</a>' for c in collections)
    (d / "index.html").write_text(BASE.substitute(
        title=e(title), description=e(description), canonical=f"{URL}/{path.strip('/')}/".replace("//", "/").replace(":/", "://"),
        site_name=e(SITE), nav=links, body=body, updated=UPDATED))
    pages.append("/" + path.strip("/") + ("/" if path.strip("/") else ""))


def apply_filters(items, f):
    out = []
    for p in items:
        if "max_price" in f and p["price"] > f["max_price"]: continue
        if "min_price" in f and p["price"] < f["min_price"]: continue
        if "min_wh" in f and p["watt_hours"] < f["min_wh"]: continue
        if "max_weight_lbs" in f and p.get("weight_lbs", 0) > f["max_weight_lbs"]: continue
        if "brand" in f and p["brand"].lower() != f["brand"].lower(): continue
        out.append(p)
    return out


def sort_items(items, key):
    rev = key.startswith("-")
    return sorted(items, key=lambda p: p[key.lstrip("-")], reverse=rev)


def table(items):
    rows = "".join(
        f'<tr><td><a href="/p/{p["slug"]}/">{e(p["brand"])} {e(p["name"])}</a></td>'
        f'<td class="num">{p["watt_hours"]:,.0f}</td><td class="num">{p.get("output_watts", 0):,.0f}</td>'
        f'<td class="num">{p.get("weight_lbs", 0):,.0f}</td><td class="num">{money(p["price"])}</td>'
        f'<td class="num">{cents(p["price_per_wh"])}</td>'
        f'<td><a class="btn" href="{e(p["url"])}" rel="sponsored nofollow noopener" target="_blank">Check price</a></td></tr>'
        for p in items)
    return ('<div class="scroll"><table><thead><tr><th>Model</th><th class="num">Capacity (Wh)</th>'
            '<th class="num">Output (W)</th><th class="num">Weight (lb)</th><th class="num">Price</th>'
            '<th class="num">Per Wh</th><th></th></tr></thead><tbody>' + rows + '</tbody></table></div>')


def flag():
    return ('<p class="flag">Sample data. Replace data/products.json (or enable a feed in sources.json) before publishing.</p>'
            if has_sample else "")


# collections: only build pages that have at least 2 products (avoid thin pages)
collections = []
for c in cfg["collections"]:
    items = sort_items(apply_filters(products, c["filters"]), c["sort"])
    if len(items) < 2:
        print(f"skip collection {c['slug']}: only {len(items)} product(s)")
        continue
    c["items"] = items
    c["short"] = c["title"].replace("Best portable power stations ", "").replace("for ", "").capitalize()
    collections.append(c)

if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir()
shutil.copytree(ROOT / "static", OUT, dirs_exist_ok=True)

# home
home_links = "".join(f'<li><a href="/best/{c["slug"]}/">{e(c["title"])}</a></li>' for c in collections)
write("", f"{SITE}: portable power stations compared",
      cfg["tagline"],
      f'{flag()}<h1>{e(cfg["tagline"])}</h1>'
      f'<p class="lede">Every model on one table, with price per watt-hour so capacity and cost are easy to weigh.</p>'
      f'<h2>Shortlists</h2><ul class="links">{home_links}</ul>'
      f'<h2>All models</h2>{table(sort_items(products, "price_per_wh"))}')

# collections
for c in collections:
    top = c["items"][0]
    write(f"best/{c['slug']}", f"{c['title']} ({datetime.now().year})",
          c["intro"][:155],
          f'{flag()}<h1>{e(c["title"])}</h1><p class="lede">{e(c["intro"])}</p>{table(c["items"])}'
          f'<h2>Lowest cost per watt-hour here</h2>'
          f'<p>The {e(top["brand"])} {e(top["name"])} is {money(top["price"])} for {top["watt_hours"]:,.0f} Wh, '
          f'or {cents(top["price_per_wh"])} per Wh.</p>')

# products
for p in products:
    hrs = lambda w: p["watt_hours"] * 0.85 / w  # ~15% conversion loss
    specs = [("Capacity", f'{p["watt_hours"]:,.0f} Wh'), ("Continuous output", f'{p.get("output_watts", 0):,.0f} W'),
             ("Weight", f'{p.get("weight_lbs", 0):,.0f} lb'), ("Battery chemistry", p.get("chemistry", "n/a")),
             ("Max solar input", f'{p.get("solar_input_watts", 0):,.0f} W'), ("Price", money(p["price"])),
             ("Price per Wh", cents(p["price_per_wh"]))]
    spec_html = "".join(f"<tr><th>{e(k)}</th><td>{e(v)}</td></tr>" for k, v in specs)
    related = [q for q in sort_items(products, "price_per_wh") if q["id"] != p["id"]][:3]
    rel = "".join(f'<li><a href="/p/{q["slug"]}/">{e(q["brand"])} {e(q["name"])}</a></li>' for q in related)
    name = f'{p["brand"]} {p["name"]}'
    write(f"p/{p['slug']}", f"{name}: specs and price",
          f'{name} stores {p["watt_hours"]:,.0f} Wh and outputs {p.get("output_watts", 0):,.0f} W for {money(p["price"])}.',
          f'{flag()}<h1>{e(name)}</h1>'
          f'<p class="lede">{p["watt_hours"]:,.0f} Wh, {p.get("output_watts", 0):,.0f} W output, {money(p["price"])}.</p>'
          f'<p><a class="btn" href="{e(p["url"])}" rel="sponsored nofollow noopener" target="_blank">Check current price</a></p>'
          f'<h2>Specs</h2><div class="scroll specs"><table style="min-width:0"><tbody>{spec_html}</tbody></table></div>'
          f'<h2>What it can run</h2><p>At typical conversion losses, expect roughly {hrs(60):.0f} hours for a 60 W laptop '
          f'or {hrs(100):.0f} hours for a 100 W TV. Heavier loads shorten that quickly, and anything above '
          f'{p.get("output_watts", 0):,.0f} W will trip the inverter.</p>'
          f'<h2>Compare with</h2><ul class="links">{rel}</ul>')

# disclosure
write("disclosure", f"Affiliate disclosure | {SITE}", "How this site earns money.",
      f'<h1>Affiliate disclosure</h1><p>{e(SITE)} is supported by affiliate commissions. When you click a link to a seller '
      f'and make a purchase, we may earn a commission at no extra cost to you. Rankings and tables are sorted by the '
      f'numbers shown (price, capacity, weight), not by commission rate.</p>'
      f'<p>Prices and specs come from seller feeds and are refreshed automatically, so they can lag behind the seller\'s '
      f'site. Check the final price before you buy.</p>')

# sitemap + robots
(OUT / "sitemap.xml").write_text(
    '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    + "".join(f"<url><loc>{URL}{u}</loc></url>\n" for u in pages) + "</urlset>\n")
(OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {URL}/sitemap.xml\n")
print(f"built {len(pages)} pages -> {OUT}")
