"""
White Rose Publication – Flask Backend
Reads combined_papers_theses.csv and exposes a REST search API.

Run:  python app.py
Endpoints:
  GET /api/search?q=&type=all|article|thesis|report|dataset&page=1&per_page=9
  GET /api/stats
  GET /api/recent?limit=12
  GET /api/health
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import csv, ast, re, os, math, sys
from datetime import datetime

# Raise CSV field size limit — some abstract fields exceed the 128KB default
csv.field_size_limit(min(sys.maxsize, 2147483647))

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# ── data path ─────────────────────────────────────────────────────────────────
DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "combined_papers_theses.csv")
PUBLICATIONS = []

# ── helpers ───────────────────────────────────────────────────────────────────

def parse_sets(raw):
    """
    The 'sets' column is a stringified dict, e.g.:
      {'status': 'pub', 'institution': 'Sheffield', 'unit': '...'}
    Extract 'institution' directly. Falls back to scanning the raw string.
    """
    try:
        d = ast.literal_eval(raw)
        inst = d.get("institution", "").strip()
        if inst:
            return inst
    except Exception:
        pass
    for uni in ("Leeds", "Sheffield", "York"):
        if uni.lower() in raw.lower():
            return uni
    return ""

def parse_date(raw):
    """Return ISO date string YYYY-MM-DD, or empty string."""
    if not raw:
        return ""
    raw = str(raw).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = re.search(r"\b(1\d{3}|20\d{2})\b", raw)
    return f"{m.group(1)}-01-01" if m else ""

def fmt_date(iso):
    """Format ISO date as '7 Jun 2002', Windows-safe (no %-d)."""
    if not iso:
        return ""
    try:
        dt = datetime.strptime(iso, "%Y-%m-%d")
        return f"{dt.day} {dt.strftime('%b')} {dt.year}"
    except ValueError:
        return iso

def parse_authors(raw):
    """Return a readable author string from a list-of-dicts or plain string."""
    try:
        authors = ast.literal_eval(raw)
        names = [a.get("name", "") for a in authors if isinstance(a, dict) and a.get("name")]
        if not names:
            return ""
        if len(names) == 1:
            return names[0]
        if len(names) <= 3:
            return ", ".join(names)
        return f"{names[0]} et al."
    except Exception:
        return str(raw)[:80] if raw else ""

def clean_html(text):
    """Strip HTML tags."""
    return re.sub(r"<[^>]+>", " ", str(text or "")).strip()

# ── load CSV ──────────────────────────────────────────────────────────────────

def load_data():
    global PUBLICATIONS
    if not os.path.exists(DATA_PATH):
        print(f"WARNING: CSV not found at {os.path.abspath(DATA_PATH)}")
        return

    with open(DATA_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=",")
        skipped = 0
        for row in reader:

            # skip blank-title rows
            title = str(row.get("title", "")).strip()
            if not title:
                skipped += 1
                continue

            # doc type — CSV has "Article", "Thesis", etc. (capitalised)
            raw_type = str(row.get("doctype", row.get("type", ""))).lower().strip()
            if "thesis" in raw_type or "thes" in raw_type:
                doc_type = "thesis"
            elif "report" in raw_type:
                doc_type = "report"
            elif "dataset" in raw_type or "data" in raw_type:
                doc_type = "dataset"
            else:
                doc_type = "article"

            # institution — parsed from the sets dict string
            inst_short = parse_sets(str(row.get("sets", "")))
            institution = f"University of {inst_short}" if inst_short else ""

            iso_date = parse_date(row.get("date", ""))

            description = clean_html(row.get("description", ""))
            if len(description) > 300:
                description = description[:297] + "…"

            PUBLICATIONS.append({
                "id":           row.get("id", ""),
                "title":        title,
                "authors":      parse_authors(row.get("authors", "")),
                "description":  description,
                "date":         iso_date,
                "date_raw":     row.get("date", ""),
                "type":         doc_type,
                "institution":  institution,
                "url":          str(row.get("url", "")),
                "doi":          str(row.get("doi", "")),
                "peer_reviewed": str(row.get("peerreviewed", "")).upper() == "TRUE",
            })

    PUBLICATIONS.sort(key=lambda p: p["date"], reverse=True)
    print(f"Loaded {len(PUBLICATIONS)} publications. (skipped {skipped} blank-title rows)")

load_data()

# ── search helper ─────────────────────────────────────────────────────────────

def matches(pub, q, doc_type):
    if doc_type and doc_type != "all" and pub["type"] != doc_type:
        return False
    if q:
        haystack = " ".join([
            pub["title"], pub["authors"],
            pub["description"], pub["institution"]
        ]).lower()
        for token in q.lower().split():
            if token not in haystack:
                return False
    return True

# ── CORS on every response ────────────────────────────────────────────────────

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"]  = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response

# ── routes ────────────────────────────────────────────────────────────────────

@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "publications": len(PUBLICATIONS)})


@app.route("/api/stats")
def stats():
    return jsonify({
        "total":          len(PUBLICATIONS),
        "universities":   3,
        "papers_per_day": "~40",
        "theses_per_day": "~2-3",
    })


@app.route("/api/recent")
def recent():
    limit = min(int(request.args.get("limit", 12)), 50)
    results = [{**p, "date_display": fmt_date(p["date"])} for p in PUBLICATIONS[:limit]]
    return jsonify(results)


@app.route("/api/search")
def search():
    q           = request.args.get("q", "").strip()
    doc_type    = request.args.get("type", "all").strip().lower()
    page        = max(1, int(request.args.get("page", 1)))
    per_page    = max(1, min(50, int(request.args.get("per_page", 9))))
    sort        = request.args.get("sort", "recent")
    inst_filter = request.args.get("institutions", "").strip()
    inst_list   = [i.strip() for i in inst_filter.split(",") if i.strip()] if inst_filter else []
    from_year   = int(request.args.get("from_year", 0))
    peer_only   = request.args.get("peer_only", "false").lower() == "true"

    filtered = []
    for p in PUBLICATIONS:
        if not matches(p, q, doc_type):
            continue
        if from_year and p["date"]:
            try:
                if int(p["date"][:4]) < from_year:
                    continue
            except ValueError:
                pass
        if inst_list:
            if not any(i.lower() in p["institution"].lower() for i in inst_list):
                continue
        if peer_only and not p["peer_reviewed"]:
            continue
        filtered.append(p)

    if sort == "oldest":
        filtered = sorted(filtered, key=lambda p: p["date"])

    total    = len(filtered)
    pages    = math.ceil(total / per_page) if total else 1
    page     = min(page, pages)
    start    = (page - 1) * per_page
    chunk    = filtered[start:start + per_page]
    items    = [{**p, "date_display": fmt_date(p["date"])} for p in chunk]

    return jsonify({
        "query":    q,
        "type":     doc_type,
        "total":    total,
        "page":     page,
        "pages":    pages,
        "per_page": per_page,
        "results":  items,
    })


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("  White Rose Publication API")
    print("  Running at http://localhost:5000")
    print("  Health:     http://localhost:5000/api/health")
    print("=" * 50 + "\n")
    app.run(debug=True, port=5000, host="0.0.0.0")