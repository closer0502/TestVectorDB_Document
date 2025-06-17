#!/usr/bin/env python
"""
MarkdownやテキストファイルをQdrantにインジェストするスクリプト。

主な機能:
- 固定長チャンク化（デフォルト）
- Markdownヘッダーベースのチャンク化（--mode markdownオプション使用時）
- 決定論的なポイントID生成（再実行時に重複を作成しない）

使用例:
    python ingest_qdrant2.py --data_dir texts --collection documents
    python ingest_qdrant2.py --mode markdown --chunk 800 --collection docs
"""

import argparse
import hashlib
import os
import uuid
from pathlib import Path
import glob
import re

from tqdm import tqdm
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

DEFAULT_CHUNK_SIZE = 500  # デフォルトのチャンクサイズ（文字数）
MODEL_NAME = "all-MiniLM-L6-v2"  # 埋め込みモデル名（日本語の場合は "bge-small-ja" など）


def parse_args():
    """
    コマンドライン引数を解析する関数。
    
    Returns:
        argparse.Namespace: 解析された引数オブジェクト
    """
    parser = argparse.ArgumentParser(description="テキスト/markdownファイルをQdrantにインジェスト")
    parser.add_argument("--data_dir", type=str, default="texts", help=".txt / .md ファイルのディレクトリ")
    parser.add_argument("--collection", type=str, default="documents", help="Qdrantコレクション名")
    parser.add_argument("--chunk", type=int, default=DEFAULT_CHUNK_SIZE, help="文字数でのチャンクサイズ")
    parser.add_argument("--mode", type=str, choices=["fixed", "markdown"], default="fixed", help="チャンク化モード")
    parser.add_argument("--host", type=str, default="localhost", help="Qdrantホスト")
    parser.add_argument("--port", type=int, default=6333, help="Qdrant RESTポート")
    return parser.parse_args()


def chunk_text_fixed(text: str, size: int):
    """
    テキストを固定長のチャンクに分割する関数。
    
    改行を考慮し、指定された文字数を目安にテキストを分割します。
    空行は無視され、各チャンクは改行で区切られます。
    
    Args:
        text (str): 分割対象のテキスト
        size (int): チャンクの目安サイズ（文字数）
    
    Returns:
        list[str]: 分割されたテキストチャンクのリスト
    """
    chunks, buf = [], ""
    for line in text.splitlines():
        if not line.strip():
            continue  # 空行はスキップ
        buf += line.strip() + "\n"
        if len(buf) >= size:
            chunks.append(buf.strip())
            buf = ""
    if buf:
        chunks.append(buf.strip())
    return chunks


def chunk_text_markdown(text: str):
    """
    Markdownファイルをヘッダー（##）ごとに分割する関数。
    
    Args:
        text (str): 分割対象のMarkdownテキスト
    
    Returns:
        list[str]: セクションごとに分割されたテキストリスト
    """
    sections = re.split(r"(?=^##\s+)", text, flags=re.MULTILINE)
    return [s.strip() for s in sections if s.strip()]


def deterministic_id(title: str, chunk_idx: int) -> str:
    """
    タイトルとチャンク番号から決定論的なID（MD5ハッシュ）を生成する関数。
    
    Args:
        title (str): ファイル名やタイトル
        chunk_idx (int): チャンク番号
    
    Returns:
        str: 生成されたID文字列
    """
    raw = f"{title.lower()}::{chunk_idx}".encode()
    return hashlib.md5(raw).hexdigest()


def ensure_collection(client: QdrantClient, name: str, dim: int):
    """
    指定したコレクションが存在しない場合は新規作成する関数。
    
    Args:
        client (QdrantClient): Qdrantクライアント
        name (str): コレクション名
        dim (int): ベクトル次元数
    """
    if name not in [c.name for c in client.get_collections().collections]:
        client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )
        print(f"[+] Created collection '{name}'")


def ingest_directory(args):
    """
    指定ディレクトリ内のテキスト/MarkdownファイルをQdrantにインジェストするメイン関数。
    
    Args:
        args (argparse.Namespace): コマンドライン引数
    """
    model = SentenceTransformer(MODEL_NAME)
    client = QdrantClient(args.host, port=args.port)
    ensure_collection(client, args.collection, model.get_sentence_embedding_dimension())

    files = glob.glob(os.path.join(args.data_dir, "*.*"))
    if not files:
        print(f"[!] '{args.data_dir}' is empty – nothing to ingest")
        return

    for fp in files:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                text = f.read()
            title = Path(fp).stem
            if args.mode == "markdown":
                chunks = chunk_text_markdown(text)
            else:
                chunks = chunk_text_fixed(text, args.chunk)

            if not chunks:
                print(f"[!] Skipped empty file: {fp}")
                continue

            print(f"\n[+] {title}: {len(chunks)} chunks – encoding vectors …")
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
