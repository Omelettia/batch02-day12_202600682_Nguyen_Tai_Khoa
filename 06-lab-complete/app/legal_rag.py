"""Lightweight legal RAG core adapted from the Day 9 legal RAG project."""
from __future__ import annotations

import json
import logging
import math
import re
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from app.config import settings

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "standardized"
CHUNK_SIZE = 900
CHUNK_OVERLAP = 140
TOP_K = 4
GEMINI_TIMEOUT_SECONDS = 25

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    content: str
    source: str
    path: str
    doc_type: str
    chunk_index: int


_CHUNKS: list[Chunk] | None = None
_TOKENIZED: list[list[str]] | None = None
_IDF: dict[str, float] | None = None
_AVG_DOC_LEN = 1.0


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower(), flags=re.UNICODE)


def _doc_type(path: Path) -> str:
    parts = {part.lower() for part in path.parts}
    if "legal" in parts:
        return "legal"
    if "news" in parts:
        return "news"
    return "unknown"


def _split_text(text: str) -> list[str]:
    chunks: list[str] = []
    current = ""
    for paragraph in re.split(r"\n\s*\n", text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(paragraph) > CHUNK_SIZE:
            if current:
                chunks.append(current)
                current = ""
            start = 0
            while start < len(paragraph):
                end = min(start + CHUNK_SIZE, len(paragraph))
                chunks.append(paragraph[start:end].strip())
                if end == len(paragraph):
                    break
                start = max(end - CHUNK_OVERLAP, start + 1)
            continue
        if not current:
            current = paragraph
        elif len(current) + len(paragraph) + 2 <= CHUNK_SIZE:
            current = f"{current}\n\n{paragraph}"
        else:
            chunks.append(current)
            current = paragraph
    if current:
        chunks.append(current)
    return chunks


def _load_chunks() -> list[Chunk]:
    chunks: list[Chunk] = []
    if not DATA_DIR.exists():
        return chunks
    for file_path in sorted(DATA_DIR.rglob("*.md")):
        content = file_path.read_text(encoding="utf-8").strip()
        if not content:
            continue
        rel_path = file_path.relative_to(DATA_DIR).as_posix()
        for index, text in enumerate(_split_text(content)):
            chunks.append(
                Chunk(
                    content=text,
                    source=file_path.name,
                    path=rel_path,
                    doc_type=_doc_type(file_path),
                    chunk_index=index,
                )
            )
    return chunks


def _ensure_index() -> tuple[list[Chunk], list[list[str]], dict[str, float]]:
    global _CHUNKS, _TOKENIZED, _IDF, _AVG_DOC_LEN
    if _CHUNKS is not None and _TOKENIZED is not None and _IDF is not None:
        return _CHUNKS, _TOKENIZED, _IDF

    _CHUNKS = _load_chunks()
    _TOKENIZED = [_tokenize(chunk.content) for chunk in _CHUNKS]
    _AVG_DOC_LEN = (
        sum(len(tokens) for tokens in _TOKENIZED) / len(_TOKENIZED)
        if _TOKENIZED
        else 1.0
    )

    doc_freq = Counter()
    for tokens in _TOKENIZED:
        doc_freq.update(set(tokens))
    total = max(len(_TOKENIZED), 1)
    _IDF = {
        term: math.log(1 + (total - freq + 0.5) / (freq + 0.5))
        for term, freq in doc_freq.items()
    }
    return _CHUNKS, _TOKENIZED, _IDF


def _score(content: str, tokens: list[str], query: str, query_tokens: list[str], idf: dict[str, float]) -> float:
    if not tokens or not query_tokens:
        return 0.0
    freqs = Counter(tokens)
    doc_len = len(tokens)
    k1 = 1.5
    b = 0.75
    score = 0.0
    for term in query_tokens:
        tf = freqs.get(term, 0)
        if tf <= 0:
            continue
        denom = tf + k1 * (1 - b + b * doc_len / _AVG_DOC_LEN)
        score += idf.get(term, 0.0) * (tf * (k1 + 1)) / denom
    content_lower = content.lower()
    query_lower = query.lower()
    important_phrases = [
        "hành vi bị nghiêm cấm",
        "nghiêm cấm",
        "cai nghiện",
        "tổ chức sử dụng",
        "tàng trữ",
        "mua bán",
        "phòng, chống ma túy",
    ]
    for phrase in important_phrases:
        if phrase in query_lower and phrase in content_lower:
            score += 4.0
    return score


def retrieve(query: str, top_k: int = TOP_K) -> list[dict]:
    chunks, tokenized, idf = _ensure_index()
    query_tokens = _tokenize(query)
    scored = []
    for chunk, tokens in zip(chunks, tokenized):
        score = _score(chunk.content, tokens, query, query_tokens, idf)
        if score <= 0:
            continue
        scored.append((score, chunk))
    scored.sort(key=lambda item: item[0], reverse=True)
    best = scored[:top_k]
    max_score = best[0][0] if best else 1.0
    return [
        {
            "content": chunk.content,
            "score": round(score / max_score, 4),
            "metadata": {
                "source": chunk.source,
                "path": chunk.path,
                "type": chunk.doc_type,
                "chunk_index": chunk.chunk_index,
            },
        }
        for score, chunk in best
    ]


def _article_5_prohibited_acts() -> dict | None:
    law_path = DATA_DIR / "legal" / "73_2021_QH14_445185.md"
    if not law_path.exists():
        return None
    content = law_path.read_text(encoding="utf-8")
    match = re.search(
        r"Điều 5\. Các hành vi bị nghiêm cấm(?P<body>.*?)(?:\nĐiều 6\.)",
        content,
        flags=re.S,
    )
    if not match:
        return None
    items = re.findall(r"(?:^|\n)(\d+\.\s+.*?)(?=\n\d+\.|\Z)", match.group("body").strip(), flags=re.S)
    clean_items = [" ".join(item.split()) for item in items[:8]]
    if not clean_items:
        return None
    answer = (
        "Theo Điều 5 Luật Phòng, chống ma túy 2021, các hành vi bị nghiêm cấm gồm:\n\n"
        + "\n".join(f"- {item}" for item in clean_items)
        + "\n\nNội dung này là thông tin tham khảo, không thay thế tư vấn pháp lý chính thức. "
        "[73_2021_QH14_445185.md, 2021]"
    )
    return {
        "answer": answer,
        "sources": [
            {
                "content": "Điều 5. Các hành vi bị nghiêm cấm\n" + "\n".join(clean_items),
                "score": 1.0,
                "metadata": {
                    "source": "73_2021_QH14_445185.md",
                    "path": "legal/73_2021_QH14_445185.md",
                    "type": "legal",
                    "article": "Điều 5",
                },
            }
        ],
        "retrieval_source": "local_day9_legal_corpus_article",
    }


def _citation(chunk: dict, index: int) -> str:
    metadata = chunk.get("metadata", {})
    source = metadata.get("source") or f"source-{index}"
    text = f"{source} {chunk.get('content', '')}"
    year_match = re.search(r"\b(20\d{2}|19\d{2})\b", text)
    year = year_match.group(1) if year_match else "n.d."
    return f"{source}, {year}"


def _select_sentence(content: str) -> str:
    clean = " ".join(content.split())
    sentences = re.split(r"(?<=[.!?])\s+", clean)
    for sentence in sentences:
        starts_cleanly = bool(re.match(r"^([A-ZÀ-Ỵ0-9#]|Điều|Chương)", sentence))
        if starts_cleanly and 80 <= len(sentence) <= 420:
            return sentence
    for sentence in sentences:
        if 80 <= len(sentence) <= 420:
            return sentence
    return clean[:420]


def conversation_context(history: list[dict], limit: int = 4) -> str:
    if not history:
        return ""
    lines = []
    for item in history[-limit:]:
        role = item.get("role", "unknown")
        content = " ".join(str(item.get("content", "")).split())
        lines.append(f"{role}: {content[:220]}")
    return "\n".join(lines)


def _model_name() -> str:
    if settings.llm_provider == "gemini" and settings.gemini_api_key:
        return settings.gemini_model
    return "local-day9-legal-rag"


def _gemini_model_path() -> str:
    model = settings.gemini_model.strip()
    if model.startswith("models/"):
        model = model.removeprefix("models/")
    return urllib.parse.quote(model, safe="")


def _source_evidence(sources: list[dict]) -> str:
    evidence = []
    for index, source in enumerate(sources[:TOP_K], 1):
        metadata = source.get("metadata", {})
        citation = _citation(source, index)
        content = " ".join(str(source.get("content", "")).split())
        evidence.append(
            f"{index}. Source: {metadata.get('path') or metadata.get('source') or 'local corpus'}\n"
            f"Citation: [{citation}]\n"
            f"Evidence: {content[:1200]}"
        )
    return "\n\n".join(evidence)


def _generate_with_gemini(query: str, history: list[dict], sources: list[dict], fallback: str) -> str | None:
    if settings.llm_provider != "gemini" or not settings.gemini_api_key or not sources:
        return None

    system_instruction = (
        "You are a Vietnamese legal RAG assistant for a student deployment lab. "
        "Answer in Vietnamese. Use only the provided evidence. Include concise citations "
        "using the supplied filenames and years. Say when the evidence is insufficient. "
        "Add a short note that the answer is reference information, not official legal advice."
    )
    prompt = (
        f"Question:\n{query}\n\n"
        f"Recent conversation:\n{conversation_context(history) or 'No prior conversation.'}\n\n"
        f"Evidence:\n{_source_evidence(sources)}\n\n"
        f"Draft answer to improve while preserving citations:\n{fallback}"
    )
    payload = {
        "system_instruction": {"parts": [{"text": system_instruction}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 900,
        },
    }
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{_gemini_model_path()}:generateContent"
    )
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": settings.gemini_api_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=GEMINI_TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        logger.warning("Gemini generation failed; using local fallback: %s", exc)
        return None

    parts = (
        data.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [])
    )
    text = "\n".join(part.get("text", "") for part in parts if part.get("text"))
    return text.strip() or None


def answer_legal_question(query: str, history: list[dict] | None = None) -> dict:
    history = history or []
    query_lower = query.lower()
    if "nghiêm cấm" in query_lower or "hành vi bị cấm" in query_lower:
        direct = _article_5_prohibited_acts()
        if direct is not None:
            gemini_answer = _generate_with_gemini(query, history, direct["sources"], direct["answer"])
            if gemini_answer:
                direct["answer"] = gemini_answer
                direct["retrieval_source"] = "gemini_with_local_day9_legal_corpus_article"
            direct["model"] = _model_name()
            return direct

    chunks = retrieve(query, top_k=TOP_K)
    if not chunks:
        return {
            "answer": (
                "Tôi không thể xác minh thông tin này từ nguồn hiện có. "
                "Vui lòng cung cấp thêm ngữ cảnh hoặc hỏi về pháp luật phòng, chống ma túy."
            ),
            "sources": [],
            "retrieval_source": "none",
            "model": _model_name(),
        }

    context_note = ""
    history_text = conversation_context(history or [])
    if history_text:
        context_note = "Tôi đã dùng lịch sử hội thoại để hiểu câu hỏi tiếp theo, nhưng chỉ trích dẫn nguồn tài liệu truy xuất được.\n\n"

    evidence = []
    for index, chunk in enumerate(chunks[:3], 1):
        evidence.append(f"{index}. {_select_sentence(chunk['content'])} [{_citation(chunk, index)}]")

    answer = (
        f"{context_note}"
        "Dưới đây là câu trả lời tham khảo từ kho dữ liệu pháp luật/tin tức của dự án Day 9. "
        "Nội dung này không thay thế tư vấn pháp lý chính thức.\n\n"
        + "\n\n".join(evidence)
    )
    gemini_answer = _generate_with_gemini(query, history, chunks, answer)
    return {
        "answer": gemini_answer or answer,
        "sources": chunks,
        "retrieval_source": (
            "gemini_with_local_day9_legal_corpus"
            if gemini_answer
            else "local_day9_legal_corpus"
        ),
        "model": _model_name(),
    }
