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
SITE, URL = cfg["site_name"], cfg["base_url"].rstrip("/")
UPDATED = datetime.fromisoformat(raw["updated"]).strftime("%B %-d, %Y")
PRICE_NOTE = raw.get("price_note", "Prices are list prices and change often.")

products = raw["products"]
for p in products:
    p["price_per_wh"] = p["price"] / p["watt_hours"]
    p["full"] = f'{p["brand"]} {p["name"]}'
MAX_WH = max(p["watt_hours"] for p in products)
has_sample = any(p.get("sample") for p in products)

# typical average draw in watts
DEVICES = [("Wi-Fi router", 10, True), ("LED lights", 20, True), ("Laptop", 60, True), ("Mini fridge", 60, False),
           ("TV", 100, False), ("Power drill", 600, False), ("Kettle", 1500, False)]
DEFAULT_W = 60
EFF = 0.85  # rough inverter and conversion losses

e = html.escape
money = lambda x: f"${x:,.0f}"
cents = lambda x: f"${x:,.2f}"
pages = []


def hours(p, w, dc=False):
    if not p.get("ac", True) and not dc:
        return None  # needs an AC outlet this station doesn't have
    return p["watt_hours"] * EFF / w if w <= p["output_watts"] else None


def fmt_h(h):
    if h is None: return "Can't run"
    if h < 1: return f"{round(h * 60)} min"
    if h < 20: return f"{h:.1f} hr"
    return f"{round(h)} hr"


def buy(p, label="Check price"):
    return f'<a class="btn" href="{e(p["url"])}" rel="sponsored nofollow noopener" target="_blank">{label}</a>'


LOGO = ('<svg class="mark" viewBox="0 0 28 28" aria-hidden="true"><rect x="2" y="6" width="21" height="16" rx="4" '
        'fill="currentColor"/><rect x="24" y="11" width="3" height="6" rx="1.5" fill="currentColor"/>'
        '<path d="M13.5 8.5 9.5 15h3.6l-1 4.5 4.4-6.6h-3.6z" fill="var(--bolt)"/></svg>')


def write(path, title, description, body):
    d = OUT / path.strip("/")
    d.mkdir(parents=True, exist_ok=True)
    nav = "".join(f'<a href="/best/{c["slug"]}/">{e(c["short"])}</a>' for c in collections)
    nav += '<a href="/how-we-rank/">How we rank</a>'
    canon = f"{URL}/{path.strip('/')}/" if path.strip("/") else f"{URL}/"
    (d / "index.html").write_text(BASE.substitute(
        title=e(title), description=e(description), canonical=canon, site_name=e(SITE),
        logo=LOGO, nav=nav, body=body, updated=UPDATED, price_note=''))
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
    return sorted(items, key=lambda p: p[key.lstrip("-")], reverse=key.startswith("-"))


def table(items):
    rows = ""
    for p in items:
        pct = p["watt_hours"] / MAX_WH * 100
        rows += (f'<tr><td><a class="model" href="/p/{p["id"]}/">{e(p["full"])}</a></td>'
                 f'<td><span class="cap"><span class="meter sm"><span style="width:{pct:.0f}%"></span></span>'
                 f'<b>{p["watt_hours"]:,.0f}</b> Wh</span></td>'
                 f'<td class="num">{p["output_watts"]:,.0f} W</td><td class="num">{p["weight_lbs"]:g} lb</td>'
                 f'<td class="num">{money(p["price"])}</td><td class="num">{cents(p["price_per_wh"])}</td>'
                 f'<td>{buy(p)}</td></tr>')
    return ('<div class="scroll"><table><thead><tr><th>Model</th><th>Capacity</th><th class="num">Output</th>'
            '<th class="num">Weight</th><th class="num">List price</th><th class="num">Per Wh</th><th></th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div><p class="note">{e(PRICE_NOTE)}</p>')


SHOW = 8


def runtime_rows(w, dc=False):
    ranked = sorted(products, key=lambda p: -(hours(p, w, dc) or -1))
    top = max((hours(p, w, dc) or 0) for p in products) or 1
    out = ""
    for i, p in enumerate(ranked):
        h = hours(p, w, dc)
        pct = (h / top * 100) if h else 0
        out += (f'<li id="r-{p["id"]}" class="row{"" if h else " off"}"{" hidden" if i >= SHOW else ""}><a class="name" href="/p/{p["id"]}/">{e(p["full"])}</a>'
                f'<span class="meter" role="img" aria-label="{fmt_h(h)}"><span style="width:{pct:.0f}%"></span></span>'
                f'<b class="hrs">{fmt_h(h)}</b><span class="price">{money(p["price"])}</span>{buy(p, "See it")}</li>')
    return out


# ---- collections (skip any with fewer than 2 products: thin pages don't rank)
collections = []
for c in cfg["collections"]:
    items = sort_items(apply_filters(products, c["filters"]), c["sort"])
    if len(items) < 2:
        print(f"skip collection {c['slug']}: only {len(items)} product(s)")
        continue
    c["items"] = items
    collections.append(c)

if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir()
shutil.copytree(ROOT / "static", OUT, dirs_exist_ok=True)

flag = ('<p class="flag">Sample data. Replace data/products.json before publishing.</p>' if has_sample else "")

# ---- home
chips = "".join(
    f'<button type="button" class="chip" data-w="{w}" data-dc="{int(dc)}" aria-pressed="{"true" if n == "Laptop" else "false"}">'
    f'{n}<small>{w:,} W</small></button>' for n, w, dc in DEVICES)
data_json = json.dumps([{"id": p["id"], "name": p["full"], "wh": p["watt_hours"], "w": p["output_watts"],
                         "price": p["price"], "ac": p.get("ac", True)} for p in products]).replace("</", "<\\/")
JS = """
(function(){
  var data = JSON.parse(document.getElementById('d').textContent), EFF = %EFF%, SHOW = %SHOW%, expanded = false, cur = [%DEF%, true];
  var list = document.getElementById('rows'), chips = document.querySelectorAll('.chip'), custom = document.getElementById('custom');
  var more = document.getElementById('more');
  function fmt(h){ if(h===null) return "Can't run"; if(h<1) return Math.round(h*60)+' min'; if(h<20) return h.toFixed(1)+' hr'; return Math.round(h)+' hr'; }
  function render(w, dc){
    cur = [w, dc];
    var rows = data.map(function(p){ return {p:p, h: ((p.ac||dc) && w<=p.w) ? p.wh*EFF/w : null}; });
    rows.sort(function(a,b){ return (b.h||-1)-(a.h||-1); });
    var top = Math.max.apply(null, rows.map(function(r){return r.h||0;})) || 1;
    rows.forEach(function(r, i){
      var li = document.getElementById('r-'+r.p.id);
      li.classList.toggle('off', r.h===null);
      li.querySelector('.meter span').style.width = (r.h? r.h/top*100 : 0)+'%';
      li.querySelector('.meter').setAttribute('aria-label', fmt(r.h));
      li.querySelector('.hrs').textContent = fmt(r.h);
      li.hidden = !expanded && i >= SHOW;
      list.appendChild(li);
    });
  }
  chips.forEach(function(c){ c.addEventListener('click', function(){
    chips.forEach(function(x){ x.setAttribute('aria-pressed','false'); });
    c.setAttribute('aria-pressed','true'); custom.value=''; render(+c.dataset.w, c.dataset.dc==='1'); }); });
  custom.addEventListener('input', function(){
    var w = +custom.value; if(!(w>0)) return;
    chips.forEach(function(x){ x.setAttribute('aria-pressed','false'); }); render(w, false); });
  if(more){ more.addEventListener('click', function(){
    expanded = !expanded; more.textContent = expanded ? 'Show fewer' : 'Show all '+data.length+' models';
    more.setAttribute('aria-expanded', expanded); render(cur[0], cur[1]); }); }
})();
""".replace("%EFF%", str(EFF)).replace("%SHOW%", str(SHOW)).replace("%DEF%", str(DEFAULT_W))

rows_html = runtime_rows(DEFAULT_W, True)
tiles = "".join(f'<li><a href="/best/{c["slug"]}/"><b>{e(c["short"])}</b><span>{e(c["title"])}</span></a></li>'
                for c in collections)
write("", f"{SITE}: {cfg['tagline']}", cfg["description"],
      f'{flag}<section class="hero"><h1>{e(cfg["tagline"])}</h1>'
      f'<p class="lede">Pick something you would plug in. Every model below is ranked by how long it keeps it running.</p>'
      f'<div class="chips" role="group" aria-label="Device">{chips}'
      f'<label class="own">Your own<input id="custom" type="number" min="1" max="3000" inputmode="numeric" placeholder="watts"></label></div>'
      f'<ol class="rows" id="rows">{rows_html}</ol>'
      f'<p><button type="button" class="more" id="more" aria-expanded="false">Show all {len(products)} models</button></p>'
      f'<p class="note">Estimates assume about {round((1 - EFF) * 100)}% conversion loss and steady draw. Real runtime varies with the device.</p></section>'
      f'<h2>Or start from your situation</h2><ul class="tiles">{tiles}</ul>'
      f'<h2>All {len(products)} models</h2>{table(sort_items(products, "price_per_wh"))}'
      f'<script type="application/json" id="d">{data_json}</script><script>{JS}</script>')

# ---- collections
for c in collections:
    top = c["items"][0]
    label = {"price_per_wh": "lowest cost per watt-hour", "-watt_hours": "largest capacity"}.get(c["sort"], "top of the list")
    write(f"best/{c['slug']}", f"{c['title']} ({datetime.now().year})", c["intro"][:155],
          f'{flag}<h1>{e(c["title"])}</h1><p class="lede">{e(c["intro"])}</p>'
          f'<div class="pick"><span class="tag">Top of this list</span><h2>{e(top["full"])}</h2>'
          f'<p>{e(top["tagline"])} {money(top["price"])} list for {top["watt_hours"]:,.0f} Wh '
          f'({cents(top["price_per_wh"])} per Wh), {label} here.</p>'
          f'<p><a class="btn" href="/p/{top["id"]}/">Read the full specs</a> {buy(top, "Check price")}</p></div>'
          f'<h2>Every match</h2>{table(c["items"])}')

# ---- products
for p in products:
    specs = [("Capacity", f'{p["watt_hours"]:,.0f} Wh'), ("Continuous output", f'{p["output_watts"]:,.0f} W'),
             ("Weight", f'{p["weight_lbs"]:g} lb'), ("Battery", f'{p["chemistry"]}, {p["cycles"]:,} cycles'),
             ("Wall recharge", p.get("ac_charge")),
             ("Max solar input", f'{p["solar_input_watts"]:,} W' if p.get("solar_input_watts") else None),
             ("List price", money(p["price"])), ("List price per Wh", cents(p["price_per_wh"]))]
    spec_html = "".join(f"<tr><th>{e(k)}</th><td>{e(v)}</td></tr>" for k, v in specs if v)
    run = "".join(f'<tr><th>{n} <small>{w:,} W</small></th><td class="num">{fmt_h(hours(p, w, dc))}</td></tr>' for n, w, dc in DEVICES)
    pc = "".join(f"<li>{e(x)}</li>" for x in p["pros"])
    cn = "".join(f"<li>{e(x)}</li>" for x in p["cons"])
    others = sorted((q for q in products if q["id"] != p["id"]), key=lambda q: abs(q["watt_hours"] - p["watt_hours"]))[:4]
    rel = "".join(f'<li><a href="/p/{q["id"]}/">{e(q["full"])}</a> '
                  f'<span>{q["watt_hours"]:,.0f} Wh, {money(q["price"])}</span></li>' for q in others)
    pct = p["watt_hours"] / MAX_WH * 100
    write(f"p/{p['id']}", f"{p['full']}: specs, runtime and price",
          f'{p["full"]} stores {p["watt_hours"]:,.0f} Wh and outputs {p["output_watts"]:,.0f} W. List price {money(p["price"])}.',
          f'{flag}<h1>{e(p["full"])}</h1><p class="lede">{e(p["tagline"])}</p>'
          f'<div class="facts"><div><b>{p["watt_hours"]:,.0f}</b><span>Wh</span></div>'
          f'<div><b>{p["output_watts"]:,.0f}</b><span>watts out</span></div>'
          f'<div><b>{p["weight_lbs"]:g}</b><span>pounds</span></div>'
          f'<div><b>{money(p["price"])}</b><span>list price</span></div></div>'
          f'<span class="meter" role="img" aria-label="{pct:.0f}% of the largest battery here"><span style="width:{pct:.0f}%"></span></span>'
          f'<p class="note">Battery size compared with the biggest model on this site.</p>'
          f'<p>{buy(p, "Check current price")}</p>'
          f'<div class="split"><div><h2>What we like</h2><ul class="pc yes">{pc}</ul></div>'
          f'<div><h2>What to know</h2><ul class="pc no">{cn}</ul></div></div>'
          f'<h2>How long it runs things</h2><div class="scroll small"><table><tbody>{run}</tbody></table></div>'
          f'<p class="note">Estimates assume about {round((1 - EFF) * 100)}% conversion loss and steady draw. "Can\'t run" means the device draws more than the {p["output_watts"]:,.0f} W output or needs an AC outlet this model lacks.</p>'
          f'<h2>Specs</h2><div class="scroll small"><table><tbody>{spec_html}</tbody></table></div>'
          f'<h2>Compare with</h2><ul class="links">{rel}</ul>')

# ---- how we rank + disclosure
write("how-we-rank", f"How we rank power stations | {SITE}", "How Wattwise sorts and compares portable power stations.",
      f'<h1>How we rank</h1><p class="lede">Everything here is sorted by numbers you can check, not by who pays us.</p>'
      f'<h2>What the numbers mean</h2><p><b>Runtime</b> is capacity in watt-hours, minus about {round((1 - EFF) * 100)}% for conversion losses, '
      f'divided by the device\'s draw in watts. A station can only run a device if its output rating covers the draw.</p>'
      f'<p><b>Per Wh</b> is list price divided by capacity. Lower means more stored energy per dollar.</p>'
      f'<p><b>List price</b> is the manufacturer or reseller list price when we checked. Sale prices are common, so use the Check price button for today\'s number.</p>'
      f'<h2>Where specs come from</h2><p>Capacity, output, weight and cycle ratings come from manufacturer and retailer spec sheets. '
      f'We have not lab-tested these units, and we say so rather than imply otherwise.</p>'
      f'<p>Prices and specs last checked {UPDATED}. Spot a mistake? Tell us and we will fix it.</p>')

write("disclosure", f"Affiliate disclosure | {SITE}", "How this site earns money.",
      f'<h1>Affiliate disclosure</h1><p>{e(SITE)} is supported by affiliate commissions. When you click a link to a seller '
      f'and buy, we may earn a commission at no extra cost to you.</p>'
      f'<p>Rankings are sorted by the numbers shown (capacity, runtime, weight, price per watt-hour), never by commission rate.</p>')

(OUT / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    + "".join(f"<url><loc>{URL}{u}</loc></url>\n" for u in pages) + "</urlset>\n")
(OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {URL}/sitemap.xml\n")
print(f"built {len(pages)} pages -> {OUT}")
