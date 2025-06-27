"""
run_fastmcp.py – FastMCP 2.0 版 Qdrant Semantic Search サーバー

起動例:
    # 最もシンプル – stdio で MCP だけ公開
    python run_fastmcp.py

    # HTTP 経由 (ストリーム対応) で公開
    fastmcp run run_fastmcp.py:mcp --transport http --host 0.0.0.0 --port 8000
         # → MCP エンドポイント: http://localhost:8000/mcp/…

依存:
    pip install fastmcp qdrant-client
"""
import os
import shutil
from pathlib import Path
from typing import Dict, List

# FastMCP
from fastmcp import FastMCP
from fastmcp.utilities.types import File  # バイナリ返却用ヘルパ
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse

# アプリ固有
from search import SearchEngine
from ingest_qdrant import ingest_directory, parse_args as ingest_args
from qdrant_client import QdrantClient

###############################################################################
# 基本セットアップ
###############################################################################
UPLOAD_DIR = Path("uploaded")
UPLOAD_DIR.mkdir(exist_ok=True)

engine = SearchEngine()
qdrant = QdrantClient("localhost", port=6333)

mcp = FastMCP("Qdrant Semantic Search MCP Server")

###############################################################################
# MCP ツール定義 (@mcp.tool)
###############################################################################
@mcp.tool
def search(query: str, limit: int = 5) -> Dict[str, List[dict]]:
    """
    ベクトル検索を実行し、上位 `limit` 件のヒットを返します。
    """
    if not query.strip():
        raise ValueError("query must not be empty")
    hits = engine.query(query, limit=limit)
    return {"results": hits}


@mcp.tool
def ingest(
    filename: str,
    collection: str = "documents",
    mode: str = "fixed",
) -> dict:
    """
    アップロード済みファイルをベクトル化して Qdrant に投入します。
    `filename` は `uploaded/` 配下に存在する必要があります。
    """
    src = UPLOAD_DIR / filename
    if not src.exists():
        raise FileNotFoundError(f"{src} not found; first POST /upload")
    args = ingest_args(argv=[])
    args.data_dir = str(UPLOAD_DIR)
    args.collection = collection
    args.mode = mode
    ingest_directory(args)
    return {"status": "success", "filename": filename, "collection": collection}


@mcp.tool
def delete_all_points(collection: str) -> dict:
    """指定コレクションを丸ごと削除。"""
    cols = {c.name for c in qdrant.get_collections().collections}
    if collection not in cols:
        raise ValueError(f"Collection '{collection}' does not exist.")
    qdrant.delete_collection(collection)
    return {"status": "deleted", "collection": collection}


@mcp.tool
def delete_point(collection: str, point_id: str) -> dict:
    """ポイント ID を 1 件削除。"""
    qdrant.delete(collection_name=collection, points_selector={"points": [point_id]})
    return {"status": "deleted", "collection": collection, "point_id": point_id}


@mcp.tool
def delete_uploaded_file(filename: str) -> dict:
    """アップロード済みファイルを 1 件削除。"""
    path = UPLOAD_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"{filename} not found in {UPLOAD_DIR}")
    path.unlink()
    return {"status": "deleted", "filename": filename}


@mcp.tool
def delete_uploaded_all_files() -> dict:
    """uploaded/ フォルダ内のファイルをすべて削除。"""
    for f in UPLOAD_DIR.iterdir():
        if f.is_file():
            f.unlink()
    return {"status": "deleted_all", "folder": str(UPLOAD_DIR)}

###############################################################################
# HTTP ルート (オプション)
###############################################################################
# FastMCP 独自の @custom_route で、ファイルアップロード等の
# Web‑UI / curl 用エンドポイントを追加可能 :contentReference[oaicite:0]{index=0}
@mcp.custom_route("/", methods=["GET"])
async def root() -> PlainTextResponse:
    return PlainTextResponse(
        "Available MCP tools: search, ingest, delete_*.\n"
        "Optional HTTP route: POST /upload for file ingestion."
    )


@mcp.custom_route("/upload", methods=["POST"])
async def upload(request: Request) -> JSONResponse:
    """
    multipart/form-data:
        file=<UploadFile>
        collection=<str|optional>
        mode=<str|optional>
    成功すると self.ingest を自動実行し、Qdrant に投入。
    """
    form = await request.form()
    upload_file = form.get("file")
    if upload_file is None or upload_file.filename == "":
        return JSONResponse({"detail": "file missing"}, status_code=400)

    collection = form.get("collection", "documents")
    mode = form.get("mode", "fixed")

    dest = UPLOAD_DIR / upload_file.filename
    if dest.exists():
        dest.unlink()  # 上書き
    with dest.open("wb") as f:
        shutil.copyfileobj(upload_file.file, f)

    # ベクトル化＆投入
    ingest(dest.name, collection=collection, mode=mode)
    return JSONResponse(
        {"status": "success", "filename": dest.name, "collection": collection}
    )

###############################################################################
# エントリーポイント
###############################################################################
if __name__ == "__main__":
    # stdio で起動。HTTP で動かす場合は CLI: fastmcp run ...
    mcp.run()
