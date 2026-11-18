"""Build the summary tables, the GeoJSON, the cover and the charts from data/montessori_schools_official_registries.csv.

Usage: python scripts/make_outputs.py
Needs pandas and matplotlib.
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA, IMG = ROOT / "data", ROOT / "images"
IMG.mkdir(exist_ok=True)

INK, BLUE, GREEN, SOFT, MINT, MUTED = "#0f172a", "#2563eb", "#059669", "#f8fafc", "#ecfdf5", "#64748b"
plt.rcParams["font.family"] = ["Segoe UI", "Arial", "DejaVu Sans"]

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
COUNTRY_COLOR = {"France": BLUE, "Netherlands": GREEN, "England": INK, "Wales": MUTED}
fr_n = int((df.country == "France").sum())
nl_n = int((df.country == "Netherlands").sum())
uk_n = int(df.country.isin(["England", "Wales"]).sum())


def card(ax, x, y, w, h, fc, ec="#e2e8f0", r=0.03):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}", fc=fc, ec=ec, lw=1.5,
                                transform=ax.transAxes, mutation_aspect=0.5))


# cover 1600x800
fig = plt.figure(figsize=(16, 8), dpi=100, facecolor=SOFT)
ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
ax.text(0.06, 0.86, "Open Dataset", color=BLUE, fontsize=20, fontweight="bold", va="center")
ax.text(0.06, 0.72, "Montessori Schools in\nOfficial School Registries", color=INK, fontsize=44,
        fontweight="bold", va="center", linespacing=1.15)
ax.text(0.06, 0.52, "France, England and the Netherlands, straight from government school lists",
        color=MUTED, fontsize=19, va="center")
ax.text(0.06, 0.38, f"{N}", color=BLUE, fontsize=64, fontweight="bold", va="center")
ax.text(0.06 + 0.115, 0.375, "open schools with Montessori\nin their official name", color=INK, fontsize=21,
        va="center", linespacing=1.3)
cards = [("France", fr_n, BLUE, MINT), ("Netherlands", nl_n, GREEN, MINT), ("England and Wales", uk_n, INK, "#ffffff")]
for i, (nm, n, col, bg) in enumerate(cards):
    x = 0.06 + i * 0.30
    card(ax, x, 0.13, 0.27, 0.15, bg)
    ax.text(x + 0.02, 0.205, f"{n}", color=col, fontsize=40, fontweight="bold", va="center")
    ax.text(x + 0.095, 0.205, nm, color=INK, fontsize=19, va="center")
ax.text(0.06, 0.05, "Montessori School Finder  ×  Montessori Theory", color=MUTED, fontsize=14, va="center")
ax.text(0.94, 0.05, "CC BY 4.0", color=MUTED, fontsize=14, va="center", ha="right")
fig.savefig(IMG / "cover.png", dpi=100, facecolor=SOFT)
plt.close(fig)


def style(ax):
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#cbd5e1")
    ax.tick_params(colors=INK, length=0)
    ax.set_facecolor("#ffffff")


def footer(fig, text):
    fig.text(0.02, 0.015, text, color=MUTED, fontsize=9)
    fig.text(0.98, 0.015, "Montessori School Finder × Montessori Theory", color=MUTED, fontsize=9, ha="right")


# chart 1 schools by country
fig, ax = plt.subplots(figsize=(10, 5.2), dpi=150, facecolor=SOFT)
d = by_country.sort_values("schools")
ax.barh(d.country, d.schools, color=[COUNTRY_COLOR[c] for c in d.country], height=0.6)
for y, v in enumerate(d.schools):
    ax.text(v + N * 0.008, y, f"{v}", va="center", color=INK, fontsize=13, fontweight="bold")
style(ax); ax.set_xticks([]); ax.set_xlim(0, d.schools.max() * 1.12)
fig.suptitle("Open Schools With Montessori in the Official Name, by Country", x=0.02, ha="left", color=INK,
             fontsize=15, fontweight="bold")
footer(fig, "Sources: Annuaire de l'education, GIAS, DUO. Nov 2026.")
fig.tight_layout(rect=(0, 0.04, 1, 0.95))
fig.savefig(IMG / "schools_by_country.png", facecolor=SOFT); plt.close(fig)

# chart 2 top regions
fig, ax = plt.subplots(figsize=(10, 6.2), dpi=150, facecolor=SOFT)
top = by_region.sort_values("schools", ascending=False).head(12).sort_values("schools")
ax.barh([f"{r}  ({c})" for r, c in zip(top.region, top.country)], top.schools,
        color=[COUNTRY_COLOR[c] for c in top.country], height=0.65)
for y, v in enumerate(top.schools):
    ax.text(v + 0.8, y, f"{v}", va="center", color=INK, fontsize=12, fontweight="bold")
style(ax); ax.set_xticks([]); ax.set_xlim(0, top.schools.max() * 1.1)
fig.suptitle("The 12 Regions With the Most Montessori-Named Schools", x=0.02, ha="left", color=INK,
             fontsize=15, fontweight="bold")
footer(fig, "Region as published by each registry.")
fig.tight_layout(rect=(0, 0.04, 1, 0.95))
fig.savefig(IMG / "top_regions.png", facecolor=SOFT); plt.close(fig)

# chart 3 public vs private
fig, ax = plt.subplots(figsize=(10, 4.6), dpi=150, facecolor=SOFT)
d = by_country.sort_values("schools", ascending=False)
cols = [("public", BLUE, "Public"), ("private", GREEN, "Private"), ("other_or_not_stated", "#cbd5e1", "Other or not stated")]
left = [0] * len(d)
for k, c, lab in cols:
    ax.barh(d.country, d[k], left=left, color=c, label=lab, height=0.6)
    left = [a + b for a, b in zip(left, d[k])]
ax.invert_yaxis(); style(ax); ax.set_xticks([])
ax.legend(frameon=False, loc="lower right", fontsize=11)
fig.suptitle("Public, Private and Other Status of Montessori-Named Schools", x=0.02, ha="left", color=INK,
             fontsize=15, fontweight="bold")
footer(fig, "Dutch schools of special denomination are publicly funded and counted under other.")
fig.tight_layout(rect=(0, 0.04, 1, 0.94))
fig.savefig(IMG / "public_private.png", facecolor=SOFT); plt.close(fig)
print("outputs done", N)
