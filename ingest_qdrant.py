#!/usr/bin/env python
"""
MarkdownやテキストファイルをQdrantにインジェストする。
- 各ファイルを固定長のチャンク（デフォルト500文字）に分割
- 決定論的なポイントIDを生成するため、再実行時に重複を作成しない
- ベクトル + ペイロードをターゲットコレクションにアップサート
使用法::
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
    parser = argparse.ArgumentParser(description="テキスト/markdownファイルをQdrantにインジェスト")
    parser.add_argument("--data_dir", type=str, default="texts", help=".txt / .md ファイルのディレクトリ")
    parser.add_argument("--collection", type=str, default="documents", help="Qdrantコレクション名")
    parser.add_argument("--chunk", type=int, default=DEFAULT_CHUNK_SIZE, help="文字数でのチャンクサイズ")
    parser.add_argument("--host", type=str, default="localhost", help="Qdrantホスト")
    parser.add_argument("--port", type=int, default=6333, help="Qdrant RESTポート")
    return parser.parse_args()


def chunk_text(text: str, size: int):
    """テキストを改行を考慮して約<size>文字のチャンクに分割する。"""
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
    """タイトル+チャンクインデックスに基づく安定した128ビットhex idを返す。"""
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
