"""Download the official registry files into raw/ (France, England, Netherlands).

Usage: python scripts/download.py [raw_dir]
The files are open data. They are treated as plain data and never executed.
"""
import sys
import urllib.request
from datetime import date, timedelta
from pathlib import Path

RAW = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "raw"

FR_URL = ("https://data.education.gouv.fr/api/explore/v2.1/catalog/datasets/"
          "fr-en-annuaire-education/exports/csv?delimiter=%3B")
GB_URL = ("https://ea-edubase-api-prod.azurewebsites.net/edubase/downloads/public/"
          "edubasealldata{d}.csv")
NL_URLS = {
    "po_vestigingen.csv": "https://duo.nl/open_onderwijsdata/images/02.-alle-schoolvestigingen-basisonderwijs.csv",
    "vo_vestigingen.csv": "https://duo.nl/open_onderwijsdata/images/02.-alle-vestigingen-vo.csv",
}


def get(url, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "montessori-open-data/1.0", "Accept-Encoding": "identity"})
    with urllib.request.urlopen(req, timeout=300) as r, open(dest, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    print("saved", dest, dest.stat().st_size, "bytes")


get(FR_URL, RAW / "fr" / "annuaire_full.csv")
for i in range(0, 10):  # the GIAS file name carries a date, try today and the days before
    d = (date.today() - timedelta(days=i)).strftime("%Y%m%d")
    try:
        get(GB_URL.format(d=d), RAW / "gb" / "edubase.csv")
        (RAW / "gb" / "edubase_date.txt").write_text(d)
        break
    except Exception as e:  # 404 until the file of the day exists
        print("no GIAS file for", d, e)
for name, url in NL_URLS.items():
    get(url, RAW / "nl" / name)
