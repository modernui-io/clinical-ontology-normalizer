#!/usr/bin/env python3
"""CLI tool for physician annotation of assertion classifier predictions.

Loads the sample JSONL from sample_assertion_eval.py and presents each
unannotated case for single-key annotation. Saves incrementally.

Keys:
    p = PRESENT        a = ABSENT        s = POSSIBLE
    h = HYPOTHETICAL   c = CONDITIONAL   f = FAMILY_HISTORY
    r = HISTORICAL     = = agree with classifier prediction
    q = quit (progress saved)
    u = undo last annotation

Usage:
    cd backend
    uv run python3 scripts/annotate_assertions.py
"""

import json
import sys
from pathlib import Path

SAMPLE_PATH = Path(__file__).parent.parent / "data" / "benchmarks" / "assertion_eval_sample.jsonl"
ANNOTATED_PATH = Path(__file__).parent.parent / "data" / "benchmarks" / "assertion_eval_annotated.jsonl"

KEY_MAP = {
    "p": "present",
    "a": "absent",
    "s": "possible",
    "h": "hypothetical",
    "c": "conditional",
    "f": "family_history",
    "r": "historical",
}

ASSERTION_COLORS = {
    "present": "\033[32m",     # green
    "absent": "\033[31m",      # red
    "possible": "\033[33m",    # yellow
    "hypothetical": "\033[35m",  # magenta
    "conditional": "\033[36m",   # cyan
    "family_history": "\033[34m",  # blue
    "historical": "\033[90m",    # gray
}
RESET = "\033[0m"
BOLD = "\033[1m"
UNDERLINE = "\033[4m"


def colorize(text: str, assertion: str) -> str:
    color = ASSERTION_COLORS.get(assertion, "")
    return f"{color}{text}{RESET}" if color else text


def load_samples() -> list[dict]:
    if not SAMPLE_PATH.exists():
        print(f"Sample file not found: {SAMPLE_PATH}")
        print("Run sample_assertion_eval.py first.")
        sys.exit(1)
    with open(SAMPLE_PATH) as f:
        return [json.loads(line) for line in f if line.strip()]


def load_annotated() -> dict[str, dict]:
    """Load already-annotated items, keyed by mention_id."""
    if not ANNOTATED_PATH.exists():
        return {}
    annotated = {}
    with open(ANNOTATED_PATH) as f:
        for line in f:
            if line.strip():
                item = json.loads(line)
                annotated[item["mention_id"]] = item
    return annotated


def save_annotated(items: list[dict]):
    """Write all annotated items to disk."""
    with open(ANNOTATED_PATH, "w") as f:
        for item in items:
            f.write(json.dumps(item) + "\n")


def display_case(idx: int, total: int, sample: dict, prediction: str):
    """Display a single annotation case."""
    print(f"\n{'='*70}")
    print(f"  {BOLD}[{idx+1}/{total}]{RESET}  note_type: {sample['note_type']}  "
          f"patient: {sample['patient_id']}")
    print(f"{'='*70}")

    # Show context with mention highlighted
    ctx = sample["context_window"]
    # Split on >>> and <<< markers
    parts = ctx.split(">>>")
    if len(parts) == 2:
        before = parts[0]
        rest = parts[1].split("<<<")
        mention = rest[0]
        after = rest[1] if len(rest) > 1 else ""
        print(f"\n  {before}{BOLD}{UNDERLINE}{mention}{RESET}{after}")
    else:
        print(f"\n  {ctx}")

    print(f"\n  Mention: {BOLD}{sample['mention_text']}{RESET}")
    print(f"  Classifier: {colorize(prediction, prediction)} "
          f"(conf={sample['classifier_confidence']:.2f})")
    if sample.get("experiencer") and sample["experiencer"] != "patient":
        print(f"  Experiencer: {sample['experiencer']}")

    print(f"\n  {BOLD}Label:{RESET} [p]resent [a]bsent po[s]sible "
          f"[h]ypothetical [c]onditional [f]amily_history histo[r]ical")
    print(f"         [=] agree with classifier   [u]ndo   [q]uit")


def main():
    samples = load_samples()
    annotated = load_annotated()

    # Build ordered list: annotated items first (preserving order), then unannotated
    annotated_list = [annotated[s["mention_id"]] for s in samples
                      if s["mention_id"] in annotated]

    # Find unannotated
    unannotated = [s for s in samples if s["mention_id"] not in annotated]

    done = len(annotated_list)
    total = len(samples)
    print(f"\nAssertion Annotation Tool")
    print(f"Annotated: {done}/{total}  |  Remaining: {total - done}")

    if done == total:
        print("All samples annotated! Run score_assertion_eval.py to compute metrics.")
        return

    for i, sample in enumerate(unannotated):
        global_idx = done + i
        prediction = sample["classifier_prediction"]
        display_case(global_idx, total, sample, prediction)

        while True:
            try:
                key = input(f"\n  > ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\n\nSaving and exiting...")
                save_annotated(annotated_list)
                return

            if key == "q":
                print(f"\nSaved {len(annotated_list)}/{total} annotations.")
                save_annotated(annotated_list)
                return
            elif key == "u":
                if annotated_list:
                    undone = annotated_list.pop()
                    del annotated[undone["mention_id"]]
                    done -= 1
                    print(f"  Undone: {undone['mention_text']} "
                          f"(was {undone['gold_label']})")
                    # Re-display current case
                    display_case(global_idx, total, sample, prediction)
                else:
                    print("  Nothing to undo.")
                continue
            elif key == "=":
                gold = prediction
            elif key in KEY_MAP:
                gold = KEY_MAP[key]
            else:
                print(f"  Invalid key '{key}'. Use p/a/s/h/c/f/r/=/u/q")
                continue

            # Record annotation
            annotated_sample = dict(sample)
            annotated_sample["gold_label"] = gold
            annotated_list.append(annotated_sample)
            annotated[sample["mention_id"]] = annotated_sample
            done += 1

            agree = "==" if gold == prediction else "!="
            print(f"  -> {colorize(gold, gold)} {agree} classifier ({prediction})")
            break

    # All done
    save_annotated(annotated_list)
    print(f"\nAll {total} samples annotated!")
    print(f"Run: uv run python3 scripts/score_assertion_eval.py")


if __name__ == "__main__":
    main()
