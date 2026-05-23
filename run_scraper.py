"""Compatibility launcher for the OpenBand scraper.

Keeps the nightly run bounded. The scraper can discover the full filing archive,
but PDF table extraction is limited to the current filing year first so more
First Nations get displayable rows before older years are attempted.
"""

import os
import urllib.request

_real_urlopen = urllib.request.urlopen


def _patched_urlopen(request, *args, **kwargs):
    if isinstance(request, urllib.request.Request) and request.full_url == "https://api.openai.com/v1/responses":
        if request.data:
            request.data = request.data.replace(b'"max_tokens": 1000', b'"max_output_tokens": 1000')
    return _real_urlopen(request, *args, **kwargs)


urllib.request.urlopen = _patched_urlopen

import scraper  # noqa: E402

scraper.urllib.request.urlopen = _patched_urlopen

_ALLOWED_YEARS = {
    y.strip()
    for y in os.getenv("OPENBAND_PARSE_YEARS", "2024-2025").split(",")
    if y.strip()
}
_MAX_PDF_ATTEMPTS = int(os.getenv("OPENBAND_MAX_PDF_ATTEMPTS", "70"))
_attempts = {"count": 0}
_original_should_parse_people = scraper.should_parse_people
_original_extract_remuneration_rows = scraper.extract_remuneration_rows


def _bounded_should_parse_people(filing):
    if filing.get("year") not in _ALLOWED_YEARS:
        return False
    return _original_should_parse_people(filing)


def _bounded_extract_remuneration_rows(pdf_url):
    if _attempts["count"] >= _MAX_PDF_ATTEMPTS:
        return {
            "parse_status": "skipped_run_limit",
            "warnings": [f"Skipped after {_MAX_PDF_ATTEMPTS} PDF parse attempts in this run"],
            "people": [],
        }
    _attempts["count"] += 1
    print(f"  parsing PDF {_attempts['count']}/{_MAX_PDF_ATTEMPTS}")
    return _original_extract_remuneration_rows(pdf_url)


scraper.should_parse_people = _bounded_should_parse_people
scraper.extract_remuneration_rows = _bounded_extract_remuneration_rows

if __name__ == "__main__":
    print("OpenBand bounded run")
    print("  parse years:", ", ".join(sorted(_ALLOWED_YEARS)))
    print("  max PDF attempts:", _MAX_PDF_ATTEMPTS)
    scraper.main()
