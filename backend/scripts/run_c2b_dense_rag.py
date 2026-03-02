#!/usr/bin/env python3
"""C2b Dense Retrieval baseline for ClinicalBench.

Replaces C2's TF-IDF/keyword retrieval with Contriever dense embeddings.
Everything else (prompt template, LLM, scoring) is identical to C2.

Usage (inside Docker):
    uv run python3 scripts/run_c2b_dense_rag.py

Produces:
    data/benchmarks/results/condition_C2b_dense_rag.json
    data/benchmarks/results/c2b_dense_rag_checkpoint.jsonl
"""

import json
import logging
import os
import sys
import time

import anthropic
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("c2b_dense_rag")

# ── Constants (match C2) ──
MAX_EVIDENCE_CHARS = 6000
MAX_CHUNKS = 10
CHUNK_TOKENS = 256
CHUNK_OVERLAP = 64
MODEL = "claude-opus-4-20250514"

SYSTEM_PROMPT = """\
You are a clinical reasoning assistant answering questions about a specific patient.
Use ONLY the provided evidence to answer. Be precise and concise.
If the evidence is insufficient, say so rather than guessing.
Answer in 1-3 sentences. Do not hedge unnecessarily when the evidence is clear."""

RESULTS_DIR = "data/benchmarks/results"
CHECKPOINT_PATH = os.path.join(RESULTS_DIR, "c2b_dense_rag_checkpoint.jsonl")
RESULT_PATH = os.path.join(RESULTS_DIR, "condition_C2b_dense_rag.json")
# epikg-benchmark may not be available inside Docker — write if exists
_epikg_base = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "epikg-benchmark", "results", "opus",
)
EPIKG_RESULT_PATH = os.path.join(_epikg_base, "C2b_dense_rag.json") if os.path.isdir(_epikg_base) else None


# ── Evaluator (v2) ──

# Try to import from epikg-benchmark (host) or inline fallback (Docker)
_epikg_paths = [
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "epikg-benchmark"),
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "epikg-benchmark"),
]
_evaluator_imported = False
for _p in _epikg_paths:
    if os.path.isdir(os.path.join(_p, "clinicalbench")):
        sys.path.insert(0, _p)
        try:
            from clinicalbench.evaluator import score_answer  # noqa: E402
            _evaluator_imported = True
            break
        except ImportError:
            pass

if not _evaluator_imported:
    # Inline the v2 evaluator (identical logic, standalone function)
    import re as _re

    _ABSTENTION_PATTERNS = [
        _re.compile(r'\b(?:notes?|records?|documentation)\b.*\b(?:do(?:es)?\s+not|lack[s]?|fail[s]?\s+to)\s+(?:mention|contain|include|provide|document|address|specify)', _re.IGNORECASE),
        _re.compile(r'\bno\s+(?:mention|information|data)\s+(?:of|about|regarding|concerning)\b', _re.IGNORECASE),
        _re.compile(r'\b(?:cannot|can\'?t|unable\s+to)\s+(?:determine|assess|evaluate|answer|ascertain|establish)\b', _re.IGNORECASE),
        _re.compile(r'\b(?:insufficient|inadequate)\s+(?:evidence|information|data|documentation)\b', _re.IGNORECASE),
        _re.compile(r'\bnot\s+(?:mentioned|documented|provided|available|specified|addressed|included)\b', _re.IGNORECASE),
        _re.compile(r'\b(?:information|evidence|data)\s+is\s+(?:missing|unavailable|lacking|absent|not\s+available)\b', _re.IGNORECASE),
        _re.compile(r'\b(?:provided|available)\s+(?:notes?|records?)\s+do(?:es)?\s+not\b', _re.IGNORECASE),
    ]
    _CLINICAL_CLAIM_PATTERNS = [
        _re.compile(r'\bpatient\s+(?:does\s+not|has\s+not|is\s+not|did\s+not)\b', _re.IGNORECASE),
        _re.compile(r'\b(?:denies|denied|ruled\s+out)\b', _re.IGNORECASE),
        _re.compile(r'\bno\s+evidence\s+of\b', _re.IGNORECASE),
        _re.compile(r'\bpatient\s+has\s+no\b', _re.IGNORECASE),
        _re.compile(r'^No[.,]', _re.IGNORECASE),
    ]

    def _strip_evidence_echo(text: str) -> str:
        stripped = text.strip()
        preamble_starts = ("Assertion Notes", "=== TEMPORAL STATUS", "=== CURRENT STATUS", "=== CROSS-ADMISSION")
        if not any(stripped.startswith(p) for p in preamble_starts):
            return text
        parts = _re.split(r"\n\n+", text)
        for part in parts[1:]:
            s = part.strip()
            if not s:
                continue
            first_line = s.split("\n")[0].strip()
            if first_line.startswith(("-", "*", ">", "=", "#", "|")):
                continue
            if first_line.startswith("Assertion"):
                continue
            return s
        lines = text.split("\n")
        for i, line in enumerate(lines):
            s = line.strip()
            if i > 0 and s and not s.startswith(("-", "*", ">", "Assertion", "=", "#", "|")):
                return "\n".join(lines[i:]).strip()
        return text

    def _is_abstention(text: str) -> bool:
        clean = _re.sub(r'\*+', '', text)
        lead = clean[:200]
        for pat in _CLINICAL_CLAIM_PATTERNS:
            if pat.search(lead):
                return False
        for pat in _ABSTENTION_PATTERNS:
            if pat.search(clean):
                return True
        return False

    def _make_patterns(keywords):
        return [_re.compile(r'\b' + _re.escape(kw) + r'\b') for kw in keywords]

    def _has_match(text, patterns):
        return any(p.search(text) for p in patterns)

    def score_answer(category: str, expected_answer: str, predicted_answer: str) -> tuple[bool, float]:
        expected_lower = expected_answer.lower()
        predicted_clean = _strip_evidence_echo(predicted_answer)
        predicted_lower = predicted_clean.lower()
        if _is_abstention(predicted_clean):
            return False, 0.0
        if category == "negation":
            kws = ["no", "negative", "denies", "absent", "not", "none", "nkda", "nothing", "cannot", "denied", "ruled out", "no evidence"]
            pats = _make_patterns(kws)
            return (_has_match(predicted_lower, pats) == _has_match(expected_lower, pats)), 1.0 if (_has_match(predicted_lower, pats) == _has_match(expected_lower, pats)) else 0.0
        elif category == "uncertainty":
            kws = ["uncertain", "possible", "suspected", "pending", "cannot rule out", "unclear", "equivocal", "likely", "probable", "concerning for", "suggestive", "may be", "may indicate", "not confirmed", "not definitively", "cannot exclude", "cannot be confirmed", "provisional", "tentative"]
            correct = _has_match(predicted_lower, _make_patterns(kws))
            return correct, 1.0 if correct else 0.0
        elif category == "family_history":
            fh_pats = _make_patterns(["family", "mother", "father", "sister", "brother", "relative"])
            dist = _has_match(predicted_lower, fh_pats)
            pneg = [_re.compile(r'\bpatient does not\b'), _re.compile(r"\bpatient's\b.*\bnormal\b"), _re.compile(r'\bno\b.*\bin patient\b')]
            clear = _has_match(predicted_lower, pneg) or "family history only" in predicted_lower
            correct = dist or clear
            return correct, 1.0 if correct else 0.0
        elif category == "conditional":
            correct = _has_match(predicted_lower, _make_patterns(["if", "conditional", "pending", "depending", "only if"]))
            return correct, 1.0 if correct else 0.0
        elif category in ("current_state", "historical"):
            cur_pats = _make_patterns(["current", "active", "present", "ongoing", "is on"])
            hist_pats = _make_patterns(["was", "former", "previously", "resolved", "discontinued", "prior"])
            ans = predicted_lower
            for sn in ["past medical history", "history of present illness", "history of"]:
                ans = ans.replace(sn, "")
            is_cur = _has_match(ans, cur_pats)
            is_hist = _has_match(ans, hist_pats)
            strong = _re.compile(r'\bcurrently active\b|\bis currently\b|\bcurrently present\b|\bis active\b')
            if strong.search(predicted_lower):
                is_cur, is_hist = True, False
            if category == "current_state":
                correct = is_cur and not is_hist
            else:
                correct = is_hist
            return correct, 1.0 if correct else 0.0
        elif category == "change":
            change_kws = ["increased", "decreased", "worsened", "improved", "new", "changed", "elevated", "rose", "fell", "higher", "lower", "progression", "resolved", "developed"]
            correct = _has_match(predicted_lower, _make_patterns(change_kws))
            return correct, 1.0 if correct else 0.0
        elif category == "duration":
            dur_pats = [_re.compile(r'\b\d+\s*(?:day|week|month|year|hour|minute|hr|min|wk|mo|yr)s?\b', _re.IGNORECASE), _re.compile(r'\b(?:since|duration|for the (?:past|last)|over the (?:past|last)|x\s*\d+)\b', _re.IGNORECASE), _re.compile(r'\b(?:chronic|acute|longstanding|long-standing|brief|prolonged|transient|intermittent)\b', _re.IGNORECASE)]
            correct = any(p.search(predicted_lower) for p in dur_pats)
            return correct, 1.0 if correct else 0.0
        elif category == "sequence":
            seq_kws = ["before", "after", "following", "prior to", "preceded", "subsequently", "then", "first", "second", "initially", "later", "earlier"]
            correct = _has_match(predicted_lower, _make_patterns(seq_kws))
            return correct, 1.0 if correct else 0.0
        else:
            return predicted_lower.strip() != "", 1.0 if predicted_lower.strip() else 0.0


# ── Chunking ──

def chunk_text(text: str, tokenizer, chunk_tokens: int = CHUNK_TOKENS, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Sliding-window chunking using the model's tokenizer."""
    token_ids = tokenizer.encode(text)
    chunks = []
    start = 0
    while start < len(token_ids):
        end = start + chunk_tokens
        chunk_ids = token_ids[start:end]
        chunk_text = tokenizer.decode(chunk_ids)
        if chunk_text.strip():
            chunks.append(chunk_text.strip())
        if end >= len(token_ids):
            break
        start += chunk_tokens - overlap
    return chunks


# ── Dense retrieval ──

def retrieve_dense(
    query: str,
    chunk_list: list[tuple[str, int, str, str]],  # (doc_id, chunk_idx, text, note_type)
    embeddings: np.ndarray,
    model,
    max_chars: int = MAX_EVIDENCE_CHARS,
    max_chunks: int = MAX_CHUNKS,
) -> str:
    """Retrieve top-k chunks by cosine similarity, up to max_chars."""
    query_emb = model.encode([query], normalize_embeddings=True, show_progress_bar=False)
    # embeddings already normalized during build
    scores = (embeddings @ query_emb.T).flatten()
    ranked_idxs = np.argsort(-scores)

    evidence_parts = []
    total_chars = 0
    for idx in ranked_idxs:
        if len(evidence_parts) >= max_chunks:
            break
        doc_id, chunk_idx, text, note_type = chunk_list[idx]
        if total_chars + len(text) > max_chars:
            # Include partial if we have nothing yet
            if not evidence_parts:
                text = text[:max_chars]
            else:
                break
        evidence_parts.append(f"[document:{doc_id}#chunk{chunk_idx}]: {text}")
        total_chars += len(text)

    return "=== Retrieved Document Context ===\n" + "\n".join(evidence_parts)


# ── Checkpoint ──

def load_checkpoint(path: str) -> set[str]:
    """Load completed question IDs from JSONL checkpoint."""
    done = set()
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    done.add(rec["question_id"])
                except (json.JSONDecodeError, KeyError):
                    continue
    return done


def append_checkpoint(path: str, record: dict):
    """Append a single result to the JSONL checkpoint."""
    with open(path, "a") as f:
        f.write(json.dumps(record) + "\n")


# ── Main ──

def main():
    t_start = time.time()

    # ── Load questions ──
    questions = []
    for task_file in ["data/benchmarks/task_a.json", "data/benchmarks/task_b.json"]:
        if not os.path.exists(task_file):
            logger.error("Missing %s", task_file)
            sys.exit(1)
        with open(task_file) as f:
            data = json.load(f)
        for q in data["questions"]:
            patient_id = f"MIMIC-{q['mimic_subject_id']}"
            questions.append({
                "question_id": q["question_id"],
                "question": q["question"],
                "expected_answer": q["expected_answer"],
                "category": q.get("subtype", "unknown"),
                "patient_id": patient_id,
            })
    logger.info("Loaded %d questions", len(questions))

    # ── Connect to DB ──
    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg2://postgres:postgres@postgres:5432/clinical_ontology",
    )
    db_url = db_url.replace("asyncpg", "psycopg2").replace("postgresql://", "postgresql+psycopg2://")
    from sqlalchemy import create_engine, text as sa_text
    engine = create_engine(db_url)

    # ── Load documents per patient ──
    patient_ids = sorted(set(q["patient_id"] for q in questions))
    logger.info("Loading documents for %d patients", len(patient_ids))

    patient_docs: dict[str, list[tuple[str, str, str]]] = {}  # pid -> [(doc_id, text, note_type)]
    with engine.connect() as conn:
        for pid in patient_ids:
            rows = conn.execute(
                sa_text("SELECT id, text, note_type FROM documents WHERE patient_id = :pid AND deleted_at IS NULL"),
                {"pid": pid},
            ).fetchall()
            patient_docs[pid] = [(str(r[0]), r[1], r[2]) for r in rows]
    total_docs = sum(len(v) for v in patient_docs.values())
    logger.info("Loaded %d documents across %d patients", total_docs, len(patient_docs))

    # ── Load embedding model ──
    logger.info("Loading sentence-transformers model...")
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        logger.error("sentence-transformers not installed. Run: uv pip install sentence-transformers")
        sys.exit(1)

    try:
        st_model = SentenceTransformer("nthakur/contriever-base-msmarco")
        logger.info("Loaded Contriever model")
    except Exception as e:
        logger.warning("Contriever download failed (%s), falling back to all-MiniLM-L6-v2", e)
        st_model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Loaded MiniLM fallback model")

    tokenizer = st_model.tokenizer

    # ── Chunk and embed per patient ──
    logger.info("Chunking and embedding documents...")
    patient_index: dict[str, tuple[list[tuple[str, int, str, str]], np.ndarray]] = {}

    for pi, pid in enumerate(patient_ids):
        docs = patient_docs.get(pid, [])
        chunk_list: list[tuple[str, int, str, str]] = []  # (doc_id, chunk_idx, text, note_type)
        for doc_id, doc_text, note_type in docs:
            chunks = chunk_text(doc_text, tokenizer)
            for ci, ct in enumerate(chunks):
                chunk_list.append((doc_id, ci, ct, note_type))

        if not chunk_list:
            patient_index[pid] = ([], np.zeros((0, 0)))
            continue

        texts = [c[2] for c in chunk_list]
        embeddings = st_model.encode(texts, batch_size=32, normalize_embeddings=True, show_progress_bar=False)
        patient_index[pid] = (chunk_list, np.array(embeddings, dtype=np.float32))
        if (pi + 1) % 10 == 0:
            logger.info("  Embedded %d/%d patients (%d chunks so far)", pi + 1, len(patient_ids),
                        sum(len(v[0]) for v in patient_index.values()))

    total_chunks = sum(len(v[0]) for v in patient_index.values())
    logger.info("Built dense index: %d chunks across %d patients", total_chunks, len(patient_index))

    # ── Checkpoint resume ──
    done_ids = load_checkpoint(CHECKPOINT_PATH)
    if done_ids:
        logger.info("Resuming: %d questions already completed", len(done_ids))

    # ── Question loop ──
    client = anthropic.Anthropic()
    results = []
    n_correct = 0
    n_done = 0

    for i, q in enumerate(questions):
        qid = q["question_id"]

        # Skip if already done
        if qid in done_ids:
            continue

        pid = q["patient_id"]
        chunk_list, embeddings = patient_index.get(pid, ([], np.zeros((0, 0))))

        # Retrieve evidence
        if chunk_list:
            evidence = retrieve_dense(q["question"], chunk_list, embeddings, st_model)
        else:
            evidence = "=== Retrieved Document Context ===\n[No documents available]"

        # Build prompt (identical to C2)
        user_prompt = (
            f"Patient evidence:\n{evidence}\n\n"
            f"Question: {q['question']}\n\n"
            f"Answer concisely based on the evidence above."
        )

        # Call Opus
        t0 = time.time()
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=512,
                temperature=0.0,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            answer = response.content[0].text
            error = None
        except Exception as e:
            logger.error("API error on %s: %s", qid, e)
            answer = ""
            error = str(e)
        latency_ms = (time.time() - t0) * 1000

        # Score
        correct, score = score_answer(q["category"], q["expected_answer"], answer)

        result = {
            "condition": "C2b_dense_rag",
            "question_id": qid,
            "predicted_answer": answer[:500],
            "expected_answer": q["expected_answer"][:500],
            "correct": correct,
            "score": score,
            "category": q["category"],
            "latency_ms": latency_ms,
            "error": error,
            "random_seed": 42,
        }
        results.append(result)
        append_checkpoint(CHECKPOINT_PATH, result)

        n_done += 1
        if correct:
            n_correct += 1

        if n_done % 10 == 0 or n_done <= 3:
            logger.info(
                "[%d/%d] qid=%s correct=%s acc_so_far=%.1f%% latency=%.0fms",
                n_done, len(questions) - len(done_ids), qid, correct,
                100 * n_correct / n_done, latency_ms,
            )

    # ── Also load checkpoint results for full accounting ──
    all_results = []
    if os.path.exists(CHECKPOINT_PATH):
        with open(CHECKPOINT_PATH) as f:
            for line in f:
                line = line.strip()
                if line:
                    all_results.append(json.loads(line))

    duration = time.time() - t_start
    total = len(all_results)
    total_correct = sum(1 for r in all_results if r["correct"])

    # ── Category breakdown ──
    from collections import defaultdict
    cat_correct = defaultdict(int)
    cat_total = defaultdict(int)
    per_question = {}
    for r in all_results:
        cat = r["category"]
        cat_total[cat] += 1
        if r["correct"]:
            cat_correct[cat] += 1
        per_question[r["question_id"]] = {
            "correct": r["correct"],
            "answer": r["predicted_answer"],
            "expected": r["expected_answer"],
        }

    category_scores = {
        cat: cat_correct[cat] / cat_total[cat] if cat_total[cat] > 0 else 0.0
        for cat in sorted(cat_total)
    }

    accuracy = total_correct / total if total > 0 else 0.0
    logger.info("=" * 60)
    logger.info("C2b Dense RAG — FINAL RESULTS")
    logger.info("Accuracy: %.1f%% (%d/%d)", 100 * accuracy, total_correct, total)
    logger.info("Duration: %.0fs", duration)
    for cat in sorted(category_scores):
        logger.info("  %-15s %.1f%% (%d/%d)", cat, 100 * category_scores[cat], cat_correct[cat], cat_total[cat])
    logger.info("=" * 60)

    # ── Write result JSON (matches C2 format) ──
    result_json = {
        "model": MODEL,
        "provider": "anthropic",
        "condition": "C2b_dense_rag",
        "retrieval_model": "nthakur/contriever-base-msmarco",
        "chunk_tokens": CHUNK_TOKENS,
        "chunk_overlap": CHUNK_OVERLAP,
        "max_evidence_chars": MAX_EVIDENCE_CHARS,
        "n_questions": total,
        "duration_s": duration,
        "accuracy": accuracy,
        "category_scores": category_scores,
        "per_question": per_question,
    }
    with open(RESULT_PATH, "w") as f:
        json.dump(result_json, f, indent=2)
    logger.info("Wrote %s", RESULT_PATH)

    # ── Write epikg-benchmark format (if directory exists) ──
    if EPIKG_RESULT_PATH:
        epikg_predictions = []
        for r in all_results:
            epikg_predictions.append({
                "question_id": r["question_id"],
                "predicted_answer": r["predicted_answer"],
                "correct": r["correct"],
                "score": r["score"],
                "category": r["category"],
            })
        epikg_json = {
            "model": "claude-opus-4-6",
            "condition": "C2b_dense_rag",
            "n_predictions": len(epikg_predictions),
            "predictions": epikg_predictions,
        }
        os.makedirs(os.path.dirname(EPIKG_RESULT_PATH), exist_ok=True)
        with open(EPIKG_RESULT_PATH, "w") as f:
            json.dump(epikg_json, f, indent=2)
        logger.info("Wrote %s", EPIKG_RESULT_PATH)
    else:
        logger.info("epikg-benchmark dir not found — skipping epikg export. Copy results manually.")


if __name__ == "__main__":
    main()
