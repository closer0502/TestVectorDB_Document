"""Ingestion utilities for loading text, markdown and PDF files into Qdrant."""

from __future__ import annotations

import argparse
import glob
import hashlib
import os
import re
from pathlib import Path
from typing import Iterable, List, Tuple

import fitz  # PyMuPDF
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

DEFAULT_CHUNK_SIZE = 500
MODEL_NAME = "all-MiniLM-L6-v2"


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for ingestion commands."""
    parser = argparse.ArgumentParser(description="テキスト/markdown/pdfファイルをQdrantにインジェスト")
    parser.add_argument("--data_dir", type=str, default="texts", help=".txt / .md / .pdf ファイルのディレクトリ")
    parser.add_argument("--collection", type=str, default="documents", help="Qdrantコレクション名")
    parser.add_argument("--chunk", type=int, default=DEFAULT_CHUNK_SIZE, help="チャンクサイズ（文字数）")
    parser.add_argument(
        "--mode",
        type=str,
        choices=["fixed", "markdown", "markdown-smart"],
        default="fixed",
        help="チャンク化モード",
    )
    parser.add_argument("--host", type=str, default="localhost", help="Qdrantホスト")
    parser.add_argument("--port", type=int, default=6333, help="Qdrant RESTポート")
    return parser.parse_args(argv)


def chunk_text_fixed(text: str, size: int) -> List[str]:
    """Split text into fixed size chunks."""
    chunks: List[str] = []
    buf = ""
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


def chunk_text_markdown(text: str) -> List[str]:
    """Split markdown text by second level headings."""
    sections = re.split(r"(?=^##\s+)", text, flags=re.MULTILINE)
    return [s.strip() for s in sections if s.strip()]


def chunk_text_markdown_smart(text: str, size: int) -> List[str]:
    """Hybrid markdown chunking with fallback to fixed size."""
    final_chunks: List[str] = []
    sections = re.split(r"(?=^##\s+)", text, flags=re.MULTILINE)
    for s in sections:
        s = s.strip()
        if not s:
            continue
        if len(s) <= size * 1.5:
            final_chunks.append(s)
        else:
            final_chunks.extend(chunk_text_fixed(s, size))
    return final_chunks


def extract_text_from_pdf(filepath: str) -> str:
    """Extract plain text from a PDF file."""
    doc = fitz.open(filepath)
    return "\n".join(page.get_text() for page in doc)


def extract_text_from_pdf_chunks(filepath: str) -> List[Tuple[int, str]]:
    """Extract text page by page from a PDF file."""
    doc = fitz.open(filepath)
    return [(page.number + 1, page.get_text()) for page in doc]


def deterministic_id(title: str, chunk_idx: int) -> str:
    """Generate a deterministic ID from title and chunk index."""
    raw = f"{title.lower()}::{chunk_idx}".encode()
    return hashlib.md5(raw).hexdigest()


def ensure_collection(client: QdrantClient, name: str, dim: int) -> None:
    """Create collection if it doesn't exist."""
    if name not in [c.name for c in client.get_collections().collections]:
        client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )
        print(f"[+] コレクション '{name}' を作成しました")


def ingest_directory(args: argparse.Namespace) -> None:
    """Ingest files under the given directory into Qdrant."""
    model = SentenceTransformer(MODEL_NAME)
    client = QdrantClient(args.host, port=args.port)
    ensure_collection(client, args.collection, model.get_sentence_embedding_dimension())

    files = glob.glob(os.path.join(args.data_dir, "*.*"))
    if not files:
        print(f"[!] '{args.data_dir}' ディレクトリが空です。インジェストするファイルがありません。")
        return

    print(f"[+] {len(files)} 件のファイルを検出しました: {', '.join(os.path.basename(fp) for fp in files)}")
    print("[+] ファイルを処理中 …")

    for fp in files:
        try:
            ext = Path(fp).suffix.lower()
            title = Path(fp).stem

            if ext == ".pdf":
                page_chunks = extract_text_from_pdf_chunks(fp)
                chunks: List[str] = []
                metadata: List[int | None] = []
                for page_num, text in page_chunks:
                    split = chunk_text_fixed(text, args.chunk)
                    chunks.extend(split)
                    metadata.extend([page_num] * len(split))
            else:
                with open(fp, "r", encoding="utf-8") as f:
                    text = f.read()
                if args.mode == "markdown-smart" and ext != ".pdf":
                    chunks = chunk_text_markdown_smart(text, args.chunk)
                elif args.mode == "markdown" and ext != ".pdf":
                    chunks = chunk_text_markdown(text)
                else:
                    chunks = chunk_text_fixed(text, args.chunk)
                metadata = [None] * len(chunks)

            if not chunks:
                print(f"[!] 空ファイルをスキップ: {fp}")
                continue

            print(f"\n[+] {title}: {len(chunks)} チャンク - ベクトルをエンコード中 …")
            vectors = model.encode(chunks, show_progress_bar=True)

            points = []
            for idx, (vec, body) in enumerate(zip(vectors, chunks), start=1):
                payload = {
                    "title": title,
                    "chunk_id": idx,
                    "summary": body,
                    "source": os.path.basename(fp),
                    "source_type": ext.lstrip("."),
                    "source_dir": os.path.basename(os.path.dirname(fp)),
                }
                if metadata[idx - 1] is not None:
                    payload["page"] = metadata[idx - 1]
                points.append(
                    PointStruct(
                        id=deterministic_id(title, idx),
                        vector=vec.tolist(),
                        payload=payload,
                    )
                )

            client.upsert(args.collection, points)
            print(f"[✓] {len(points)}件のポイントを '{title}' にアップサートしました")
        except Exception as exc:
            print(f"[!] {fp} の処理中にエラー: {exc}")
