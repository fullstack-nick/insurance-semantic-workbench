"""One pinned CPU model, shared cache, no network access during application runs."""

from functools import lru_cache
from threading import Lock

import numpy as np

from .config import settings
from .util import digest

MANIFEST = {
    "model": "intfloat/multilingual-e5-small",
    "revision": "614241f622f53c4eeff9890bdc4f31cfecc418b3",
    "dimension": 384,
    "device": "cpu",
    "normalization": "L2",
    "distance": "cosine",
    "query_prefix": "query: ",
    "passage_prefix": "passage: ",
    "max_tokens": 512,
    "chunker": "clause-300-overlap40-v1",
    "fact_card": "v1",
}
MANIFEST_HASH = digest(MANIFEST)
_lock = Lock()


@lru_cache
def tokenizer():
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(
        str(settings().model_dir), local_files_only=True, trust_remote_code=False
    )


@lru_cache
def model():
    import torch
    from sentence_transformers import SentenceTransformer

    torch.set_num_threads(4)
    return SentenceTransformer(
        str(settings().model_dir), device="cpu", local_files_only=True, trust_remote_code=False
    )


def encode(texts, query=False):
    prefix = MANIFEST["query_prefix" if query else "passage_prefix"]
    with _lock:
        result = model().encode(
            [prefix + t for t in texts], normalize_embeddings=True, show_progress_bar=False, batch_size=32
        )
    if result.shape != (len(texts), 384) or not np.isfinite(result).all():
        raise RuntimeError("Embedding model violated its manifest")
    return result


def cache_key(text):
    return digest([MANIFEST_HASH, text])


def chunks(text):
    """Split only inside a single clause, preserving Unicode offsets."""
    tokens = tokenizer()(text, add_special_tokens=False, return_offsets_mapping=True)
    offsets = tokens["offset_mapping"]
    if len(offsets) <= 350:
        return [(0, len(text), text)]
    parts = []
    for first in range(0, len(offsets), 260):
        last = min(first + 300, len(offsets))
        start = offsets[first][0]
        end = offsets[last - 1][1]
        parts.append((start, end, text[start:end]))
        if last == len(offsets):
            break
    return parts
