#!/usr/bin/env python
"""
Markdown・テキスト・PDFファイルをQdrantにインジェストするスクリプト。

主な機能:
- 固定長チャンク化（デフォルト）
- Markdownヘッダーベースのチャンク化（--mode markdown）
- スマートハイブリッドチャンク化（--mode markdown-smart）
- 決定論的なポイントID生成（再実行時に重複を作成しない）

使用例:
    python ingest_qdrant.py --mode fixed
    python ingest_qdrant.py --data_dir texts --collection documents
    python ingest_qdrant.py --mode markdown --chunk 500 --collection docs
    python ingest_qdrant.py --mode markdown-smart --chunk 500 --collection docs
"""

import argparse
import hashlib
import os
import uuid
from pathlib import Path
import glob
import re
import fitz  # PyMuPDF

from tqdm import tqdm
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

DEFAULT_CHUNK_SIZE = 500  # デフォルトのチャンクサイズ（文字数）
MODEL_NAME = "all-MiniLM-L6-v2"  # 埋め込みモデル名


def parse_args(argv=None):
    """
    コマンドライン引数を解析する関数。
    
    Returns:
        argparse.Namespace: 解析された引数オブジェクト
    """
    parser = argparse.ArgumentParser(description="テキスト/markdown/pdfファイルをQdrantにインジェスト")
    parser.add_argument("--data_dir", type=str, default="texts", help=".txt / .md / .pdf ファイルのディレクトリ")
    parser.add_argument("--collection", type=str, default="documents", help="Qdrantコレクション名")
    parser.add_argument("--chunk", type=int, default=DEFAULT_CHUNK_SIZE, help="チャンクサイズ（文字数）")
    parser.add_argument("--mode", type=str, choices=["fixed", "markdown", "markdown-smart"], default="fixed", help="チャンク化モード")
    parser.add_argument("--host", type=str, default="localhost", help="Qdrantホスト")
    parser.add_argument("--port", type=int, default=6333, help="Qdrant RESTポート")
    return parser.parse_args(argv)


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


def chunk_text_markdown_smart(text: str, size: int):
    """
    Markdownのセクションごとに分割し、さらに長いセクションは固定長で分割するスマートなチャンク化関数。
    
    Args:
        text (str): 分割対象のMarkdownテキスト
        size (int): チャンクの目安サイズ（文字数）
    
    Returns:
        list[str]: 分割されたテキストチャンクのリスト
    """
    final_chunks = []
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
    """
    PDFファイルからテキストを抽出する関数。
    
    Args:
        filepath (str): PDFファイルのパス
    
    Returns:
        str: 抽出されたテキスト
    """
    doc = fitz.open(filepath)
    return "\n".join([page.get_text() for page in doc])


def extract_text_from_pdf_chunks(filepath: str) -> list[tuple[int, str]]:
    """ 
    PDFファイルからページごとにテキストを抽出する関数。

    Args:
        filepath (str): PDFファイルのパス

    Returns:
        list[tuple[int, str]]: ページ番号とテキストのタプルのリスト
    """

    doc = fitz.open(filepath)
    return [(page.number + 1, page.get_text()) for page in doc]


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
        print(f"[+] コレクション '{name}' を作成しました")
        

def ingest_directory(args):
    """
    指定ディレクトリ内のテキスト/Markdown/PDFファイルをQdrantにインジェストするメイン関数。

    Args:
        args (argparse.Namespace): コマンドライン引数
    """
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
                chunks, metadata = [], []
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
                    "source_dir": os.path.basename(os.path.dirname(fp))
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

    

if __name__ == "__main__":
    ingest_directory(parse_args())
