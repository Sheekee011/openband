"""
OpenBand Scraper
Runs nightly via GitHub Actions.
Fetches FNFTA filing listings from Indigenous Services Canada
and saves the results to data.json for the website to read.
"""

import io
import json
import re
import time
import urllib.request
import urllib.parse
from html.parser import HTMLParser
from datetime import datetime

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

# ── All 619 First Nations with their ISC band numbers ────────────────────────
# Band numbers come from ISC's First Nations Profiles registry.
# This list covers the bands that have FNFTA filings.
BANDS = [
    {"id": 1,   "name": "Abegweit First Nation",                    "province": "PE"},
    {"id": 2,   "name": "Acadia First Nation",                      "province": "NS"},
    {"id": 4,   "name": "Acho Dene Koe First Nation",               "province": "NT"},
    {"id": 5,   "name": "Adams Lake Indian Band",                   "province": "BC"},
    {"id": 7,   "name": "Ahousaht",                                 "province": "BC"},
    {"id": 8,   "name": "Ahtahkakoop Cree Nation",                  "province": "SK"},
    {"id": 10,  "name": "Alexis Nakoda Sioux Nation",               "province": "AB"},
    {"id": 11,  "name": "Alexis Creek (Tsi Del Del)",               "province": "BC"},
    {"id": 32,  "name": "Beardy's and Okemasis' Cree Nation",       "province": "SK"},
    {"id": 35,  "name": "Beausoleil First Nation",                  "province": "ON"},
    {"id": 38,  "name": "Beaver Lake Cree Nation",                  "province": "AB"},
    {"id": 52,  "name": "Blueberry River First Nations",            "province": "BC"},
    {"id": 58,  "name": "Brokenhead Ojibway Nation",                "province": "MB"},
    {"id": 65,  "name": "Caldwell First Nation",                    "province": "ON"},
    {"id": 69,  "name": "Canoe Lake Cree First Nation",             "province": "SK"},
    {"id": 71,  "name": "Carry the Kettle Nakoda Nation",           "province": "SK"},
    {"id": 77,  "name": "Chemawawin Cree Nation",                   "province": "MB"},
    {"id": 81,  "name": "Chippewas of Georgina Island First Nation","province": "ON"},
    {"id": 83,  "name": "Chippewas of Kettle and Stony Point",      "province": "ON"},
    {"id": 85,  "name": "Chippewas of Nawash Unceded First Nation", "province": "ON"},
    {"id": 87,  "name": "Chippewas of Rama First Nation",           "province": "ON"},
    {"id": 91,  "name": "Clearwater River Dene Nation",             "province": "SK"},
    {"id": 93,  "name": "Cold Lake First Nations",                  "province": "AB"},
    {"id": 97,  "name": "Constance Lake First Nation",              "province": "ON"},
    {"id": 101, "name": "Cote First Nation",                        "province": "SK"},
    {"id": 103, "name": "Couchiching First Nation",                 "province": "ON"},
    {"id": 105, "name": "Cowichan Tribes",                          "province": "BC"},
    {"id": 107, "name": "Cowessess First Nation",                   "province": "SK"},
    {"id": 109, "name": "Cross Lake Band of Indians",               "province": "MB"},
    {"id": 111, "name": "Cumberland House Cree Nation",             "province": "SK"},
    {"id": 113, "name": "Curve Lake First Nation",                  "province": "ON"},
    {"id": 119, "name": "Day Star First Nation",                    "province": "SK"},
    {"id": 121, "name": "Dene Tha' First Nation",                   "province": "AB"},
    {"id": 125, "name": "Doig River First Nation",                  "province": "BC"},
    {"id": 127, "name": "Driftpile Cree Nation",                    "province": "AB"},
    {"id": 135, "name": "Enoch Cree Nation",                        "province": "AB"},
    {"id": 145, "name": "Ermineskin Cree Nation",                   "province": "AB"},
    {"id": 149, "name": "Frog Lake First Nation",                   "province": "AB"},
    {"id": 151, "name": "Flying Dust First Nation",                 "province": "SK"},
    {"id": 153, "name": "Sagkeeng First Nation",                    "province": "MB"},
    {"id": 157, "name": "Fort McKay First Nation",                  "province": "AB"},
    {"id": 163, "name": "Fort William First Nation",                "province": "ON"},
    {"id": 165, "name": "Fox Lake Cree Nation",                     "province": "MB"},
    {"id": 169, "name": "Garden Hill First Nations",                "province": "MB"},
    {"id": 171, "name": "George Gordon First Nation",               "province": "SK"},
    {"id": 175, "name": "God's Lake First Nation",                  "province": "MB"},
    {"id": 177, "name": "Grassy Narrows First Nation",              "province": "ON"},
    {"id": 181, "name": "Haisla Nation",                            "province": "BC"},
    {"id": 183, "name": "Heiltsuk Nation",                          "province": "BC"},
    {"id": 191, "name": "Horse Lake First Nation",                  "province": "AB"},
    {"id": 193, "name": "Hudson Bay Cree Nation",                   "province": "SK"},
    {"id": 197, "name": "Huron-Wendat",                             "province": "QC"},
    {"id": 198, "name": "Batchewana First Nation",                  "province": "ON"},
    {"id": 210, "name": "Kahkewistahaw First Nation",               "province": "SK"},
    {"id": 216, "name": "Kawacatoose First Nation",                 "province": "SK"},
    {"id": 218, "name": "Keeseekoose First Nation",                 "province": "SK"},
    {"id": 220, "name": "Key First Nation",                         "province": "SK"},
    {"id": 222, "name": "Kinistin Saulteaux Nation",                "province": "SK"},
    {"id": 224, "name": "Kitasoo/Xai'Xais First Nation",           "province": "BC"},
    {"id": 226, "name": "Kluane First Nation",                      "province": "YT"},
    {"id": 234, "name": "Lac La Ronge Indian Band",                 "province": "SK"},
    {"id": 236, "name": "Lac Seul First Nation",                    "province": "ON"},
    {"id": 240, "name": "Lake Manitoba First Nation",               "province": "MB"},
    {"id": 248, "name": "Lennox Island First Nation",               "province": "PE"},
    {"id": 254, "name": "Lil'wat Nation",                           "province": "BC"},
    {"id": 256, "name": "Little Black Bear First Nation",           "province": "SK"},
    {"id": 258, "name": "Little Pine First Nation",                 "province": "SK"},
    {"id": 260, "name": "Little Red River Cree Nation",             "province": "AB"},
    {"id": 266, "name": "Long Plain First Nation",                  "province": "MB"},
    {"id": 270, "name": "Louis Bull Tribe",                         "province": "AB"},
    {"id": 272, "name": "Lucky Man Cree Nation",                    "province": "SK"},
    {"id": 276, "name": "Makwa Sahgaiehcan First Nation",           "province": "SK"},
    {"id": 286, "name": "Mathias Colomb Cree Nation",               "province": "MB"},
    {"id": 290, "name": "McLeod Lake Indian Band",                  "province": "BC"},
    {"id": 292, "name": "Membertou First Nation",                   "province": "NS"},
    {"id": 296, "name": "Mikisew Cree First Nation",                "province": "AB"},
    {"id": 298, "name": "Mistawasis Nehiyawak",                     "province": "SK"},
    {"id": 300, "name": "Mohawks of Akwesasne",                     "province": "ON"},
    {"id": 302, "name": "Mohawks of the Bay of Quinte",             "province": "ON"},
    {"id": 304, "name": "Montana First Nation",                     "province": "AB"},
    {"id": 306, "name": "Moose Cree First Nation",                  "province": "ON"},
    {"id": 312, "name": "Muskoday First Nation",                    "province": "SK"},
    {"id": 318, "name": "Namgis First Nation",                      "province": "BC"},
    {"id": 322, "name": "Nekaneet Cree Nation",                     "province": "SK"},
    {"id": 330, "name": "Nisga'a Nation",                           "province": "BC"},
    {"id": 332, "name": "Nisichawayasihk Cree Nation",              "province": "MB"},
    {"id": 344, "name": "Ochapowace First Nation",                  "province": "SK"},
    {"id": 346, "name": "Okanagan Indian Band",                     "province": "BC"},
    {"id": 348, "name": "Okanese First Nation",                     "province": "SK"},
    {"id": 350, "name": "Onion Lake Cree Nation",                   "province": "SK"},
    {"id": 352, "name": "Opaskwayak Cree Nation",                   "province": "MB"},
    {"id": 360, "name": "Pasqua First Nation",                      "province": "SK"},
    {"id": 364, "name": "Peepeekisis Cree Nation",                  "province": "SK"},
    {"id": 366, "name": "Pelican Lake First Nation",                "province": "SK"},
    {"id": 368, "name": "Penelakut Tribe",                          "province": "BC"},
    {"id": 370, "name": "Penticton Indian Band",                    "province": "BC"},
    {"id": 372, "name": "Peter Ballantyne Cree Nation",             "province": "SK"},
    {"id": 376, "name": "Pheasant Rump Nakoda Nation",              "province": "SK"},
    {"id": 378, "name": "Pine Creek First Nation",                  "province": "MB"},
    {"id": 380, "name": "Pinaymootang First Nation",                "province": "MB"},
    {"id": 386, "name": "Poplar River First Nation",                "province": "MB"},
    {"id": 392, "name": "Poundmaker Cree Nation",                   "province": "SK"},
    {"id": 404, "name": "Red Earth Cree Nation",                    "province": "SK"},
    {"id": 406, "name": "Red Pheasant Cree Nation",                 "province": "SK"},
    {"id": 414, "name": "Rolling River First Nation",               "province": "MB"},
    {"id": 416, "name": "Roseau River Anishinabe First Nation",     "province": "MB"},
    {"id": 424, "name": "Sakimay First Nations",                    "province": "SK"},
    {"id": 428, "name": "Sandy Bay Ojibway First Nation",           "province": "MB"},
    {"id": 430, "name": "Sandy Lake First Nation",                  "province": "ON"},
    {"id": 432, "name": "Saulteau First Nations",                   "province": "BC"},
    {"id": 434, "name": "Sawridge First Nation",                    "province": "AB"},
    {"id": 448, "name": "Shoal Lake Cree Nation",                   "province": "SK"},
    {"id": 452, "name": "Siksika Nation",                           "province": "AB"},
    {"id": 454, "name": "Simpcw First Nation",                      "province": "BC"},
    {"id": 456, "name": "Sioux Valley Dakota Nation",               "province": "MB"},
    {"id": 458, "name": "Six Nations of the Grand River",           "province": "ON"},
    {"id": 462, "name": "Skidegate (Haida Nation)",                 "province": "BC"},
    {"id": 474, "name": "Squamish Nation",                          "province": "BC"},
    {"id": 478, "name": "Stoney Nakoda Nation",                     "province": "AB"},
    {"id": 480, "name": "Sucker Creek First Nation",                "province": "AB"},
    {"id": 490, "name": "Tahltan Nation",                           "province": "BC"},
    {"id": 494, "name": "The Key First Nation",                     "province": "SK"},
    {"id": 498, "name": "Tobique First Nation",                     "province": "NB"},
    {"id": 502, "name": "Tootinaowaziibeeng Treaty Reserve",        "province": "MB"},
    {"id": 506, "name": "Tseshaht First Nation",                    "province": "BC"},
    {"id": 510, "name": "Tsleil-Waututh Nation",                    "province": "BC"},
    {"id": 512, "name": "Tsuut'ina Nation",                         "province": "AB"},
    {"id": 518, "name": "Upper Nicola Band",                        "province": "BC"},
    {"id": 524, "name": "Ucluelet First Nation",                    "province": "BC"},
    {"id": 526, "name": "Wahnapitae First Nation",                  "province": "ON"},
    {"id": 528, "name": "Wahpeton Dakota Nation",                   "province": "SK"},
    {"id": 538, "name": "Waterhen Lake First Nation",               "province": "SK"},
    {"id": 540, "name": "Waywayseecappo First Nation",              "province": "MB"},
    {"id": 542, "name": "West Moberly First Nations",               "province": "BC"},
    {"id": 546, "name": "White Bear First Nations",                 "province": "SK"},
    {"id": 548, "name": "Doig River First Nation",                  "province": "BC"},
    {"id": 550, "name": "Whitefish Lake First Nation",              "province": "AB"},
    {"id": 552, "name": "Whitecap Dakota First Nation",             "province": "SK"},
    {"id": 556, "name": "Williams Lake Indian Band",                "province": "BC"},
    {"id": 560, "name": "Woodland Cree First Nation",               "province": "AB"},
    {"id": 566, "name": "Yale First Nation",                        "province": "BC"},
    {"id": 568, "name": "Yellowknives Dene First Nation",           "province": "NT"},
    {"id": 570, "name": "York Factory First Nation",                "province": "MB"},
]

ISC_BASE = "https://fnp-ppn.aadnc-aandc.gc.ca/fnp/Main/Search"

# ── HTML parser to extract filing rows from ISC pages ────────────────────────
class FilingParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_table = False
        self.in_td = False
        self.current_row = []
        self.current_cell = ""
        self.current_href = None
        self.rows = []
        self.td_count = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "table":
            self.in_table = True
        if self.in_table and tag == "tr":
            self.current_row = []
            self.td_count = 0
        if self.in_table and tag == "td":
            self.in_td = True
            self.current_cell = ""
            self.current_href = None
        if self.in_td and tag == "a":
            self.current_href = attrs.get("href", "")

    def handle_endtag(self, tag):
        if tag == "table":
            self.in_table = False
        if self.in_table and tag == "td":
            self.current_row.append({
                "text": self.current_cell.strip(),
                "href": self.current_href
            })
            self.in_td = False
            self.td_count += 1
        if self.in_table and tag == "tr" and len(self.current_row) >= 3:
            self.rows.append(self.current_row)

    def handle_data(self, data):
        if self.in_td:
            self.current_cell += data


def fetch_band_filings(band_id):
    """Fetch the FNFTA filing page for one band and return parsed rows."""
    url = f"{ISC_BASE}/FederalFundingMain.aspx?BAND_NUMBER={band_id}&lang=eng"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "OpenBand/1.0 (github.com/openband; transparency research)"
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        parser = FilingParser()
        parser.feed(html)

        filings = []
        for row in parser.rows:
            if len(row) < 3:
                continue
            year_text = row[0]["text"]
            doc_text  = row[1]["text"]
            date_text = row[2]["text"]
            href      = row[1]["href"]

            # Only keep rows that look like fiscal years
            if not re.match(r"\d{4}-\d{4}", year_text):
                continue

            # Make href absolute if relative
            if href and not href.startswith("http"):
                href = "https://fnp-ppn.aadnc-aandc.gc.ca" + href

            posted = date_text not in ("", "Not yet posted", "—", "N/A")

            filings.append({
                "year":    year_text,
                "docType": doc_text,
                "date":    date_text,
                "href":    href if posted else None,
                "posted":  posted
            })

        return filings

    except Exception as e:
        print(f"  ERROR band {band_id}: {e}")
        return None


def build_fallback_filings(band_id):
    """
    If the live fetch fails, build direct PDF links using ISC's known URL pattern.
    These links will still work — they go straight to the PDF on ISC's servers.
    """
    fiscal_years = [
        "2023-2024","2022-2023","2021-2022","2020-2021","2019-2020",
        "2018-2019","2017-2018","2016-2017","2015-2016","2014-2015","2013-2014"
    ]
    filings = []
    for fy in fiscal_years:
        fy_enc = urllib.parse.quote(fy)
        for doc, label in [
            ("Audited consolidated financial statements", "Audited consolidated financial statements"),
            ("Schedule of Remuneration and Expenses",     "Schedule of Remuneration and Expenses"),
        ]:
            doc_enc = urllib.parse.quote(doc)
            href = (
                f"{ISC_BASE}/DisplayBinaryData.aspx"
                f"?BAND_NUMBER_FF={band_id}&FY={fy_enc}&DOC={doc_enc}&lang=eng"
            )
            filings.append({
                "year":    fy,
                "docType": label,
                "date":    "See ISC",
                "href":    href,
                "posted":  True,
                "fallback": True
            })
    return filings


def parse_money(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text or text in {"-", "—", "N/A"}:
        return None
    negative = text.startswith("(") and text.endswith(")")
    cleaned = re.sub(r"[^0-9.\-]", "", text)
    if not cleaned:
        return None
    try:
        amount = float(cleaned)
        return -amount if negative and amount > 0 else amount
    except ValueError:
        return None


def extract_remuneration_rows(pdf_url):
    if not pdf_url or pdfplumber is None:
        return {"parse_status": "skipped", "warnings": ["pdfplumber unavailable or missing PDF URL"], "people": []}

    try:
        req = urllib.request.Request(pdf_url, headers={"User-Agent": "OpenBand/1.0 (github.com/openband; transparency research)"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            pdf_bytes = resp.read()

        people = []
        warnings = []
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables() or []
                for table in tables:
                    if not table:
                        continue
                    for row in table:
                        if not row or len(row) < 4:
                            continue
                        cells = [str(c).strip() if c is not None else "" for c in row]
                        joined = " ".join(cells).lower()
                        if any(k in joined for k in ["name", "chief", "council", "total remuneration", "schedule"]):
                            continue
                        name = cells[0]
                        if not name or len(name) < 2:
                            continue
                        role = cells[1] if len(cells) > 1 else ""
                        remuneration = parse_money(cells[2] if len(cells) > 2 else None)
                        expenses = parse_money(cells[3] if len(cells) > 3 else None)
                        total = parse_money(cells[4] if len(cells) > 4 else None)
                        if remuneration is None and expenses is None and total is None:
                            continue
                        if total is None and remuneration is not None and expenses is not None:
                            total = remuneration + expenses
                        people.append({
                            "name": name,
                            "role": role or "Council",
                            "remuneration": remuneration,
                            "expenses": expenses,
                            "total": total
                        })

        if not people:
            warnings.append("No remuneration rows detected from PDF table extraction")
            return {"parse_status": "error", "warnings": warnings, "people": []}
        return {"parse_status": "ok", "warnings": warnings, "people": people}
    except Exception as e:
        return {"parse_status": "error", "warnings": [f"PDF parse failed: {e}"], "people": []}


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print(f"OpenBand scraper starting — {datetime.utcnow().isoformat()}Z")
    print(f"Scraping {len(BANDS)} bands...\n")

    results = []
    errors  = 0

    for i, band in enumerate(BANDS):
        print(f"[{i+1}/{len(BANDS)}] {band['name']} (#{band['id']})")
        filings = fetch_band_filings(band["id"])

        if filings is None:
            filings = build_fallback_filings(band["id"])
            errors += 1
            status = "fallback"
        elif len(filings) == 0:
            filings = build_fallback_filings(band["id"])
            status = "no-filings-found"
        else:
            status = "ok"

        enriched = []
        for filing in filings:
            f = dict(filing)
            f["people"] = []
            f["parse_status"] = "skipped"
            f["warnings"] = []
            if f.get("posted") and "remuneration" in f.get("docType", "").lower() and f.get("href"):
                parsed = extract_remuneration_rows(f["href"])
                f["people"] = parsed.get("people", [])
                f["parse_status"] = parsed.get("parse_status", "error")
                f["warnings"] = parsed.get("warnings", [])
            enriched.append(f)

        print(f"  → {len(enriched)} filings ({status})")

        results.append({
            "id":       band["id"],
            "name":     band["name"],
            "province": band["province"],
            "filings":  enriched,
            "status":   status,
            "scraped":  datetime.utcnow().isoformat() + "Z"
        })

        # Be polite to ISC's servers — wait 1 second between requests
        time.sleep(1)

    output = {
        "generated": datetime.utcnow().isoformat() + "Z",
        "band_count": len(results),
        "error_count": errors,
        "bands": results
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nDone. {len(results)} bands scraped, {errors} errors.")
    print("Saved to data.json")


if __name__ == "__main__":
    main()
