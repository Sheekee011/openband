from http.server import BaseHTTPRequestHandler
import json
import requests
import pdfplumber
import io
import re


def extract_money(value):
    if not value:
        return 0

    value = value.replace('$', '').replace(',', '').strip()

    try:
        return float(value)
    except:
        return 0


def parse_pdf(pdf_url):
    response = requests.get(pdf_url, timeout=30)
    response.raise_for_status()

    pdf_data = io.BytesIO(response.content)
    rows = []

    with pdfplumber.open(pdf_data) as pdf:
        text = ""

        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text += page_text + "\n"

    lines = text.splitlines()

    for line in lines:
        line = re.sub(r'\s+', ' ', line).strip()
        money = re.findall(r'\$?[\d,]+(?:\.\d{2})?', line)

        if len(money) >= 2:
            rows.append({
                "raw": line,
                "values": money
            })

    return rows


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length)
            data = json.loads(body)

            pdf_url = data.get('pdfUrl')

            if not pdf_url:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({
                    "error": "Missing pdfUrl"
                }).encode())
                return

            parsed = parse_pdf(pdf_url)

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            self.wfile.write(json.dumps({
                "success": True,
                "data": parsed
            }).encode())

        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": False,
                "error": str(e)
            }).encode())