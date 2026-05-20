"""
OpenBand Scraper

Runs nightly via GitHub Actions.
Fetches FNFTA filing listings from Indigenous Services Canada and saves the
results to data.json for the website to read.
"""

import base64
import io
import json
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime
from html.parser import HTMLParser

try:
    import pdfplumber
except ImportError:
    pdfplumber = None


# Band numbers come from ISC's First Nations Profiles registry.
# This starter list covers the bands currently tracked by OpenBand.
BANDS = [
    {"id": 1, "name": "Abegweit First Nation", "province": "PE"},
    {"id": 2, "name": "Acadia First Nation", "province": "NS"},
    {"id": 4, "name": "Acho Dene Koe First Nation", "province": "NT"},
    {"id": 5, "name": "Adams Lake Indian Band", "province": "BC"},
    {"id": 7, "name": "Ahousaht", "province": "BC"},
    {"id": 8, "name": "Ahtahkakoop Cree Nation", "province": "SK"},
    {"id": 10, "name": "Alexis Nakoda Sioux Nation", "province": "AB"},
    {"id": 11, "name": "Alexis Creek (Tsi Del Del)", "province": "BC"},
    {"id": 32, "name": "Beardy's and Okemasis' Cree Nation", "province": "SK"},
    {"id": 35, "name": "Beausoleil First Nation", "province": "ON"},
    {"id": 38, "name": "Beaver Lake Cree Nation", "province": "AB"},
    {"id": 52, "name": "Blueberry River First Nations", "province": "BC"},
    {"id": 58, "name": "Brokenhead Ojibway Nation", "province": "MB"},
    {"id": 65, "name": "Caldwell First Nation", "province": "ON"},
    {"id": 69, "name": "Canoe Lake Cree First Nation", "province": "SK"},
    {"id": 71, "name": "Carry the Kettle Nakoda Nation", "province": "SK"},
    {"id": 77, "name": "Chemawawin Cree Nation", "province": "MB"},
    {"id": 81, "name": "Chippewas of Georgina Island First Nation", "province": "ON"},
    {"id": 83, "name": "Chippewas of Kettle and Stony Point", "province": "ON"},
    {"id": 85, "name": "Chippewas of Nawash Unceded First Nation", "province": "ON"},
    {"id": 87, "name": "Chippewas of Rama First Nation", "province": "ON"},
    {"id": 91, "name": "Clearwater River Dene Nation", "province": "SK"},
    {"id": 93, "name": "Cold Lake First Nations", "province": "AB"},
    {"id": 97, "name": "Constance Lake First Nation", "province": "ON"},
    {"id": 101, "name": "Cote First Nation", "province": "SK"},
    {"id": 103, "name": "Couchiching First Nation", "province": "ON"},
    {"id": 105, "name": "Cowichan Tribes", "province": "BC"},
    {"id": 107, "name": "Cowessess First Nation", "province": "SK"},
    {"id": 109, "name": "Cross Lake Band of Indians", "province": "MB"},
    {"id": 111, "name": "Cumberland House Cree Nation", "province": "SK"},
    {"id": 113, "name": "Curve Lake First Nation", "province": "ON"},
    {"id": 119, "name": "Day Star First Nation", "province": "SK"},
    {"id": 121, "name": "Dene Tha' First Nation", "province": "AB"},
    {"id": 125, "name": "Doig River First Nation", "province": "BC"},
    {"id": 127, "name": "Driftpile Cree Nation", "province": "AB"},
    {"id": 135, "name": "Enoch Cree Nation", "province": "AB"},
    {"id": 145, "name": "Ermineskin Cree Nation", "province": "AB"},
    {"id": 149, "name": "Frog Lake First Nation", "province": "AB"},
    {"id": 151, "name": "Flying Dust First Nation", "province": "SK"},
    {"id": 153, "name": "Sagkeeng First Nation", "province": "MB"},
    {"id": 157, "name": "Fort McKay First Nation", "province": "AB"},
    {"id": 163, "name": "Fort William First Nation", "province": "ON"},
    {"id": 165, "name": "Fox Lake Cree Nation", "province": "MB"},
    {"id": 169, "name": "Garden Hill First Nations", "province": "MB"},
    {"id": 171, "name": "George Gordon First Nation", "province": "SK"},
    {"id": 175, "name": "God's Lake First Nation", "province": "MB"},
    {"id": 177, "name": "Grassy Narrows First Nation", "province": "ON"},
    {"id": 181, "name": "Haisla Nation", "province": "BC"},
    {"id": 183, "name": "Heiltsuk Nation", "province": "BC"},
    {"id": 191, "name": "Horse Lake First Nation", "province": "AB"},
    {"id": 193, "name": "Hudson Bay Cree Nation", "province": "SK"},
    {"id": 197, "name": "Huron-Wendat", "province": "QC"},
    {"id": 198, "name": "Batchewana First Nation", "province": "ON"},
    {"id": 210, "name": "Kahkewistahaw First Nation", "province": "SK"},
    {"id": 216, "name": "Kawacatoose First Nation", "province": "SK"},
    {"id": 218, "name": "Keeseekoose First Nation", "province": "SK"},
    {"id": 220, "name": "Key First Nation", "province": "SK"},
    {"id": 222, "name": "Kinistin Saulteaux Nation", "province": "SK"},
    {"id": 224, "name": "Kitasoo/Xai'Xais First Nation", "province": "BC"},
    {"id": 226, "name": "Kluane First Nation", "province": "YT"},
    {"id": 234, "name": "Lac La Ronge Indian Band", "province": "SK"},
    {"id": 236, "name": "Lac Seul First Nation", "province": "ON"},
    {"id": 240, "name": "Lake Manitoba First Nation", "province": "MB"},
    {"id": 248, "name": "Lennox Island First Nation", "province": "PE"},
    {"id": 254, "name": "Lil'wat Nation", "province": "BC"},
    {"id": 256, "name": "Little Black Bear First Nation", "province": "SK"},
    {"id": 258, "name": "Little Pine First Nation", "province": "SK"},
    {"id": 260, "name": "Little Red River Cree Nation", "province": "AB"},
    {"id": 266, "name": "Long Plain First Nation", "province": "MB"},
    {"id": 270, "name": "Louis Bull Tribe", "province": "AB"},
    {"id": 272, "name": "Lucky Man Cree Nation", "province": "SK"},
    {"id": 276, "name": "Makwa Sahgaiehcan First Nation", "province": "SK"},
    {"id": 286, "name": "Mathias Colomb Cree Nation", "province": "MB"},
    {"id": 290, "name": "McLeod Lake Indian Band", "province": "BC"},
    {"id": 292, "name": "Membertou First Nation", "province": "NS"},
    {"id": 296, "name": "Mikisew Cree First Nation", "province": "AB"},
    {"id": 298, "name": "Mistawasis Nehiyawak", "province": "SK"},
    {"id": 300, "name": "Mohawks of Akwesasne", "province": "ON"},
    {"id": 302, "name": "Mohawks of the Bay of Quinte", "province": "ON"},
    {"id": 304, "name": "Montana First Nation", "province": "AB"},
    {"id": 306, "name": "Moose Cree First Nation", "province": "ON"},
    {"id": 312, "name": "Muskoday First Nation", "province": "SK"},
    {"id": 318, "name": "Namgis First Nation", "province": "BC"},
    {"id": 322, "name": "Nekaneet Cree Nation", "province": "SK"},
    {"id": 330, "name": "Nisga'a Nation", "province": "BC"},
    {"id": 332, "name": "Nisichawayasihk Cree Nation", "province": "MB"},
    {"id": 344, "name": "Ochapowace First Nation", "province": "SK"},
    {"id": 346, "name": "Okanagan Indian Band", "province": "BC"},
    {"id": 348, "name": "Okanese First Nation", "province": "SK"},
    {"id": 350, "name": "Onion Lake Cree Nation", "province": "SK"},
    {"id": 352, "name": "Opaskwayak Cree Nation", "province": "MB"},
    {"id": 360, "name": "Pasqua First Nation", "province": "SK"},
    {"id": 364, "name": "Peepeekisis Cree Nation", "province": "SK"},
    {"id": 366, "name": "Pelican Lake First Nation", "province": "SK"},
    {"id": 368, "name": "Penelakut Tribe", "province": "BC"},
    {"id": 370, "name": "Penticton Indian Band", "province": "BC"},
    {"id": 372, "name": "Peter Ballantyne Cree Nation", "province": "SK"},
    {"id": 376, "name": "Pheasant Rump Nakoda Nation", "province": "SK"},
    {"id": 378, "name": "Pine Creek First Nation", "province": "MB"},
    {"id": 380, "name": "Pinaymootang First Nation", "province": "MB"},
    {"id": 386, "name": "Poplar River First Nation", "province": "MB"},
    {"id": 392, "name": "Poundmaker Cree Nation", "province": "SK"},
    {"id": 404, "name": "Red Earth Cree Nation", "province": "SK"},
    {"id": 406, "name": "Red Pheasant Cree Nation", "province": "SK"},
    {"id": 414, "name": "Rolling River First Nation", "province": "MB"},
    {"id": 416, "name": "Roseau River Anishinabe First Nation", "province": "MB"},
    {"id": 424, "name": "Sakimay First Nations", "province": "SK"},
    {"id": 428, "name": "Sandy Bay Ojibway First Nation", "province": "MB"},
    {"id": 430, "name": "Sandy Lake First Nation", "province": "ON"},
    {"id": 432, "name": "Saulteau First Nations", "province": "BC"},
    {"id": 434, "name": "Sawridge First Nation", "province": "AB"},
    {"id": 448, "name": "Shoal Lake Cree Nation", "province": "SK"},
    {"id": 452, "name": "Siksika Nation", "province": "AB"},
    {"id": 454, "name": "Simpcw First Nation", "province": "BC"},
    {"id": 456, "name": "Sioux Valley Dakota Nation", "province": "MB"},
    {"id": 458, "name": "Six Nations of the Grand River", "province": "ON"},
    {"id": 462, "name": "Skidegate (Haida Nation)", "province": "BC"},
    {"id": 474, "name": "Squamish Nation", "province": "BC"},
    {"id": 478, "name": "Stoney Nakoda Nation", "province": "AB"},
    {"id": 480, "name": "Sucker Creek First Nation", "province": "AB"},
    {"id": 490, "name": "Tahltan Nation", "province": "BC"},
    {"id": 494, "name": "The Key First Nation", "province": "SK"},
    {"id": 498, "name": "Tobique First Nation", "province": "NB"},
    {"id": 502, "name": "Tootinaowaziibeeng Treaty Reserve", "province": "MB"},
    {"id": 506, "name": "Tseshaht First Nation", "province": "BC"},
    {"id": 510, "name": "Tsleil-Waututh Nation", "province": "BC"},
    {"id": 512, "name": "Tsuut'ina Nation", "province": "AB"},
    {"id": 518, "name": "Upper Nicola Band", "province": "BC"},
    {"id": 524, "name": "Ucluelet First Nation", "province": "BC"},
    {"id": 526, "name": "Wahnapitae First Nation", "province": "ON"},
    {"id": 528, "name": "Wahpeton Dakota Nation", "province": "SK"},
    {"id": 538, "name": "Waterhen Lake First Nation", "province": "SK"},
    {"id": 540, "name": "Waywayseecappo First Nation", "province": "MB"},
    {"id": 542, "name": "West Moberly First Nations", "province": "BC"},
    {"id": 546, "name": "White Bear First Nations", "province": "SK"},
    {"id": 548, "name": "Doig River First Nation", "province": "BC"},
    {"id": 550, "name": "Whitefish Lake First Nation", "province": "AB"},
    {"id": 552, "name": "Whitecap Dakota First Nation", "province": "SK"},
    {"id": 556, "name": "Williams Lake Indian Band", "province": "BC"},
    {"id": 560, "name": "Woodland Cree First Nation", "province": "AB"},
    {"id": 566, "name": "Yale First Nation", "province": "BC"},
    {"id": 568, "name": "Yellowknives Dene First Nation", "province": "NT"},
    {"id": 570, "name": "York Factory First Nation", "province": "MB"},
]

ISC_HOST = "https://fnp-ppn.aadnc-aandc.gc.ca"
ISC_BASE = f"{ISC_HOST}/fnp/Main/Search"
USER_AGENT = "OpenBand/1.0 (transparency research; nightly GitHub Action)"


def utc_now():
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def normalize_pdf_url(url):
    """Ensure query params are URL-encoded before requesting ISC PDFs."""
    if not url:
        return url
    parts = urllib.parse.urlsplit(url)
    query_pairs = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    safe_query = urllib.parse.urlencode(query_pairs, quote_via=urllib.parse.quote)
    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, parts.path, safe_query, parts.fragment)
    )


class FilingParser(HTMLParser):
    """Extract rows from ISC filing-listing tables."""

    def __init__(self):
        super().__init__()
        self.in_table = False
        self.in_td = False
        self.current_row = []
        self.current_cell = ""
        self.current_href = None
        self.rows = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "table":
            self.in_table = True
        elif self.in_table and tag == "tr":
            self.current_row = []
        elif self.in_table and tag == "td":
            self.in_td = True
            self.current_cell = ""
            self.current_href = None
        elif self.in_td and tag == "a":
            self.current_href = attrs.get("href", "")

    def handle_endtag(self, tag):
        if tag == "td" and self.in_td:
            self.current_row.append(
                {"text": " ".join(self.current_cell.split()), "href": self.current_href}
            )
            self.in_td = False
        elif tag == "tr" and self.in_table and len(self.current_row) >= 3:
            self.rows.append(self.current_row)
        elif tag == "table":
            self.in_table = False

    def handle_data(self, data):
        if self.in_td:
            self.current_cell += data


def fetch_url(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_band_filings(band_id):
    """Fetch the FNFTA filing page for one band and return parsed rows."""
    url = f"{ISC_BASE}/FederalFundingMain.aspx?BAND_NUMBER={band_id}&lang=eng"
    try:
        html = fetch_url(url, timeout=15).decode("utf-8", errors="replace")
        parser = FilingParser()
        parser.feed(html)

        filings = []
        for row in parser.rows:
            year_text = row[0]["text"]
            doc_text = row[1]["text"]
            date_text = row[2]["text"]
            href = row[1]["href"]

            if not re.match(r"\d{4}-\d{4}", year_text):
                continue

            if href and not href.startswith("http"):
                href = f"{ISC_HOST}/{href.lstrip('/')}"

            posted = date_text not in ("", "Not yet posted", "-", "—", "N/A")
            filings.append(
                {
                    "year": year_text,
                    "docType": doc_text,
                    "date": date_text,
                    "href": href if posted else None,
                    "posted": posted,
                }
            )

        return filings
    except Exception as exc:
        print(f"  ERROR band {band_id}: {exc}")
        return None


def build_fallback_filings(band_id):
    """Build direct ISC PDF links using the public DisplayBinaryData URL pattern."""
    fiscal_years = [
        "2023-2024",
        "2022-2023",
        "2021-2022",
        "2020-2021",
        "2019-2020",
        "2018-2019",
        "2017-2018",
        "2016-2017",
        "2015-2016",
        "2014-2015",
        "2013-2014",
    ]
    doc_types = [
        "Audited consolidated financial statements",
        "Schedule of Remuneration and Expenses",
    ]

    filings = []
    for fy in fiscal_years:
        for doc in doc_types:
            href = (
                f"{ISC_BASE}/DisplayBinaryData.aspx?"
                + urllib.parse.urlencode(
                    {"BAND_NUMBER_FF": band_id, "FY": fy, "DOC": doc, "lang": "eng"},
                    quote_via=urllib.parse.quote,
                )
            )
            filings.append(
                {
                    "year": fy,
                    "docType": doc,
                    "date": "See ISC",
                    "href": href,
                    "posted": True,
                    "fallback": True,
                }
            )
    return filings


def parse_money(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text or text in {"-", "—", "N/A"}:
        return None
    negative = text.startswith("(") and text.endswith(")")
    cleaned = re.sub(r"[^0-9.\-]", "", text)
    if not cleaned or cleaned in {"-", "."}:
        return None
    try:
        amount = float(cleaned)
        return -amount if negative and amount > 0 else amount
    except ValueError:
        return None


def response_output_text(response_json):
    if response_json.get("output_text"):
        return response_json["output_text"]

    chunks = []
    for item in response_json.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                chunks.append(content["text"])
    return "\n".join(chunks).strip()


def extract_with_openai_vision(pdf_bytes):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {
            "parse_status": "skipped_openai_no_key",
            "warnings": ["OPENAI_API_KEY not set"],
            "people": [],
        }

    prompt = (
        "Extract the Chief and Council remuneration table from this PDF. "
        "Return only JSON with this shape: "
        '{"people":[{"name":str,"role":str,"months":number|null,'
        '"remuneration":number|null,"travel":number|null,"expenses":number|null,'
        '"creditCard":number|null,"otherPayments":number|null,"total":number|null}]}. '
        "If no table is present, return {\"people\":[]}."
    )
    payload = {
        "model": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {
                        "type": "input_file",
                        "filename": "filing.pdf",
                        "file_data": "data:application/pdf;base64,"
                        + base64.b64encode(pdf_bytes).decode("ascii"),
                    },
                ],
            }
        ],
    }

    req = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = json.loads(resp.read().decode("utf-8"))

        text = response_output_text(raw)
        if not text:
            return {
                "parse_status": "error_openai_empty",
                "warnings": ["OpenAI returned empty output"],
                "people": [],
            }

        data = json.loads(text)
        rows = data.get("people", []) if isinstance(data, dict) else []
        people = []
        for row in rows:
            people.append(
                {
                    "name": str(row.get("name", "")).strip(),
                    "role": str(row.get("role", "")).strip() or "Council",
                    "months": parse_money(row.get("months")),
                    "remuneration": parse_money(row.get("remuneration")),
                    "travel": parse_money(row.get("travel")),
                    "expenses": parse_money(row.get("expenses")),
                    "creditCard": parse_money(row.get("creditCard")),
                    "otherPayments": parse_money(row.get("otherPayments")),
                    "total": parse_money(row.get("total")),
                }
            )
        return {
            "parse_status": "ok_openai",
            "warnings": [],
            "people": [p for p in people if p["name"]],
        }
    except Exception as exc:
        return {
            "parse_status": "error_openai",
            "warnings": [f"OpenAI parse failed: {exc}"],
            "people": [],
        }


def role_from_cells(cells):
    joined = " ".join(cells).lower()
    if re.search(r"\bchief\b", joined):
        return "Chief"
    if re.search(r"\bcouncillor\b|\bcouncil\b", joined):
        return "Councillor"
    return "Council"


def header_key(cell):
    text = re.sub(r"\s+", " ", str(cell or "").strip().lower())
    if not text:
        return None
    if "credit" in text and "card" in text:
        return "creditCard"
    if "other" in text and ("payment" in text or "payments" in text):
        return "otherPayments"
    if "travel" in text or "per diem" in text:
        return "travel"
    if "expense" in text and "remuneration" not in text:
        return "expenses"
    if "remuneration" in text or "salary" in text or "honoraria" in text:
        return "remuneration"
    if "month" in text:
        return "months"
    if "position" in text or text == "chief and council":
        return "role"
    if text.startswith("name"):
        return "name"
    if text == "total":
        return "total"
    return None


def clean_person_name(name):
    name = re.sub(r"\*+$", "", str(name or "").strip())
    name = re.sub(r"\s+", " ", name)
    return name


def value_by_key(cells, keys, key):
    if key not in keys:
        return None
    index = keys.index(key)
    if index >= len(cells):
        return None
    return cells[index]


def extract_people_from_table(table):
    people = []
    keys = []

    for row in table:
        if not row:
            continue

        cells = [" ".join(str(cell or "").split()) for cell in row]
        joined = " ".join(cells).lower()
        if not joined:
            continue

        possible_keys = [header_key(cell) for cell in cells]
        if "remuneration" in possible_keys and (
            "months" in possible_keys
            or "travel" in possible_keys
            or "expenses" in possible_keys
            or "otherPayments" in possible_keys
            or "total" in possible_keys
        ):
            keys = possible_keys
            continue

        amounts = [parse_money(cell) for cell in cells]
        amounts = [amount for amount in amounts if amount is not None]
        if not amounts:
            continue
        if re.match(r"^\s*total\b", cells[0], re.I):
            continue

        name = clean_person_name(value_by_key(cells, keys, "name"))
        role = value_by_key(cells, keys, "role") or ""

        # Some schedules use a blank name header with role in column 1 and name in column 2.
        if not name and cells and re.search(r"chief|councillor|council", cells[0], re.I):
            role = role or cells[0]
            name = clean_person_name(cells[1] if len(cells) > 1 else "")

        if not name:
            for cell in cells:
                if parse_money(cell) is not None:
                    continue
                if re.search(r"chief|councillor|council|months?|position", cell, re.I):
                    continue
                if len(cell) >= 2:
                    name = clean_person_name(cell)
                    break
        if not name:
            continue

        months = parse_money(value_by_key(cells, keys, "months"))
        remuneration = parse_money(value_by_key(cells, keys, "remuneration"))
        travel = parse_money(value_by_key(cells, keys, "travel"))
        expenses = parse_money(value_by_key(cells, keys, "expenses"))
        credit_card = parse_money(value_by_key(cells, keys, "creditCard"))
        other_payments = parse_money(value_by_key(cells, keys, "otherPayments"))
        total = parse_money(value_by_key(cells, keys, "total"))

        if remuneration is None:
            remuneration = amounts[0]
        if total is None:
            total = sum(
                value or 0
                for value in [remuneration, travel, expenses, credit_card, other_payments]
            )

        people.append(
            {
                "name": name,
                "role": role_from_cells([role] + cells),
                "months": months,
                "remuneration": remuneration,
                "travel": travel,
                "expenses": expenses,
                "creditCard": credit_card,
                "otherPayments": other_payments,
                "total": total,
            }
        )
    return people


def extract_remuneration_rows(pdf_url):
    if not pdf_url:
        return {"parse_status": "no_pdf_url", "warnings": ["No PDF URL available"], "people": []}

    warnings = []
    try:
        pdf_bytes = fetch_url(normalize_pdf_url(pdf_url), timeout=30)
    except Exception as exc:
        return {
            "parse_status": "error_pdf_download",
            "warnings": [f"PDF download failed: {exc}"],
            "people": [],
        }

    if pdfplumber is None:
        ai_result = extract_with_openai_vision(pdf_bytes)
        ai_result["warnings"] = ["pdfplumber unavailable"] + ai_result.get("warnings", [])
        return ai_result

    try:
        people = []
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables() or []:
                    people.extend(extract_people_from_table(table))

        if people:
            return {"parse_status": "ok_pdfplumber", "warnings": warnings, "people": people}

        ai_result = extract_with_openai_vision(pdf_bytes)
        if ai_result.get("people"):
            ai_result["warnings"] = ["Parsed via OpenAI fallback"] + ai_result.get("warnings", [])
            return ai_result

        warnings.append("No remuneration rows detected from PDF table extraction")
        warnings.extend(ai_result.get("warnings", []))
        return {
            "parse_status": ai_result.get("parse_status", "no_rows"),
            "warnings": warnings,
            "people": [],
        }
    except Exception as exc:
        return {"parse_status": "error", "warnings": [f"PDF parse failed: {exc}"], "people": []}


def should_parse_people(filing):
    return filing.get("posted") and "remuneration" in filing.get("docType", "").lower()


def main():
    print(f"OpenBand scraper starting - {utc_now()}")
    print(f"Scraping {len(BANDS)} bands...\n")

    results = []
    errors = 0

    for index, band in enumerate(BANDS, start=1):
        print(f"[{index}/{len(BANDS)}] {band['name']} (#{band['id']})")
        filings = fetch_band_filings(band["id"])

        if filings is None:
            filings = build_fallback_filings(band["id"])
            errors += 1
            status = "fallback"
        elif not filings:
            filings = build_fallback_filings(band["id"])
            status = "no-filings-found"
        else:
            status = "ok"

        enriched = []
        for filing in filings:
            enriched_filing = dict(filing)
            enriched_filing["people"] = []
            enriched_filing["parse_status"] = "not_applicable"
            enriched_filing["warnings"] = []

            if should_parse_people(enriched_filing):
                parsed = extract_remuneration_rows(enriched_filing.get("href"))
                enriched_filing["people"] = parsed.get("people", [])
                enriched_filing["parse_status"] = parsed.get("parse_status", "error")
                enriched_filing["warnings"] = parsed.get("warnings", [])

            enriched.append(enriched_filing)

        print(f"  -> {len(enriched)} filings ({status})")
        results.append(
            {
                "id": band["id"],
                "name": band["name"],
                "province": band["province"],
                "filings": enriched,
                "status": status,
                "scraped": utc_now(),
            }
        )

        time.sleep(float(os.getenv("OPENBAND_REQUEST_DELAY", "1")))

    output = {
        "generated": utc_now(),
        "band_count": len(results),
        "error_count": errors,
        "bands": results,
    }

    with open("data.json", "w", encoding="utf-8") as handle:
        json.dump(output, handle, ensure_ascii=False, indent=2)

    print(f"\nDone. {len(results)} bands scraped, {errors} errors.")
    print("Saved to data.json")


if __name__ == "__main__":
    main()
