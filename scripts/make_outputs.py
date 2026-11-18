"""Build the summary tables, the GeoJSON, the cover and the charts (Natural Earth outlines, public domain, are downloaded once into ../../_raw) from data/montessori_schools_official_registries.csv.

Usage: python scripts/make_outputs.py
Needs pandas, numpy, matplotlib and Pillow.
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import msf_style as S

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA, IMG, RAW = ROOT / "data", ROOT / "images", ROOT.parent / "_raw"
IMG.mkdir(exist_ok=True)

df = pd.read_csv(DATA / "montessori_schools_official_registries.csv", dtype=str).fillna("")
N = len(df)

# ---------- summary tables ----------
def pub(s):
    return "Public" if s == "Public" else ("Private" if s.startswith("Private") else "Other or not stated")

df["_pub"] = df["public_or_private"].map(pub)
by_country = (df.groupby(["country", "country_code", "registry"])
              .agg(schools=("official_id", "count"),
                   cities=("city", lambda s: s[s != ""].nunique()),
                   regions=("region", "nunique"),
                   with_coordinates=("latitude", lambda s: int((s != "").sum())),
                   public=("_pub", lambda s: int((s == "Public").sum())),
                   private=("_pub", lambda s: int((s == "Private").sum())),
                   other_or_not_stated=("_pub", lambda s: int((s == "Other or not stated").sum())),
                   with_msf_city_page=("msf_city_url", lambda s: int((s != "").sum())))
              .reset_index().sort_values("schools", ascending=False))
by_country["share_of_dataset_pct"] = (by_country["schools"] / N * 100).round(1)
by_region = (df.groupby(["country", "region"]).agg(schools=("official_id", "count"),
                                                    cities=("city", lambda s: s[s != ""].nunique()))
             .reset_index().sort_values(["country", "schools", "region"], ascending=[True, False, True]))
by_type = (df.groupby(["country", "type_phase", "public_or_private"]).size().rename("schools").reset_index()
           .sort_values(["country", "schools"], ascending=[True, False]))
by_city = (df[df.city != ""].groupby(["country", "region", "city"]).size().rename("schools").reset_index()
           .sort_values(["schools", "country", "city"], ascending=[False, True, True]))
by_country.to_csv(DATA / "by_country.csv", index=False)
by_region.to_csv(DATA / "by_region.csv", index=False)
by_type.to_csv(DATA / "by_type.csv", index=False)
by_city.to_csv(DATA / "by_city.csv", index=False)

# checks: every summary adds up to the main file
assert by_country.schools.sum() == N == by_region.schools.sum() == by_type.schools.sum()
assert by_city.schools.sum() == int((df.city != "").sum())
assert (by_country.public + by_country.private + by_country.other_or_not_stated == by_country.schools).all()

# ---------- GeoJSON (records that carry coordinates in their registry) ----------
g = df[df.latitude != ""]
feats = [{"type": "Feature",
          "geometry": {"type": "Point", "coordinates": [float(r.longitude), float(r.latitude)]},
          "properties": {"country": r.country, "official_id": r.official_id, "name": r["name"], "city": r.city,
                         "region": r.region, "public_or_private": r.public_or_private}}
         for _, r in g.iterrows()]
(DATA / "montessori_schools_with_coordinates.geojson").write_text(
    json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False), encoding="utf-8")

# ---------- images ----------
fr_n = int((df.country == "France").sum())
nl_n = int((df.country == "Netherlands").sum())
uk_n = int(df.country.isin(["England", "Wales"]).sum())
SRC = "Sources: Annuaire de l'éducation, GIAS, DUO Open Onderwijsdata. Downloaded 2026-11-17."
CCOL = {"France": S.BLUE, "Netherlands": S.AMBER, "England": S.CORAL, "Wales": S.VIOLET}

S.cover(IMG / "cover.png", HERE / "cover_photo.jpg", "Montessori Schools in\nOfficial School Registries",
        "Open dataset  ·  CC BY 4.0", f"{N}", "open schools with Montessori\nin their official name",
        [f"{fr_n} France", f"{nl_n} Netherlands", f"{uk_n} England and Wales"],
        "Photo: Anil Sharma, Pexels", accent=S.AMBER, focus=(0.5, 0.45))

# key numbers
idf = int(by_region[(by_region.country == "France") & (by_region.region == "Ile-de-France")].schools.iloc[0])
ams = int(by_city[by_city.city == "Amsterdam"].schools.iloc[0])
S.key_numbers(IMG / "key_numbers.png", "Official Registries in Six Numbers",
              "Open schools with Montessori in the official name, in the school lists of three governments.", SRC, [
                  (f"{N}", "open schools in the file", S.AMBER),
                  (f"{fr_n}", "in France, from 68,555 establishments", S.BLUE),
                  (f"{nl_n}", "in the Netherlands, from 7,720 locations", S.TEAL),
                  (f"{uk_n}", "in England and Wales, from about 27,200", S.CORAL),
                  (f"{idf}", "in Ile-de-France, the biggest French region", S.VIOLET),
                  (f"{ams}", "in Amsterdam, the biggest city overall", S.GREEN),
              ], accent=S.AMBER)

# France dot map
world = S.natural_earth(RAW, "ne_50m_admin_0_countries.geojson")
fr = df[(df.country == "France") & (df.latitude != "")].copy()
fr["la"], fr["lo"] = fr.latitude.astype(float), fr.longitude.astype(float)
LON, LAT = (-5.6, 10.2), (41.0, 51.6)
main = fr[(fr.la > LAT[0]) & (fr.la < LAT[1]) & (fr.lo > LON[0]) & (fr.lo < LON[1])]
k = np.cos(np.radians(46.3))
p = S.Page("Where the French Registry Places Them",
           f"{len(main)} of the {len(fr)} French records with coordinates fall in mainland France. One dot per school.",
           SRC, accent=S.AMBER, size=(1400, 1000))
ax = p.axes(66, p.top - 6, 720, p.bottom - p.top)
for f in world["features"]:
    for poly in S.polygons(f):
        c = f["properties"]["NAME"] == "France"
        ax.fill(poly[:, 0] * k, poly[:, 1], fc=S.mix(S.AMBER, "#ffffff", 0.82) if c else "#dde5ef", ec="white", lw=1.2, zorder=1)
ax.scatter(main.lo * k, main.la, s=62, color=S.AMBER, edgecolor="white", linewidth=0.9, alpha=0.9, zorder=3)
ax.set_xlim(LON[0] * k, LON[1] * k); ax.set_ylim(*LAT); ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
ax.set_facecolor("#eaf2fb"); ax.patch.set_alpha(1)
for sp in ax.spines.values(): sp.set_visible(False)
cards = [(f"{len(fr)}", "French records carry registry coordinates", S.AMBER),
         (f"{len(fr) - len(main)}", "overseas records, not drawn on this map", S.VIOLET),
         (f"{idf}", f"schools in Ile-de-France, of {fr_n} in France", S.BLUE)]
for i, (big, lab, col) in enumerate(cards):
    y = p.top + 14 + i * 214
    S.rrect(p.ax, 840, y, 494, 190, r=26, fc=S.mix(col, "#ffffff", 0.92), ec=S.mix(col, "#ffffff", 0.7), lw=1.5, z=2)
    S.rrect(p.ax, 868, y + 28, 46, 8, r=4, fc=col, z=3)
    p.ax.text(868, y + 96, big, fontsize=44, fontweight="bold", color=col, va="center", zorder=3)
    p.ax.text(868, y + 152, lab, fontsize=14.5, va="center", zorder=3)
p.save(IMG / "france_dot_map.png")

# country shares and public or private status
d = by_country.sort_values("schools", ascending=False)
p = S.Page("Who Lists Them, and How They Are Funded",
           f"Left, the {N} schools by country. Right, the public or private status each registry gives.",
           "Dutch schools of special denomination are publicly funded and counted under other. " + SRC, accent=S.CORAL, size=(1400, 860))
a1 = p.axes(70, p.top + 10, 430, 430)
S.donut(a1, list(d.schools), [CCOL[c] for c in d.country], f"{N}", "schools", width=0.36)
for i, (_, r) in enumerate(d.iterrows()):
    x, y = 70 + (i % 2) * 215, p.top + 480 + (i // 2) * 44
    p.ax.scatter([x + 10], [y], s=120, color=CCOL[r.country], zorder=5)
    p.ax.text(x + 28, y, f"{r.country}", fontsize=13, va="center", zorder=5)
    p.ax.text(x + 28 + S.text_w(p.fig, p.ax, f"{r.country}  ", 13), y, f"{r.schools}", fontsize=13, va="center", fontweight="bold", zorder=5)
seg = [("public", S.BLUE, "Public"), ("private", S.GREEN, "Private"), ("other_or_not_stated", "#94a3b8", "Other or not stated")]
x0, bw = 640, 640
lx = x0
for key, col, lab in seg:
    S.rrect(p.ax, lx, p.top + 10, 24, 20, r=5, fc=col, z=5)
    p.ax.text(lx + 34, p.top + 20, lab, fontsize=12.5, va="center", zorder=5)
    lx += 40 + S.text_w(p.fig, p.ax, lab, 12.5) + 24
for i, (_, r) in enumerate(d.iterrows()):
    y = p.top + 90 + i * 100
    p.ax.text(x0, y - 12, r.country, fontsize=14, fontweight="bold", va="center", zorder=5)
    p.ax.text(x0 + bw, y - 12, f"{r.schools} school" + ("" if r.schools == 1 else "s"), fontsize=12.5, color=S.MUTED, ha="right", va="center", zorder=5)
    x = x0
    for key, col, lab in seg:
        w = bw * r[key] / r.schools
        if w <= 0:
            continue
        S.rrect(p.ax, x, y + 6, max(w - 3, 2), 34, r=8, fc=col, z=4)
        if w > 20:
            p.ax.text(x + w / 2, y + 23, f"{int(r[key])}", fontsize=12.5 if w > 44 else 10.5, color="white", fontweight="bold", ha="center", va="center", zorder=5)
        x += w
p.save(IMG / "registry_shares.png")

# top regions
top = by_region.sort_values(["schools", "region"], ascending=[False, True]).head(12)
p = S.Page("The 12 Regions With the Most Montessori-Named Schools",
           "Regions, Government Office Regions and provinces, as each registry publishes them. Colour shows the country.",
           SRC, accent=S.VIOLET, size=(1400, 880))
ax = p.axes(380, p.top - 4, 850, p.bottom - p.top - 6)
S.lollipop(ax, [f"{r}  ({c})" for r, c in zip(top.region, top.country)], list(top.schools), [CCOL[c] for c in top.country], xmax=105, size=260)
ax.set_xticks([])
p.save(IMG / "top_regions.png")
print("outputs done", N)
