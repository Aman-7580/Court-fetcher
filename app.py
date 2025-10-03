# app.py
import os
import sqlite3
import datetime
from flask import Flask, request, jsonify, send_from_directory, render_template, g
import requests
from bs4 import BeautifulSoup

BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, 'data')
PDF_DIR = os.path.join(DATA_DIR, 'pdfs')
DB_PATH = os.path.join(DATA_DIR, 'db.sqlite3')

app = Flask(__name__, template_folder='templates')
os.makedirs(PDF_DIR, exist_ok=True)

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db

def init_db():
    with app.app_context():
        db = get_db()
        db.execute('''
        CREATE TABLE IF NOT EXISTS queries(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_type TEXT,
            case_number TEXT,
            year TEXT,
            parties TEXT,
            filing_date TEXT,
            next_hearing TEXT,
            status TEXT,
            pdf_path TEXT,
            raw_response TEXT,
            created_at TEXT
        )
        ''')
        db.commit()

init_db()

# Small helper: create a tiny valid PDF file for demo (only if not present)
def ensure_demo_pdf(path):
    if not os.path.exists(path):
        pdf_content = b'%PDF-1.1\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Count 1 /Kids [3 0 R] >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>\nendobj\n4 0 obj\n<< /Length 55 >>\nstream\nBT /F1 24 Tf 100 700 Td (Sample judgment) Tj ET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f \n0000000010 00000 n \n0000000066 00000 n \n0000000123 00000 n \n0000000200 00000 n \ntrailer\n<< /Root 1 0 R /Size 5 >>\nstartxref\n279\n%%EOF'
        with open(path, 'wb') as f:
            f.write(pdf_content)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/search', methods=['POST'])
def api_search():
    # Accept form or JSON
    case_type = request.form.get('case_type') or (request.get_json() or {}).get('case_type')
    case_number = request.form.get('case_number') or (request.get_json() or {}).get('case_number')
    year = request.form.get('year') or (request.get_json() or {}).get('year')

    if not (case_type and case_number and year):
        return jsonify({'error': 'Please provide case_type, case_number and year'}), 400

    # MVP: demo fetcher — replace with real court-specific scraper later
    parsed = demo_fetcher(case_type, case_number, year)

    # Save results + raw response in DB, and create demo PDF
    db = get_db()
    cur = db.cursor()
    now = datetime.datetime.utcnow().isoformat()
    pdf_name = f"{case_type}_{case_number}_{year}.pdf"
    pdf_path = os.path.join(PDF_DIR, pdf_name)
    ensure_demo_pdf(pdf_path)

    cur.execute(
        'INSERT INTO queries(case_type,case_number,year,parties,filing_date,next_hearing,status,pdf_path,raw_response,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)',
        (case_type, case_number, year, parsed.get('parties'), parsed.get('filing_date'),
         parsed.get('next_hearing'), parsed.get('status'), pdf_name, parsed.get('raw'), now)
    )
    db.commit()
    qid = cur.lastrowid

    return jsonify({
        'id': qid,
        'parties': parsed.get('parties'),
        'filing_date': parsed.get('filing_date'),
        'next_hearing': parsed.get('next_hearing'),
        'status': parsed.get('status'),
        'pdf_url': f'/download_pdf/{qid}'
    })

@app.route('/download_pdf/<int:qid>')
def download_pdf(qid):
    db = get_db()
    cur = db.execute('SELECT pdf_path FROM queries WHERE id=?', (qid,))
    row = cur.fetchone()
    if not row:
        return 'Not found', 404
    return send_from_directory(PDF_DIR, row['pdf_path'], as_attachment=True)

def demo_fetcher(case_type, case_number, year):
    """
    Simulated fetcher: returns a parsed structure and a raw HTML string.
    Replace this function with a real scraper for a specific court portal.
    """
    raw = f"<html><body><h1>Case {case_type} {case_number}/{year}</h1><p>Demo raw HTML</p></body></html>"
    return {
        'parties': 'Alice v Bob',
        'filing_date': '2024-01-01',
        'next_hearing': '2025-01-01',
        'status': 'Listed',
        'raw': raw
    }

@app.teardown_appcontext
def close_conn(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
