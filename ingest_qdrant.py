#!/usr/bin/env python
"""
Ingest Markdown / text files into Qdrant.
- Splits each file into fixed-length chunks (default 500 chars)
- Generates deterministic point IDs so re-running does **not** create duplicates
- Upserts vectors + payload into a target collection
Usage::
    python ingest_qdrant.py --data_dir texts --collection documents
"""

import argparse
import hashlib
import os
import uuid
from pathlib import Path
import glob

from tqdm import tqdm
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

DEFAULT_CHUNK_SIZE = 500
MODEL_NAME = "all-MiniLM-L6-v2"  # 日本語のみ→"bge-small-ja" など


def parse_args():
    parser = argparse.ArgumentParser(description="Ingest text/markdown files into Qdrant")
    parser.add_argument("--data_dir", type=str, default="texts", help="Directory with .txt / .md files")
    parser.add_argument("--collection", type=str, default="documents", help="Qdrant collection name")
    parser.add_argument("--chunk", type=int, default=DEFAULT_CHUNK_SIZE, help="Chunk size in characters")
    parser.add_argument("--host", type=str, default="localhost", help="Qdrant host")
    parser.add_argument("--port", type=int, default=6333, help="Qdrant REST port")
    return parser.parse_args()


def chunk_text(text: str, size: int):
    """Split text into \n-aware chunks of approximately <size> characters."""
    chunks, buf = [], ""
    for line in text.splitlines():
        if not line.strip():
            continue
        buf += line.strip() + "\n"
        if len(buf) >= size:
            chunks.append(buf.strip())
            buf = ""
    if buf:
        chunks.append(buf.strip())
    return chunks


def deterministic_id(title: str, chunk_idx: int) -> str:
    """Return stable 128-bit hex id based on title+chunk index."""
    raw = f"{title.lower()}::{chunk_idx}".encode()
    return hashlib.md5(raw).hexdigest()


def ensure_collection(client: QdrantClient, name: str, dim: int):
    if name not in [c.name for c in client.get_collections().collections]:
        client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )
        print(f"[+] Created collection '{name}'")


def ingest_directory(args):
    model = SentenceTransformer(MODEL_NAME)
    client = QdrantClient(args.host, port=args.port)
    ensure_collection(client, args.collection, model.get_sentence_embedding_dimension())

    files = glob.glob(os.path.join(args.data_dir, "*.*"))
    if not files:
        print(f"[!] '{args.data_dir}' is empty - nothing to ingest")
        return

    for fp in files:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                text = f.read()
            title = Path(fp).stem
            chunks = chunk_text(text, args.chunk)
            if not chunks:
                print(f"[!] Skipped empty file: {fp}")
                continue

            print(f"\n[+] {title}: {len(chunks)} chunks - encoding vectors …")
            vectors = model.encode(chunks, show_progress_bar=True)

            points = []
            for idx, (vec, body) in enumerate(zip(vectors, chunks), start=1):
                points.append(
                    PointStruct(
                        id=deterministic_id(title, idx),
                        vector=vec.tolist(),
                        payload={
                            "title": title,
                            "chunk_id": idx,
                            "summary": body,
                            "source": os.path.basename(fp),
                        },
                    )
                )

            client.upsert(args.collection, points)
            print(f"[✓] Upserted {len(points)} points for '{title}'")
        except Exception as exc:
            print(f"[!] Error processing {fp}: {exc}")


if __name__ == "__main__":
    ingest_directory(parse_args())
