"""Compatibility launcher for the OpenBand scraper.

The main scraper currently builds a Responses API payload using `max_tokens`.
The Responses API expects `max_output_tokens`, so this launcher patches that
request body before it is sent and then runs scraper.main().
"""

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

if __name__ == "__main__":
    scraper.main()
