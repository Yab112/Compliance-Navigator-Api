"""Which service is the person talking about?

Candidates come from every source we hold, each with English and Amharic names and aliases:
  path:<document>   our multi-office paths (the compliance graph)
  org:<uuid>        services organizations published themselves
  mesob:<id>        the MESOB partner catalog (English and Amharic entries)

Score = embedding cosine (multilingual model, when available) blended with a lexical match,
plus a small preference for organization-published data. A clear winner is accepted; close
calls become disambiguation chips; weak matches are reported as not found.
"""

from __future__ import annotations

import hashlib
import logging
import re
import threading
from dataclasses import dataclass, field

import numpy as np

from assistant import entities, nlu
from services import catalog_service

log = logging.getLogger(__name__)

COSINE_FLOOR = 0.80
ACCEPT = 0.60
MARGIN = 0.06
SUGGEST = 0.42
OPTION_SPREAD = 0.15  # only offer options close to the best one
SOURCE_BONUS = {"org": 0.04, "path": 0.03, "mesob": 0.0}
RESOLVER_EMBEDDERS = ("intfloat/multilingual-e5-small", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

STOP = {
    "i", "want", "need", "to", "get", "a", "an", "the", "my", "for", "how", "do", "can", "apply", "please", "what",
    "should", "is", "it", "me", "of", "and", "in", "on", "process", "steps", "help", "obtain", "new", "where", "much",
    "እፈልጋለሁ", "ማውጣት", "ለማውጣት", "እንዴት", "ምን", "ማድረግ", "አለብኝ", "efeligalehu", "mawtat", "lemawtat", "min",
    "madreg", "alebign", "endet",
    # Question and marketplace words: a follow-up like "where do i go" names no service
    "much", "cost", "costs", "fee", "fees", "price", "pay", "paid", "money", "birr", "etb", "where", "go", "going",
    "office", "offices", "branch", "address", "open", "hours", "documents", "document", "bring", "papers", "paper",
    "requirements", "required", "long", "take", "takes", "days", "day", "time", "ready", "online", "website", "link",
    "someone", "somebody", "brother", "sister", "wife", "husband", "relative", "family", "behalf", "apply", "myself",
    "agent", "agents", "find", "hire", "delala", "broker", "guday", "geday", "does", "do", "is", "there", "which",
    "when", "who", "this", "that", "with", "will", "be", "are", "you", "your", "about", "tell", "else", "other", "also",
    "ስንት", "ብር", "ያስከፍላል", "ክፍያ", "ክፍያው", "የት", "ልሂድ", "ይዤ", "ሰነዶች", "ጊዜ", "ቀን", "ይፈጃል", "ኦንላይን",
    "ሌላ", "ሰው", "ሊያመለክትልኝ", "ይችላል", "ወኪል", "ደላላ", "ቢሮ", "ቢሮው", "ነው", "ናቸው", "ያስፈልጋል",
}


@dataclass
class Candidate:
    key: str
    source: str
    ref: str
    title: str
    title_am: str | None
    language: str
    texts: list[str] = field(default_factory=list)


@dataclass
class Match:
    candidate: Candidate
    score: float


def _path_candidates() -> list[Candidate]:
    try:
        from services.graph_admin import list_documents

        docs = list_documents()
    except Exception:
        log.warning("Graph unavailable for the resolver; path services skipped")
        docs = []
    out = []
    for d in docs:
        if not d.get("target_of"):
            continue
        meta = entities.DOCUMENTS.get(d["id"], {})
        title_am = d.get("name_am") or meta.get("am")
        texts = [d.get("name") or d["id"], *(meta.get("aliases") or [])]
        if title_am:
            texts.append(title_am)
        out.append(Candidate(f"path:{d['id']}", "path", d["id"], d.get("name") or d["id"], title_am, "en", texts))
    return out


def _org_candidates() -> list[Candidate]:
    try:
        from services import org_service

        live = org_service._live_services()
    except Exception:
        log.warning("Organization services unavailable for the resolver")
        return []
    out = []
    for sid, snap in live.items():
        texts = [snap.get("name") or "", snap.get("summary") or ""]
        if snap.get("name_am"):
            texts.append(snap["name_am"])
        out.append(Candidate(f"org:{sid}", "org", sid, snap.get("name") or "", snap.get("name_am"), "en",
                             [t for t in texts if t]))
    return out


def _mesob_candidates() -> list[Candidate]:
    out = []
    for s in catalog_service.load_catalog()["services"]:
        name = s["name"].strip()
        title = name.title() if name.isupper() else name
        texts = [title, f"{title} {s.get('institution_short_name') or ''}"]
        out.append(Candidate(f"mesob:{s['id']}", "mesob", s["id"], title,
                             name if s["language"] == "am" else None, s["language"], texts))
    return out


class ServiceIndex:
    def __init__(self) -> None:
        self.candidates = _path_candidates() + _org_candidates() + _mesob_candidates()
        self.signature = hashlib.sha1("|".join(c.key for c in self.candidates).encode()).hexdigest()
        self.idf = _idf(self.candidates)
        self.embedder: str | None = None
        self.vectors: np.ndarray | None = None
        self._embed()

    def _embed(self) -> None:
        # The first text of each candidate is its name; that is what we embed
        names = [nlu.normalize(c.texts[0] if c.language == "en" else (c.title_am or c.texts[0])) for c in self.candidates]
        for name in RESOLVER_EMBEDDERS:
            try:
                self.vectors = _unit(nlu.embed(name, names))
                self.embedder = name
                return
            except Exception:
                log.warning("Resolver embedder %s unavailable", name)
        self.vectors = None

    def search(self, text: str, limit: int = 5) -> list[Match]:
        query = nlu.normalize(text)
        q_tokens = [t for t in query.split() if t not in STOP]
        if not q_tokens:
            return []
        lexical = np.array([_lexical(q_tokens, query, c, self.idf) for c in self.candidates])
        if self.vectors is not None and self.embedder:
            qv = _unit(nlu.embed(self.embedder, [" ".join(q_tokens)]))[0]
            # These embedders put any two texts at about 0.8; only what is above that says they mean the same
            cosine = np.clip((self.vectors @ qv - COSINE_FLOOR) / (1 - COSINE_FLOOR), 0, 1)
            score = 0.5 * cosine + 0.5 * lexical
        else:
            score = lexical
        score = score + np.array([SOURCE_BONUS[c.source] for c in self.candidates])
        order = np.argsort(score)[::-1]
        out, seen = [], set()
        for i in order:
            c = self.candidates[i]
            dedupe = (c.title.lower(), c.source)
            if dedupe in seen:
                continue
            seen.add(dedupe)
            out.append(Match(c, float(score[i])))
            if len(out) >= limit:
                break
        return out

    def get(self, key: str) -> Candidate | None:
        return next((c for c in self.candidates if c.key == key), None)


def _unit(m: np.ndarray) -> np.ndarray:
    return m / np.clip(np.linalg.norm(m, axis=1, keepdims=True), 1e-9, None)


def _trigrams(s: str) -> set[str]:
    s = f"  {s} "
    return {s[i:i + 3] for i in range(len(s) - 2)}


def _tokens(text: str) -> list[str]:
    return [w for w in nlu.normalize(text).split() if w not in STOP]


def _idf(candidates: list[Candidate]) -> dict[str, float]:
    """Rare words tell services apart ("driving", "VAT"); common ones ("license", "registration") don't."""
    counts: dict[str, int] = {}
    for c in candidates:
        for w in {w for text in c.texts for w in _tokens(text)}:
            counts[w] = counts.get(w, 0) + 1
    n = max(1, len(candidates))
    return {w: float(np.log((n + 1) / (k + 0.5))) for w, k in counts.items()}


def _same_word(a: str, b: str) -> bool:
    if a == b:
        return True
    if len(a) > 3 and len(b) > 3 and (a in b or b in a):
        return True
    # driving / driver, registration / register: a shared stem
    stem = 0
    for x, y in zip(a, b):
        if x != y:
            break
        stem += 1
    return stem >= max(4, min(len(a), len(b)) - 3)


def _lexical(q_tokens: list[str], query: str, c: Candidate, idf: dict[str, float] | None = None) -> float:
    idf = idf or {}
    default = float(np.mean(list(idf.values()))) if idf else 1.0  # a word no service uses: an average word

    def weight(w: str) -> float:
        return idf.get(w, default)

    q_weight = sum(weight(q) for q in q_tokens) or 1.0
    best = 0.0
    for text in c.texts:
        t_tokens = _tokens(text)
        if not t_tokens:
            continue
        t_weight = sum(weight(w) for w in t_tokens) or 1.0
        covered = sum(weight(w) for w in t_tokens if any(_same_word(w, q) for q in q_tokens))
        found = sum(weight(q) for q in q_tokens if any(_same_word(w, q) for w in t_tokens))
        coverage, precision = covered / t_weight, found / q_weight
        tri_q, tri_t = _trigrams(" ".join(q_tokens)), _trigrams(" ".join(t_tokens))
        jaccard = len(tri_q & tri_t) / max(1, len(tri_q | tri_t))
        best = max(best, 0.4 * coverage + 0.4 * precision + 0.2 * jaccard)
    return best


_index: ServiceIndex | None = None
_index_lock = threading.Lock()


def get_index(refresh: bool = False) -> ServiceIndex:
    global _index
    with _index_lock:
        if _index is None or refresh:
            _index = ServiceIndex()
        return _index


# ---------------------------------------------------------------- families that always need a choice

PASSPORT = re.compile(r"passport|ፓስፖርት|pasport|paspport")


def passport_options(language: str) -> list[dict]:
    """New passport is a multi-office path; the other cases are single MESOB services."""
    am = language == "am"
    rows = [
        ("new", "New passport", "አዲስ ፓስፖርት", "path:passport"),
        ("renewal", "Renewal", "እድሳት", "mesob:mesob-13" if am else "mesob:mesob-728"),
        ("lost", "Lost or stolen", "የጠፋ ወይም የተሰረቀ", "mesob:mesob-588" if am else "mesob:mesob-732"),
        ("damaged", "Damaged", "የተበላሸ", "mesob:mesob-587" if am else "mesob:mesob-731"),
        ("pages", "Pages ran out", "ቅጠሉ ያለቀበት", "mesob:mesob-589" if am else "mesob:mesob-733"),
    ]
    index = get_index()
    return [{"variant": v, "label": am_label if am else en_label, "key": key}
            for v, en_label, am_label, key in rows if index.get(key)]


def resolve(text: str, language: str) -> dict:
    """{"status": "resolved"|"ambiguous"|"none", "candidate", "options"}"""
    norm = nlu.normalize(text)
    if PASSPORT.search(norm):
        options = passport_options(language)
        variant = entities.passport_variant(text)
        chosen = next((o for o in options if o["variant"] == variant), None)
        if chosen:
            return {"status": "resolved", "candidate": get_index().get(chosen["key"]), "options": []}
        return {"status": "ambiguous", "candidate": None, "options": options, "family": "passport"}

    matches = get_index().search(text)
    if language == "am":
        # Prefer the Amharic catalog entry when the person writes in Amharic
        matches.sort(key=lambda m: -(m.score + (0.02 if m.candidate.language == "am" or m.candidate.title_am else 0)))
    else:
        matches = [m for m in matches if m.candidate.language == "en"] or matches
    if not matches or matches[0].score < SUGGEST:
        return {"status": "none", "candidate": None, "options": []}
    top = matches[0]
    second = matches[1].score if len(matches) > 1 else 0.0
    if top.score >= ACCEPT and top.score - second >= MARGIN:
        return {"status": "resolved", "candidate": top.candidate, "options": [], "score": top.score}
    options = [{"label": (m.candidate.title_am if language == "am" and m.candidate.title_am else m.candidate.title),
                "key": m.candidate.key, "score": round(m.score, 3)}
               for m in matches[:3] if m.score >= max(SUGGEST, top.score - OPTION_SPREAD)]
    return {"status": "ambiguous", "candidate": None, "options": options, "score": top.score}
