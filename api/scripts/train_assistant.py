"""
Train the assistant's intent model and compare candidate featurizers.

Run from api/:  uv run python -m scripts.train_assistant [--activate] [--candidates tfidf,minilm,e5,labse,mpnet]

Data: hand-written seeds in assistant/training_data.py (English, Amharic, transliterated
Amharic), split by seed into train/val/test BEFORE augmentation, so templates and service
names in the test set are never seen in training. Admin-labelled chat messages are added
to the training split only, so test scores stay comparable between versions.

Candidates: char n-gram TF-IDF, several multilingual sentence embedders (each + logistic
regression), hybrids (embedding + TF-IDF features) and soft-vote ensembles of the singles.
Selection: the candidate with the best validation score (mean of overall macro-F1 and
Amharic macro-F1) wins; test scores are reported for every candidate. With --activate the
winner becomes ACTIVE only if its test macro-F1 is not lower than the active model's.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import joblib  # noqa: E402
import numpy as np  # noqa: E402
from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import accuracy_score, classification_report, f1_score  # noqa: E402

from assistant import nlu  # noqa: E402
from assistant.training_data import INTENTS, SEEDS, SERVICE_NAMES  # noqa: E402

SEED = 13
CANDIDATES = {
    "tfidf": {"kind": "tfidf", "embedder": None},
    "minilm": {"kind": "embedding", "embedder": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"},
    "e5": {"kind": "embedding", "embedder": "intfloat/multilingual-e5-small"},
    "labse": {"kind": "embedding", "embedder": "sentence-transformers/LaBSE"},
    "mpnet": {"kind": "embedding", "embedder": "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"},
}


# ---------------------------------------------------------------- data


def _typo(text: str, rng: random.Random) -> str:
    if len(text) < 4:
        return text
    i = rng.randrange(1, len(text) - 1)
    op = rng.choice(["drop", "dup", "swap"])
    if op == "drop":
        return text[:i] + text[i + 1:]
    if op == "dup":
        return text[:i] + text[i] + text[i:]
    return text[: i - 1] + text[i] + text[i - 1] + text[i + 1:]


def _fill(template: str, names: list[str], k: int, rng: random.Random) -> list[str]:
    if "{svc}" not in template:
        return [template]
    return [template.replace("{svc}", n) for n in rng.sample(names, min(k, len(names)))]


def build_dataset(extra_train: list[tuple[str, str, str]] | None = None) -> dict[str, list[tuple[str, str, str]]]:
    """Returns {"train"|"val"|"test": [(text, intent, lang)]}."""
    rng = random.Random(SEED)
    splits = {"train": [], "val": [], "test": []}
    for intent, seeds in SEEDS.items():
        by_lang: dict[str, list[str]] = {}
        for lang, text in seeds:
            by_lang.setdefault(lang, []).append(text)
        for lang, texts in by_lang.items():
            texts = texts[:]
            rng.shuffle(texts)
            n = len(texts)
            n_test = max(1, round(n * 0.2)) if n >= 4 else 0
            n_val = max(1, round(n * 0.2)) if n >= 6 else 0
            parts = {"test": texts[:n_test], "val": texts[n_test:n_test + n_val], "train": texts[n_test + n_val:]}
            for split, items in parts.items():
                pool = SERVICE_NAMES[lang]["train" if split == "train" else "test"]
                for t in items:
                    for filled in _fill(t, pool, 4 if split == "train" else 2, rng):
                        splits[split].append((filled, intent, lang))
                        if split == "train":
                            # Robustness to how people actually type
                            splits[split].append((_typo(filled, rng), intent, lang))
                            if lang == "en":
                                splits[split].append((filled.upper() if rng.random() < 0.2 else filled.capitalize(), intent, lang))
    for item in extra_train or []:
        splits["train"].append(item)
    return splits


def admin_labelled_examples() -> list[tuple[str, str, str]]:
    try:
        from services.db import fetch_all

        rows = fetch_all(
            "select message_redacted, labelled_intent from assistant_turns where labelled_intent is not null"
        )
    except Exception:
        return []
    return [(r["message_redacted"], r["labelled_intent"], nlu.detect_language(r["message_redacted"]))
            for r in rows if r["labelled_intent"] in INTENTS]


# ---------------------------------------------------------------- training


def _macro_f1(y_true, y_pred) -> float:
    return float(f1_score(y_true, y_pred, average="macro", labels=sorted(set(y_true)), zero_division=0))


def evaluate(predictor, data) -> dict:
    texts = [t for t, _, _ in data]
    y = [i for _, i, _ in data]
    probs = predictor.predict_proba(texts)
    pred = [predictor.classes_[k] for k in np.argmax(probs, axis=1)]
    out = {"n": len(y), "accuracy": float(accuracy_score(y, pred)), "macro_f1": _macro_f1(y, pred)}
    for group, langs in {"en": {"en"}, "amharic": {"am", "tr"}, "am_script": {"am"}, "transliterated": {"tr"}}.items():
        idx = [k for k, (_, _, lang) in enumerate(data) if lang in langs]
        if idx:
            yt = [y[k] for k in idx]
            yp = [pred[k] for k in idx]
            out[group] = {"n": len(idx), "accuracy": float(accuracy_score(yt, yp)), "macro_f1": _macro_f1(yt, yp)}
    out["per_intent"] = {
        k: round(v["f1-score"], 3)
        for k, v in classification_report(y, pred, output_dict=True, zero_division=0).items()
        if k in INTENTS
    }
    return out


def _val_score(val: dict) -> float:
    return (val["macro_f1"] + val.get("amharic", val)["macro_f1"]) / 2


def _latency(predictor) -> float:
    """Cold latency of one unseen message (the embedding memo is cleared first)."""
    predictor.predict_proba(["warm up"])
    phrases = ["i want to renew my passport", "ስንት ብር ያስከፍላል", "kebele metawekiya efeligalehu",
               "where is the trade office", "can someone apply for me"]
    total = 0.0
    for text in phrases:
        nlu._EMBED_CACHE.clear()
        t1 = time.time()
        predictor.predict_proba([text])
        total += time.time() - t1
    return round(total / len(phrases) * 1000, 1)


def train_candidate(name: str, spec: dict, splits: dict) -> dict:
    spec = dict(spec)
    t0 = time.time()
    tfidf = None
    if spec["kind"] in ("tfidf", "hybrid"):
        tfidf = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=1, sublinear_tf=True)
        tfidf.fit([nlu.normalize(t) for t, _, _ in splits["train"]])
    x_train = nlu.featurize(spec, tfidf, [t for t, _, _ in splits["train"]])
    y_train = [i for _, i, _ in splits["train"]]
    best = None
    for c in ([4, 16, 64] if spec["kind"] == "tfidf" else [1, 4, 16]):
        clf = LogisticRegression(C=c, max_iter=3000, class_weight="balanced", random_state=SEED)
        clf.fit(x_train, y_train)
        predictor = nlu.SinglePredictor(spec, tfidf, clf)
        val = evaluate(predictor, splits["val"])
        if best is None or _val_score(val) > best["val_score"]:
            best = {"C": c, "predictor": predictor, "val": val, "val_score": _val_score(val)}
    return {
        "name": name, "spec": spec, "C": best["C"], "predictor": best["predictor"],
        "val": best["val"], "val_score": best["val_score"], "test": evaluate(best["predictor"], splits["test"]),
        "train_seconds": round(time.time() - t0, 1), "latency_ms": _latency(best["predictor"]),
    }


def ensemble_candidates(results: list[dict], splits: dict) -> list[dict]:
    """Soft-vote ensembles of the single models; weights picked on the validation set."""
    by_name = {r["name"]: r for r in results}
    member_sets = [names for names in (["tfidf", "e5", "labse"], ["tfidf", "labse"], ["tfidf", "e5"], ["e5", "labse"])
                   if all(n in by_name for n in names)]
    out = []
    for names in member_sets:
        best = None
        grid = [[1.0] * len(names)] + [[2.0 if k == j else 1.0 for k in range(len(names))] for j in range(len(names))]
        for weights in grid:
            predictor = nlu.EnsemblePredictor([(n, by_name[n]["predictor"]) for n in names], weights)
            val = evaluate(predictor, splits["val"])
            if best is None or _val_score(val) > best["val_score"]:
                best = {"predictor": predictor, "val": val, "val_score": _val_score(val), "weights": weights}
        spec = {"kind": "ensemble", "embedder": "+".join(names), "weights": best["weights"]}
        out.append({
            "name": f"ensemble({'+'.join(names)})", "spec": spec, "C": None, "predictor": best["predictor"],
            "val": best["val"], "val_score": best["val_score"], "test": evaluate(best["predictor"], splits["test"]),
            "train_seconds": 0.0, "latency_ms": _latency(best["predictor"]),
        })
    return out


def _row(r: dict) -> str:
    t = r["test"]
    return (f"| {r['name']} | {r['spec'].get('embedder') or 'char n-gram TF-IDF'} | {r['val_score']:.3f} | "
            f"{t['macro_f1']:.3f} | {t['accuracy']:.3f} | {t.get('en', {}).get('macro_f1', 0):.3f} | "
            f"{t.get('amharic', {}).get('macro_f1', 0):.3f} | {t.get('am_script', {}).get('macro_f1', 0):.3f} | "
            f"{t.get('transliterated', {}).get('macro_f1', 0):.3f} | {r['latency_ms']} ms |")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", default="tfidf,minilm,e5,labse")
    ap.add_argument("--activate", action="store_true", help="make the winner ACTIVE if it does not regress")
    ap.add_argument("--no-hybrid", action="store_true")
    args = ap.parse_args()

    status_file = nlu.STORE / ".last_run.json"
    nlu.STORE.mkdir(parents=True, exist_ok=True)
    status_file.write_text(json.dumps({"state": "running", "started_at": datetime.now(timezone.utc).isoformat()}))

    labelled = admin_labelled_examples()
    splits = build_dataset(labelled)
    print(f"train {len(splits['train'])} · val {len(splits['val'])} · test {len(splits['test'])} "
          f"(admin-labelled {len(labelled)})", flush=True)

    results = []
    for name in args.candidates.split(","):
        name = name.strip()
        try:
            r = train_candidate(name, CANDIDATES[name], splits)
        except Exception as exc:  # a model that fails to download should not stop the run
            print(f"{name}: skipped ({exc})", flush=True)
            continue
        results.append(r)
        print(_row(r), flush=True)

    for r in ensemble_candidates(results, splits):
        results.append(r)
        print(_row(r), flush=True)

    embedded = [r for r in results if r["spec"]["kind"] == "embedding"]
    if embedded and not args.no_hybrid:
        top = max(embedded, key=lambda r: r["val_score"])
        for weight in (0.5, 1.0):
            spec = {"kind": "hybrid", "embedder": top["spec"]["embedder"], "tfidf_weight": weight}
            r = train_candidate(f"hybrid({top['name']}+tfidf x{weight})", spec, splits)
            results.append(r)
            print(_row(r), flush=True)

    winner = max(results, key=lambda r: r["val_score"])
    version = "v" + datetime.now().strftime("%Y%m%d-%H%M%S")
    folder = nlu.STORE / version
    folder.mkdir(parents=True)
    joblib.dump({"predictor": winner["predictor"]}, folder / "model.joblib")
    metrics = {
        "version": version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "chosen": winner["name"],
        "featurizer": winner["spec"],
        "C": winner["C"],
        "examples": {k: len(v) for k, v in splits.items()} | {"admin_labelled": len(labelled)},
        "test": winner["test"],
        "val": winner["val"],
        "latency_ms": winner["latency_ms"],
        "candidates": [
            {"name": r["name"], "featurizer": r["spec"], "val_score": round(r["val_score"], 4), "test": r["test"],
             "latency_ms": r["latency_ms"], "train_seconds": r["train_seconds"]}
            for r in results
        ],
    }
    (folder / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False))
    header = ("| candidate | featurizer | val score | test macro-F1 | test acc | English F1 | Amharic F1 (all) | "
              "Ge'ez script F1 | transliterated F1 | latency |\n|---|---|---|---|---|---|---|---|---|---|")
    report = [
        f"# Assistant intent model {version}", "",
        f"Chosen: **{winner['name']}** (best validation score: mean of overall and Amharic macro-F1).", "",
        f"Examples: {metrics['examples']}. Test set uses held-out seed sentences and held-out service names.", "",
        header, *[_row(r) for r in results], "",
        "Per-intent test F1 of the chosen model:", "",
        *[f"- {k}: {v}" for k, v in winner["test"]["per_intent"].items()],
    ]
    (folder / "report.md").write_text("\n".join(report) + "\n")

    activated = False
    if args.activate:
        current = nlu.active_version()
        current_f1 = None
        if current and (nlu.STORE / current / "metrics.json").exists():
            current_f1 = json.loads((nlu.STORE / current / "metrics.json").read_text())["test"]["macro_f1"]
        if current_f1 is None or winner["test"]["macro_f1"] >= current_f1:
            (nlu.STORE / "ACTIVE").write_text(version)
            activated = True
        print(f"active: {current} ({current_f1}) -> {'activated ' + version if activated else 'kept'}", flush=True)
    status_file.write_text(json.dumps({
        "state": "done", "version": version, "chosen": winner["name"], "activated": activated,
        "test_macro_f1": winner["test"]["macro_f1"], "finished_at": datetime.now(timezone.utc).isoformat(),
    }))
    print(f"saved {folder}  chosen={winner['name']}  test macro-F1={winner['test']['macro_f1']:.3f}  "
          f"Amharic={winner['test'].get('amharic', {}).get('macro_f1', 0):.3f}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        (nlu.STORE / ".last_run.json").write_text(json.dumps({"state": "failed", "error": str(exc)}))
        raise
