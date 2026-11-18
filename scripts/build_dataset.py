"""Build the Montessori schools in official registries dataset from the raw registry files.

Usage: python scripts/build_dataset.py [raw_dir] [--msf-db path/to/msf.sqlite] [--retrieved YYYY-MM-DD]

Selection: the school name contains "Montessori" (case and accent insensitive).
Only open schools are kept. Nothing is estimated or filled in.
--msf-db is optional. Without it the column msf_city_url stays empty.
"""
import argparse
import csv
import math
import re
import sqlite3
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("raw", nargs="?", default=str(ROOT / "raw"))
ap.add_argument("--msf-db", default=None)
ap.add_argument("--retrieved", default="2026-11-17")
args = ap.parse_args()
RAW = Path(args.raw)
OUT = ROOT / "data"
OUT.mkdir(exist_ok=True)

COLS = ["country", "country_code", "registry", "official_id", "name", "type_phase", "registry_category",
        "public_or_private", "status", "address", "postcode", "city", "region", "latitude", "longitude",
        "age_range_or_phase", "source_url", "retrieved_at", "match_reason", "msf_city_url"]


def fold(s):
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def is_match(name):
    return "montessori" in fold(name)


def clean(s):
    return re.sub(r"\s+", " ", (s or "").strip())


def join(*parts):
    return ", ".join(clean(p) for p in parts if clean(p))


def read_csv(path, enc, delim=","):
    with open(path, encoding=enc, newline="") as f:
        return list(csv.DictReader(f, delimiter=delim))


rows = []
totals = []  # denominators: all open records in each registry file

# ---------- France ----------
FR_SRC = "https://data.education.gouv.fr/explore/dataset/fr-en-annuaire-education/table/?q={id}"
fr_all = read_csv(RAW / "fr" / "annuaire_full.csv", "utf-8-sig", ";")
totals.append(("France", "Annuaire de l'education, all establishments", sum(r["etat"] == "OUVERT" for r in fr_all)))
for r in fr_all:
    if not is_match(r["nom_etablissement"]) or r["etat"] != "OUVERT":
        continue
    flags = []
    if r["ecole_maternelle"] == "1":
        flags.append("Maternelle")
    if r["ecole_elementaire"] == "1":
        flags.append("Elementaire")
    rows.append({
        "country": "France", "country_code": "FR",
        "registry": "Annuaire de l'education (Ministere de l'Education nationale)",
        "official_id": r["identifiant_de_l_etablissement"], "name": clean(r["nom_etablissement"]),
        "type_phase": r["type_etablissement"], "registry_category": r["libelle_nature"].capitalize(),
        "public_or_private": {"Public": "Public", "Privé": "Private"}.get(r["statut_public_prive"], r["statut_public_prive"]),
        "status": "Open", "address": join(r["adresse_1"], r["adresse_2"]), "postcode": r["code_postal"],
        "city": clean(r["nom_commune"]), "region": r["libelle_region"],
        "latitude": r["latitude"], "longitude": r["longitude"],
        "age_range_or_phase": " and ".join(flags),
        "source_url": FR_SRC.format(id=r["identifiant_de_l_etablissement"]),
        "retrieved_at": args.retrieved, "match_reason": "name contains Montessori",
    })

# ---------- England, plus the one Welsh record GIAS holds ----------
GB_SRC = "https://get-information-schools.service.gov.uk/Establishments/Establishment/Details/{urn}"
gb_all = read_csv(RAW / "gb" / "edubase.csv", "cp1252")
totals.append(("England and Wales", "GIAS, all open establishments (includes a few outside England and Wales)",
               sum(r["EstablishmentStatus (name)"].startswith("Open") for r in gb_all)))
for r in gb_all:
    if not is_match(r["EstablishmentName"]):
        continue
    st = r["EstablishmentStatus (name)"]
    if not st.startswith("Open"):
        continue
    if r["TypeOfEstablishment (name)"] == "British schools overseas":
        continue  # outside the UK, not kept
    gor = r["GOR (name)"]
    if gor.startswith("Wales"):
        country, code, region = "Wales", "GB-WLS", "Wales"
    else:
        country, code, region = "England", "GB-ENG", gor
    lo, hi = r["StatutoryLowAge"], r["StatutoryHighAge"]
    group = r["EstablishmentTypeGroup (name)"]
    rows.append({
        "country": country, "country_code": code,
        "registry": "Get Information About Schools (Department for Education)",
        "official_id": r["URN"], "name": clean(r["EstablishmentName"]),
        "type_phase": r["TypeOfEstablishment (name)"], "registry_category": group,
        "public_or_private": "Private (independent)" if group == "Independent schools" else "Not stated",
        "status": st, "address": join(r["Street"], r["Locality"], r["Address3"]), "postcode": r["Postcode"],
        "city": clean(r["Town"]), "region": region, "latitude": "", "longitude": "",
        "age_range_or_phase": f"{lo}-{hi}" if lo and hi else "",
        "source_url": GB_SRC.format(urn=r["URN"]), "retrieved_at": args.retrieved,
        "match_reason": "name contains Montessori",
    })

# ---------- Netherlands ----------
NL_SRC = {"po": "https://duo.nl/open_onderwijsdata/images/02.-alle-schoolvestigingen-basisonderwijs.csv",
          "vo": "https://duo.nl/open_onderwijsdata/images/02.-alle-vestigingen-vo.csv"}
NL_PHASE = {"po": "Primary (basisonderwijs)", "vo": "Secondary (voortgezet onderwijs)"}


NL_TAGS = {"nh": "north-holland", "nb": "north-brabant", "ov": "overijssel", "gld": "gelderland", "ut": "utrecht",
           "zh": "south-holland", "fr": "friesland", "gr": "groningen", "dr": "drenthe", "fl": "flevoland",
           "li": "limburg", "ze": "zeeland"}


def nl_place(s):
    s = clean(s)
    s = re.sub(r"\s+GEM\s+.*$", "", s)  # DUO appends "GEM <municipality>" to some place names
    if s.isupper():
        s = s.title()
        s = re.sub(r"^'S-", "'s-", s)
        s = re.sub(r"^'T ", "'t ", s)
    return s


for key in ("po", "vo"):
    nl_all = read_csv(RAW / "nl" / f"{key}_vestigingen.csv", "cp1252", ";")
    totals.append(("Netherlands", f"DUO {NL_PHASE[key]}, all school locations", len(nl_all)))
    for r in nl_all:
        if not is_match(r["VESTIGINGSNAAM"]):
            continue
        den = r["DENOMINATIE"]
        rows.append({
            "country": "Netherlands", "country_code": "NL",
            "registry": "DUO Open Onderwijsdata (Dienst Uitvoering Onderwijs)",
            "official_id": r["VESTIGINGSCODE"], "name": clean(r["VESTIGINGSNAAM"]),
            "type_phase": NL_PHASE[key], "registry_category": den,
            "public_or_private": "Public" if den == "Openbaar" else "Publicly funded, special or denominational",
            "status": "Open",
            "address": clean(r["STRAATNAAM"] + " " + r["HUISNUMMER-TOEVOEGING"]),
            "postcode": clean(r["POSTCODE"]), "city": nl_place(r["PLAATSNAAM"]), "region": r["PROVINCIE"],
            "latitude": "", "longitude": "", "age_range_or_phase": "",
            "source_url": NL_SRC[key], "retrieved_at": args.retrieved, "match_reason": "name contains Montessori",
        })

# ---------- optional link to a Montessori School Finder city page ----------
for r in rows:
    r["msf_city_url"] = ""
if args.msf_db:
    db = sqlite3.connect(f"file:{args.msf_db}?mode=ro", uri=True)
    by = {}
    for code, name, path, lat, lng in db.execute("select country_code,name,path,lat,lng from cities"):
        by.setdefault((code, fold(name)), []).append((path, lat, lng))

    def km(a, b, c, d):
        p = math.pi / 180
        x = math.sin((c - a) * p / 2) ** 2 + math.cos(a * p) * math.cos(c * p) * math.sin((d - b) * p / 2) ** 2
        return 12742 * math.asin(math.sqrt(x))

    for r in rows:
        city = re.sub(r"\s+\d+\w*\s+arrondissement$", "", fold(r["city"]).strip()).strip()
        cands = by.get((r["country_code"], city), [])
        if not cands and r["country_code"] == "NL":
            # DUO adds a province tag to some place names, for example "Hoorn Nh" or "Oosterhout Nb".
            # The link is kept only when the tag agrees with the province of the MSF city page.
            m = re.match(r"(.*)\s+(nh|nb|ov|gld|ut|zh|fr|gr|dr|fl|li|ze)$", city)
            if m:
                slug = NL_TAGS[m.group(2)]
                cands = [c for c in by.get(("NL", m.group(1)), []) if f"/netherlands/{slug}/" in c[0]]
        if r["latitude"]:
            # with coordinates (France), keep only city pages within 15 km of the school and take the nearest
            la, lo_ = float(r["latitude"]), float(r["longitude"])
            cands = [c for c in cands if km(la, lo_, c[1], c[2]) < 15]
            cands.sort(key=lambda c: km(la, lo_, c[1], c[2]))
            cands = cands[:1]
        if len(cands) == 1:
            r["msf_city_url"] = "https://www.montessorischoolfinder.com" + cands[0][0]

# ---------- checks and output ----------
ids = [(r["country_code"], r["official_id"]) for r in rows]
assert len(ids) == len(set(ids)), "duplicate official ids"
rows.sort(key=lambda r: (r["country"], r["region"], r["city"], r["name"]))
with open(OUT / "montessori_schools_official_registries.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, COLS)
    w.writeheader()
    w.writerows(rows)
with open(OUT / "registry_totals.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["country", "registry_file", "open_establishments"])
    w.writerows(totals)
print("rows", len(rows))
