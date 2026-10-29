"""Intent model: text normalization, language detection, featurizers, runtime loading.

A model version lives in models_store/assistant/<version>/ with
  model.joblib   {"predictor": SinglePredictor | EnsemblePredictor}
  metrics.json   evaluation on the held-out test set (overall, per language, per intent)
  report.md      human readable comparison of the candidates that were trained
models_store/assistant/ACTIVE holds the version the API serves.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

STORE = Path(__file__).resolve().parent.parent / "models_store" / "assistant"

ETHIOPIC = re.compile(r"[ሀ-፿]")
LATIN = re.compile(r"[a-zA-Z]")
# Common Ge'ez homophones are written interchangeably; fold them to one form
_GEEZ_FOLD = str.maketrans({
    "ሐ": "ሀ", "ኀ": "ሀ", "ሑ": "ሁ", "ኁ": "ሁ", "ሒ": "ሂ", "ኂ": "ሂ", "ሓ": "ሃ", "ኃ": "ሃ", "ሔ": "ሄ", "ኄ": "ሄ",
    "ሕ": "ህ", "ኅ": "ህ", "ሖ": "ሆ", "ኆ": "ሆ", "ሠ": "ሰ", "ሡ": "ሱ", "ሢ": "ሲ", "ሣ": "ሳ", "ሤ": "ሴ", "ሥ": "ስ",
    "ሦ": "ሶ", "ዐ": "አ", "ዑ": "ኡ", "ዒ": "ኢ", "ዓ": "ኣ", "ዔ": "ኤ", "ዕ": "እ", "ዖ": "ኦ", "ፀ": "ጸ", "ፁ": "ጹ",
    "ፂ": "ጺ", "ፃ": "ጻ", "ፄ": "ጼ", "ፅ": "ጽ", "ፆ": "ጾ",
})
# Words that only appear in Amharic written with Latin letters
TRANSLIT_HINTS = {
    "selam", "salam", "efeligalehu", "efelgalehu", "amesegnalehu", "sint", "alebign", "mawtat", "lemawtat",
    "masadess", "lemasades", "endet", "yasfeligal", "metawekiya", "fekad", "nigd", "yeneged", "echilalehu", "lihid",
    "chaw", "dehna", "tena", "yistilign", "alew", "yifejal", "biro", "wekil", "betam", "ishi", "endegena", "lela",
    "neger", "yichalal", "magignet", "alegn", "tadias", "yet", "min", "new",
}
# Words that are also ordinary English, so they only count next to a clearly Amharic word
_AMBIGUOUS_HINTS = {"yet", "min", "new", "tena", "lela", "biro"}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text or "").lower().translate(_GEEZ_FOLD)
    text = re.sub(r"[፡።፣፤፥፦፧፨!?.,;:\"'()\[\]{}<>@#$%^&*_=+~`|\\/-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def detect_language(text: str) -> str:
    """'am' for Ge'ez script, 'tr' for Amharic in Latin letters, else 'en'."""
    ethiopic = len(ETHIOPIC.findall(text or ""))
    latin = len(LATIN.findall(text or ""))
    if ethiopic and ethiopic >= latin:
        return "am"
    words = set(normalize(text).split())
    strong = words & (TRANSLIT_HINTS - _AMBIGUOUS_HINTS)
    if strong and len(words & TRANSLIT_HINTS) >= max(1, len(words) // 3):
        return "tr"
    return "en"


# ---------------------------------------------------------------- featurizers

E5_MODELS = {"intfloat/multilingual-e5-small"}
CUSTOM_MODELS = {
    # Not bundled with fastembed: ONNX exports on Hugging Face
    "intfloat/multilingual-e5-small": ("Xenova/multilingual-e5-small", 384, "onnx/model_quantized.onnx"),
    "sentence-transformers/LaBSE": ("Xenova/LaBSE", 768, "onnx/model_quantized.onnx"),
}


@lru_cache(maxsize=4)
def embedder(name: str):
    from fastembed import TextEmbedding

    if name in CUSTOM_MODELS:
        from fastembed.common.model_description import ModelSource, PoolingType

        hf, dim, file = CUSTOM_MODELS[name]
        try:
            TextEmbedding.add_custom_model(
                model=name, pooling=PoolingType.MEAN, normalization=True,
                sources=ModelSource(hf=hf), dim=dim, model_file=file,
            )
        except ValueError:
            pass  # already registered in this process
    from services.embeddings import MODEL_CACHE  # one persistent cache for every embedder, never /tmp

    Path(MODEL_CACHE).mkdir(parents=True, exist_ok=True)
    return TextEmbedding(model_name=name, cache_dir=MODEL_CACHE)


_EMBED_CACHE: dict[tuple[str, str], np.ndarray] = {}
_EMBED_CACHE_MAX = 20000


def embed(name: str, texts: list[str]) -> np.ndarray:
    """Embeddings with a per-text memo, so training and repeated chat phrases don't re-run the model."""
    prefix = "query: " if name in E5_MODELS else ""
    missing = [t for t in dict.fromkeys(texts) if (name, t) not in _EMBED_CACHE]
    if missing:
        if len(_EMBED_CACHE) > _EMBED_CACHE_MAX:
            _EMBED_CACHE.clear()
        for t, v in zip(missing, embedder(name).embed([prefix + t for t in missing])):
            _EMBED_CACHE[(name, t)] = np.asarray(v, dtype=np.float32)
    return np.stack([_EMBED_CACHE[(name, t)] for t in texts])


def featurize(spec: dict, tfidf, texts: list[str]):
    """spec = {"kind": "tfidf"|"embedding"|"hybrid", "embedder": name|None, "tfidf_weight": float}"""
    from scipy.sparse import csr_matrix, hstack

    norm = [normalize(t) for t in texts]
    parts = []
    if spec["kind"] in ("embedding", "hybrid"):
        parts.append(csr_matrix(embed(spec["embedder"], norm)))
    if spec["kind"] in ("tfidf", "hybrid"):
        parts.append(tfidf.transform(norm) * spec.get("tfidf_weight", 1.0))
    return parts[0] if len(parts) == 1 else hstack(parts).tocsr()


# ---------------------------------------------------------------- predictors


class SinglePredictor:
    """One featurizer + one linear classifier."""

    def __init__(self, spec: dict, tfidf, classifier):
        self.spec, self.tfidf, self.classifier = spec, tfidf, classifier
        self.classes_ = list(classifier.classes_)

    def predict_proba(self, texts: list[str]) -> np.ndarray:
        return self.classifier.predict_proba(featurize(self.spec, self.tfidf, texts))


class EnsemblePredictor:
    """Weighted soft vote: each member is strong on a different script (English, Ge'ez, Latin Amharic)."""

    def __init__(self, members: list[tuple[str, SinglePredictor]], weights: list[float]):
        self.members, self.weights = members, weights
        self.classes_ = members[0][1].classes_
        assert all(m.classes_ == self.classes_ for _, m in members)

    def predict_proba(self, texts: list[str]) -> np.ndarray:
        total = sum(self.weights)
        return sum(w * m.predict_proba(texts) for (_, m), w in zip(self.members, self.weights)) / total


# ---------------------------------------------------------------- runtime


@dataclass
class Prediction:
    intent: str
    confidence: float
    ranked: list[tuple[str, float]]
    language: str
    version: str | None


class IntentModel:
    def __init__(self, version: str, bundle: dict, metrics: dict):
        self.version = version
        self.predictor = bundle["predictor"]
        self.labels = list(self.predictor.classes_)
        self.metrics = metrics

    @classmethod
    def load(cls, version: str) -> "IntentModel":
        import joblib

        folder = STORE / version
        bundle = joblib.load(folder / "model.joblib")
        metrics = json.loads((folder / "metrics.json").read_text()) if (folder / "metrics.json").exists() else {}
        return cls(version, bundle, metrics)

    def predict(self, text: str) -> Prediction:
        probs = self.predictor.predict_proba([text])[0]
        order = np.argsort(probs)[::-1]
        ranked = [(self.labels[i], float(probs[i])) for i in order[:3]]
        return Prediction(ranked[0][0], ranked[0][1], ranked, detect_language(text), self.version)


_lock = threading.Lock()
_active: IntentModel | None = None


def active_version() -> str | None:
    marker = STORE / "ACTIVE"
    return marker.read_text().strip() if marker.exists() else None


def get_model() -> IntentModel | None:
    """The served model, reloaded when ACTIVE points somewhere new. None if nothing is trained."""
    global _active
    version = active_version()
    if not version:
        return None
    with _lock:
        if _active is None or _active.version != version:
            try:
                _active = IntentModel.load(version)
            except Exception:
                log.exception("Could not load assistant model %s", version)
                return None
        return _active


def list_versions() -> list[dict]:
    out = []
    if not STORE.exists():
        return out
    for folder in sorted(p for p in STORE.iterdir() if p.is_dir() and not p.name.startswith(".")):
        metrics_file = folder / "metrics.json"
        metrics = json.loads(metrics_file.read_text()) if metrics_file.exists() else {}
        out.append({"version": folder.name, "chosen": metrics.get("chosen"), "test": metrics.get("test"),
                    "created_at": metrics.get("created_at"), "examples": metrics.get("examples")})
    return out
