"""Local MIMIC-IV Note Viewer with full-text search. Run: python3 mimic_viewer.py"""

import json
import sqlite3
import html
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

DB_PATH = "/Users/alexstinard/projects/brainstorm/jan-14-2026/tools/mimic_notes.db"
PORT = 8899

VIEWER_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MIMIC-IV Note Viewer</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #09090b; color: #e4e4e7; overflow: hidden; height: 100vh; }

  .header { background: #18181b; border-bottom: 1px solid #27272a; padding: 16px 24px; }
  .header-top { display: flex; align-items: center; justify-content: space-between; }
  .header h1 { font-size: 20px; font-weight: 700; }
  .header h1 .sub { color: #71717a; font-weight: 400; font-size: 13px; margin-left: 8px; }

  .stats-row { display: flex; gap: 12px; margin-top: 10px; flex-wrap: wrap; }
  .stat-chip { background: #27272a; padding: 4px 12px; border-radius: 6px; font-size: 12px; color: #a1a1aa; }
  .stat-chip strong { color: #fafafa; margin-right: 4px; }

  .controls { display: flex; gap: 8px; margin-top: 12px; align-items: center; flex-wrap: wrap; }
  .search-input { flex: 1; min-width: 280px; padding: 9px 14px; background: #0f0f11; border: 1px solid #3f3f46; border-radius: 8px; color: #e4e4e7; font-size: 14px; outline: none; }
  .search-input:focus { border-color: #3b82f6; box-shadow: 0 0 0 2px rgba(59,130,246,0.15); }
  .search-input::placeholder { color: #52525b; }

  .filter-btn { padding: 7px 16px; border-radius: 6px; cursor: pointer; font-size: 12px; font-weight: 500; background: #27272a; color: #a1a1aa; border: 1px solid #3f3f46; transition: all 0.12s; }
  .filter-btn:hover { background: #3f3f46; color: #e4e4e7; }
  .filter-btn.active { background: #1e3a5f; color: #60a5fa; border-color: #3b82f6; }

  .search-btn { padding: 9px 20px; background: #2563eb; color: #fff; border: none; border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer; transition: background 0.12s; }
  .search-btn:hover { background: #1d4ed8; }
  .search-btn:disabled { background: #1e3a5f; cursor: wait; }

  .main { display: flex; height: calc(100vh - 140px); }

  .sidebar { width: 380px; border-right: 1px solid #27272a; overflow-y: auto; background: #0f0f11; flex-shrink: 0; }
  .note-item { padding: 12px 16px; border-bottom: 1px solid #1a1a1e; cursor: pointer; transition: background 0.08s; }
  .note-item:hover { background: #1a1a1e; }
  .note-item.active { background: #172554; border-left: 3px solid #3b82f6; }
  .note-item .row1 { display: flex; justify-content: space-between; align-items: center; }
  .note-item .nid { font-family: 'SF Mono', monospace; font-size: 11px; color: #71717a; }
  .note-item .badge { font-size: 10px; font-weight: 600; padding: 2px 8px; border-radius: 4px; }
  .badge.discharge { background: #052e16; color: #4ade80; }
  .badge.radiology { background: #0c1a2e; color: #60a5fa; }
  .badge.triage { background: #2e1a05; color: #fb923c; }
  .note-item .row2 { font-size: 11px; color: #71717a; margin-top: 4px; }
  .note-item .preview { font-size: 12px; color: #52525b; margin-top: 5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

  .content { flex: 1; overflow-y: auto; display: flex; flex-direction: column; }
  .note-top { padding: 18px 28px; background: #18181b; border-bottom: 1px solid #27272a; flex-shrink: 0; }
  .note-top h2 { font-size: 15px; font-weight: 600; }
  .note-top .meta { display: flex; gap: 16px; margin-top: 6px; font-size: 12px; color: #a1a1aa; flex-wrap: wrap; }
  .note-top .meta code { font-family: 'SF Mono', monospace; background: #27272a; padding: 1px 6px; border-radius: 4px; font-size: 11px; color: #d4d4d8; }
  .note-body { flex: 1; padding: 20px 28px; white-space: pre-wrap; font-family: 'SF Mono', 'Menlo', monospace; font-size: 13px; line-height: 1.75; color: #d4d4d8; overflow-y: auto; }
  .note-body .sh { color: #fbbf24; font-weight: 700; }
  .note-body mark { background: #854d0e; color: #fef3c7; padding: 1px 3px; border-radius: 2px; }

  .empty { display: flex; align-items: center; justify-content: center; height: 100%; color: #3f3f46; font-size: 14px; flex-direction: column; gap: 8px; }
  .empty .big { font-size: 40px; }

  .pager { display: flex; align-items: center; justify-content: center; gap: 8px; padding: 10px; border-top: 1px solid #27272a; background: #0f0f11; }
  .pager button { padding: 5px 14px; background: #27272a; color: #a1a1aa; border: 1px solid #3f3f46; border-radius: 6px; font-size: 12px; cursor: pointer; }
  .pager button:hover { background: #3f3f46; color: #e4e4e7; }
  .pager button:disabled { opacity: 0.3; cursor: default; }
  .pager .info { font-size: 12px; color: #71717a; }

  .loading { display: none; position: fixed; top: 50%; left: 50%; transform: translate(-50%,-50%); background: #18181b; border: 1px solid #3f3f46; padding: 24px 40px; border-radius: 12px; z-index: 100; text-align: center; }
  .loading.show { display: block; }
  .loading .spinner { width: 28px; height: 28px; border: 3px solid #3f3f46; border-top-color: #3b82f6; border-radius: 50%; animation: spin 0.7s linear infinite; margin: 0 auto 10px; }
  @keyframes spin { to { transform: rotate(360deg); } }

  ::-webkit-scrollbar { width: 7px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: #3f3f46; border-radius: 4px; }
</style>
</head>
<body>

<div class="header">
  <div class="header-top">
    <h1>MIMIC-IV Note Viewer <span class="sub" id="dbStats"></span></h1>
  </div>
  <div class="stats-row" id="statsRow"></div>
  <div class="controls">
    <input class="search-input" id="searchInput" placeholder="Search all notes... (e.g. pneumonia, chest pain, diabetes)" autofocus>
    <button class="filter-btn active" data-cat="all" onclick="setFilter('all', this)">All</button>
    <button class="filter-btn" data-cat="Discharge Summary" onclick="setFilter('Discharge Summary', this)">Discharge</button>
    <button class="filter-btn" data-cat="Radiology Report" onclick="setFilter('Radiology Report', this)">Radiology</button>
    <button class="filter-btn" data-cat="ED Triage" onclick="setFilter('ED Triage', this)">ED Triage</button>
    <button class="search-btn" id="searchBtn" onclick="doSearch()">Search</button>
  </div>
</div>

<div class="main">
  <div style="display:flex;flex-direction:column;width:380px;flex-shrink:0;">
    <div class="sidebar" id="sidebar">
      <div class="empty"><div class="big">&#128269;</div>Search to browse notes</div>
    </div>
    <div class="pager" id="pager" style="display:none;">
      <button id="prevBtn" onclick="changePage(-1)">&#8592; Prev</button>
      <span class="info" id="pageInfo"></span>
      <button id="nextBtn" onclick="changePage(1)">Next &#8594;</button>
    </div>
  </div>
  <div class="content" id="content">
    <div class="empty"><div class="big">&#128196;</div>Select a note to view</div>
  </div>
</div>

<div class="loading" id="loading"><div class="spinner"></div><div>Searching...</div></div>

<script>
let notes = [];
let totalResults = 0;
let currentPage = 0;
let currentFilter = 'all';
let currentQuery = '';
const PAGE_SIZE = 50;

const SECTION_HEADERS = [
  'Chief Complaint','Major Surgical','History of Present Illness','Past Medical History',
  'Social History','Family History','Physical Exam','Pertinent Results',
  'Brief Hospital Course','Medications on Admission','Discharge Medications',
  'Discharge Disposition','Discharge Diagnosis','Discharge Condition',
  'Discharge Instructions','Followup Instructions','EXAMINATION','INDICATION',
  'TECHNIQUE','COMPARISON','FINDINGS','IMPRESSION','Allergies','Attending',
  'Service','Facility','Active Issues','Assessment and Plan','Review of Systems',
  'Vitals','Labs','Imaging','Micro'
];
const sectionRegex = new RegExp('(^|\\n)(' + SECTION_HEADERS.join('|') + ')([:\\s])', 'gm');

async function fetchStats() {
  const r = await fetch('/api/stats');
  const d = await r.json();
  document.getElementById('dbStats').textContent = d.total.toLocaleString() + ' notes indexed';
  const row = document.getElementById('statsRow');
  row.innerHTML = '';
  for (const [cat, cnt] of Object.entries(d.categories)) {
    row.innerHTML += '<div class="stat-chip"><strong>' + cnt.toLocaleString() + '</strong>' + cat + '</div>';
  }
}

async function doSearch(page) {
  currentQuery = document.getElementById('searchInput').value.trim();
  if (page === undefined) { currentPage = 0; } else { currentPage = page; }

  document.getElementById('loading').classList.add('show');
  document.getElementById('searchBtn').disabled = true;

  const params = new URLSearchParams({
    q: currentQuery,
    category: currentFilter,
    offset: currentPage * PAGE_SIZE,
    limit: PAGE_SIZE,
  });

  try {
    const r = await fetch('/api/search?' + params);
    const d = await r.json();
    notes = d.notes;
    totalResults = d.total;
    renderSidebar();
    updatePager();
    if (notes.length > 0) selectNote(0);
    else {
      document.getElementById('content').innerHTML = '<div class="empty"><div class="big">&#128528;</div>No results found</div>';
    }
  } finally {
    document.getElementById('loading').classList.remove('show');
    document.getElementById('searchBtn').disabled = false;
  }
}

function renderSidebar() {
  const sb = document.getElementById('sidebar');
  if (notes.length === 0) {
    sb.innerHTML = '<div class="empty"><div class="big">&#128269;</div>No notes found</div>';
    return;
  }
  sb.innerHTML = notes.map((n, i) => {
    const bc = n.note_category.includes('Discharge') ? 'discharge' : n.note_category.includes('Radiology') ? 'radiology' : 'triage';
    const preview = n.text.replace(/\s+/g, ' ').trim().slice(0, 90);
    return '<div class="note-item" id="ni-' + i + '" onclick="selectNote(' + i + ')">' +
      '<div class="row1"><span class="nid">' + esc(n.note_id) + '</span><span class="badge ' + bc + '">' + esc(n.note_category) + '</span></div>' +
      '<div class="row2">Patient ' + esc(n.subject_id) + ' &middot; ' + esc(n.charttime || '—') + '</div>' +
      '<div class="preview">' + esc(preview) + '</div></div>';
  }).join('');
}

function selectNote(i) {
  document.querySelectorAll('.note-item').forEach(el => el.classList.remove('active'));
  const el = document.getElementById('ni-' + i);
  if (el) el.classList.add('active');

  const n = notes[i];
  let txt = esc(n.text);
  txt = txt.replace(sectionRegex, '$1<span class="sh">$2</span>$3');

  if (currentQuery) {
    const words = currentQuery.split(/\s+/).filter(w => w.length > 1);
    words.forEach(w => {
      const wr = new RegExp('(' + w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'gi');
      txt = txt.replace(wr, '<mark>$1</mark>');
    });
  }

  document.getElementById('content').innerHTML =
    '<div class="note-top"><h2>' + esc(n.note_category) + '</h2>' +
    '<div class="meta"><span>Note: <code>' + esc(n.note_id) + '</code></span>' +
    '<span>Patient: <code>' + esc(n.subject_id) + '</code></span>' +
    '<span>Admission: <code>' + esc(n.hadm_id || '—') + '</code></span>' +
    '<span>Chart: <code>' + esc(n.charttime || '—') + '</code></span></div></div>' +
    '<div class="note-body">' + txt + '</div>';
}

function updatePager() {
  const pager = document.getElementById('pager');
  if (totalResults <= PAGE_SIZE) { pager.style.display = 'none'; return; }
  pager.style.display = 'flex';
  const totalPages = Math.ceil(totalResults / PAGE_SIZE);
  document.getElementById('pageInfo').textContent =
    'Page ' + (currentPage + 1) + ' of ' + totalPages + ' (' + totalResults.toLocaleString() + ' results)';
  document.getElementById('prevBtn').disabled = currentPage === 0;
  document.getElementById('nextBtn').disabled = currentPage >= totalPages - 1;
}

function changePage(delta) {
  doSearch(currentPage + delta);
}

function setFilter(cat, btn) {
  currentFilter = cat;
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  doSearch();
}

function esc(s) {
  if (!s) return '';
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

document.getElementById('searchInput').addEventListener('keydown', e => {
  if (e.key === 'Enter') doSearch();
});

fetchStats();
doSearch();
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # quiet logs

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/" or parsed.path == "":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(VIEWER_HTML.encode())
            return

        if parsed.path == "/api/stats":
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM notes")
            total = c.fetchone()[0]
            c.execute("SELECT note_category, COUNT(*) FROM notes GROUP BY note_category")
            cats = {r[0]: r[1] for r in c.fetchall()}
            conn.close()
            self._json({"total": total, "categories": cats})
            return

        if parsed.path == "/api/search":
            params = parse_qs(parsed.query)
            q = params.get("q", [""])[0].strip()
            category = params.get("category", ["all"])[0]
            offset = int(params.get("offset", [0])[0])
            limit = min(int(params.get("limit", [50])[0]), 100)

            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            if q:
                # FTS5 search
                fts_query = " ".join(f'"{w}"' for w in q.split() if w)
                cat_clause = ""
                cat_params = []
                if category != "all":
                    cat_clause = "AND n.note_category = ?"
                    cat_params = [category]

                count_sql = f"""
                    SELECT COUNT(*) FROM notes_fts f
                    JOIN notes n ON n.id = f.rowid
                    WHERE notes_fts MATCH ? {cat_clause}
                """
                c.execute(count_sql, [fts_query] + cat_params)
                total = c.fetchone()[0]

                sql = f"""
                    SELECT n.* FROM notes_fts f
                    JOIN notes n ON n.id = f.rowid
                    WHERE notes_fts MATCH ? {cat_clause}
                    ORDER BY rank
                    LIMIT ? OFFSET ?
                """
                c.execute(sql, [fts_query] + cat_params + [limit, offset])
            else:
                cat_clause = ""
                cat_params = []
                if category != "all":
                    cat_clause = "WHERE note_category = ?"
                    cat_params = [category]

                c.execute(f"SELECT COUNT(*) FROM notes {cat_clause}", cat_params)
                total = c.fetchone()[0]

                c.execute(
                    f"SELECT * FROM notes {cat_clause} ORDER BY id LIMIT ? OFFSET ?",
                    cat_params + [limit, offset],
                )

            rows = c.fetchall()
            notes = [dict(r) for r in rows]
            # Truncate text for list view, full text for selected note
            for n in notes:
                if len(n.get("text", "")) > 50000:
                    n["text"] = n["text"][:50000] + "\n\n... [truncated at 50,000 chars]"

            conn.close()
            self._json({"notes": notes, "total": total})
            return

        self.send_error(404)

    def _json(self, data):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    print(f"MIMIC-IV Note Viewer starting on http://localhost:{PORT}")
    print(f"Database: {DB_PATH}")
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    try:
        import webbrowser
        webbrowser.open(f"http://localhost:{PORT}")
        print("Opened in browser. Press Ctrl+C to stop.")
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()
