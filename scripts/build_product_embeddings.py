"""Compute product-search embeddings locally (run on the operator's PC, not
on the production server).

backend/services/rag_service.py used to embed every product with BAAI/bge-m3
at backend startup. That was tolerable for ~2k products, but with the ~130k
TII products it would take hours of CPU per deploy. Instead this script
embeds them once, here, and scripts/sync_to_production.py pushes the vectors
into Postgres (pgvector); production only ever embeds the user's query.

Incremental: a product is re-embedded only when its embedding text changes
(new product, renamed, re-categorized); unchanged vectors are reused.

Output (gitignored, derived data):
    backend/data/product_embeddings/embeddings.npy   float16 [n, 1024], L2-normalized
    backend/data/product_embeddings/meta.json        {"model", "ids", "text_hashes"}

Usage:
    python scripts/build_product_embeddings.py [--batch-size 64] [--limit N]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from inventory_db import get_inventory_connection  # noqa: E402

MODEL_NAME = "BAAI/bge-m3"  # must match backend/services/rag_service.py
OUT_DIR = ROOT / "backend" / "data" / "product_embeddings"


# "(第3次部分變更)" etc. only marks a filing revision of the same product --
# no meaning for search -- and ~half the TII catalogue is such revisions.
# Stripping it lets all revisions share one vector (halves embedding time).
_REVISION_RE = re.compile(r"[(（]\s*第?\s*[0-9一二三四五六七八九十百]+\s*次\s*部[分份]變更\s*[)）]")


def embedding_text(product_name: str, company: str, category: str) -> str:
    # Same shape rag_service has always embedded ("name，company，category").
    name = _REVISION_RE.sub("", unicodedata.normalize("NFKC", product_name or "")).strip()
    return f"{name}，{company}，{category}"


def _hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def load_existing() -> tuple[dict[int, tuple[str, np.ndarray]], str]:
    meta_path, vec_path = OUT_DIR / "meta.json", OUT_DIR / "embeddings.npy"
    if not (meta_path.exists() and vec_path.exists()):
        return {}, ""
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    vectors = np.load(vec_path)
    return {pid: (h, vectors[i]) for i, (pid, h) in enumerate(zip(meta["ids"], meta["text_hashes"]))}, meta["model"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--limit", type=int, default=0, help="Only embed this many new products (speed test).")
    args = parser.parse_args()

    with get_inventory_connection() as conn:
        rows = conn.execute(
            "SELECT id, product_name, company_name, category FROM insurance_products ORDER BY id"
        ).fetchall()
    ids = [r[0] for r in rows]
    texts = [embedding_text(r[1], r[2], r[3]) for r in rows]
    hashes = [_hash(t) for t in texts]

    existing, existing_model = load_existing()
    if existing_model and existing_model != MODEL_NAME:
        existing = {}
    todo = [i for i, (pid, h) in enumerate(zip(ids, hashes)) if existing.get(pid, ("",))[0] != h]
    if args.limit:
        todo = todo[: args.limit]
    print(f"products={len(ids)} to_embed={len(todo)}", flush=True)

    vectors = np.zeros((len(ids), 1024), dtype=np.float16)
    # Hash recorded per row only once its vector is real (reused unchanged,
    # or freshly embedded) -- anything else is saved with "" so the next run
    # embeds it, even if this run was cut short or limited by --limit.
    valid_hashes = [""] * len(ids)
    for i, (pid, h) in enumerate(zip(ids, hashes)):
        if existing.get(pid, ("",))[0] == h:
            vectors[i] = existing[pid][1]
            valid_hashes[i] = h

    if todo:
        import os

        import torch
        from sentence_transformers import SentenceTransformer

        # torch defaults to fewer threads than this CPU's logical cores; on a
        # hybrid P/E-core CPU using all of them measured ~1.5x faster.
        torch.set_num_threads(os.cpu_count() or 4)

        model = SentenceTransformer(MODEL_NAME)
        model.max_seq_length = 128  # names are short; caps cost of the rare very long one
        # Each distinct text is embedded once and shared by every row that
        # has it; sorted by length so a batch pads to a similar size.
        rows_by_text: dict[str, list[int]] = {}
        for i in todo:
            rows_by_text.setdefault(texts[i], []).append(i)
        unique_texts = sorted(rows_by_text, key=len)
        print(f"distinct texts to embed: {len(unique_texts)}", flush=True)
        started = time.time()
        for start in range(0, len(unique_texts), args.batch_size):
            batch = unique_texts[start : start + args.batch_size]
            emb = model.encode(batch, normalize_embeddings=True, show_progress_bar=False).astype(np.float16)
            for text, vec in zip(batch, emb):
                for i in rows_by_text[text]:
                    vectors[i] = vec
                    valid_hashes[i] = hashes[i]
            done = start + len(batch)
            if done % (args.batch_size * 20) < args.batch_size or done == len(unique_texts):
                rate = done / (time.time() - started)
                print(f"embedded {done}/{len(unique_texts)}  {rate:.1f}/s  eta {(len(unique_texts) - done) / rate / 60:.1f} min", flush=True)
            if done % (args.batch_size * 200) < args.batch_size:
                _save(ids, valid_hashes, vectors)  # checkpoint

    _save(ids, valid_hashes, vectors)
    print("done", flush=True)


def _save(ids, valid_hashes, vectors) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    np.save(OUT_DIR / "embeddings.npy.tmp.npy", vectors)
    (OUT_DIR / "embeddings.npy.tmp.npy").replace(OUT_DIR / "embeddings.npy")
    (OUT_DIR / "meta.json").write_text(
        json.dumps({"model": MODEL_NAME, "ids": ids, "text_hashes": valid_hashes}), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
