"""
使用例:
    uvicorn run_fastapi:app --reload
"""
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi_mcp import FastApiMCP
from pydantic import BaseModel
from typing import Optional
import shutil
import os

from search import SearchEngine
from vectorDB.ingest_qdrant import ingest_directory, parse_args as ingest_args, ensure_collection
from qdrant_client import QdrantClient
from config import Settings


app = FastAPI(title="Qdrant Semantic Search API")
# 追加: MCPサーバーのセットアップ
mcp = FastApiMCP(app)
mcp.mount()  # /mcp エンドポイントをFastAPIアプリに追加

engine = SearchEngine()

qdrant = QdrantClient(
    host=Settings.QDRANT_HOST,
    port=Settings.QDRANT_PORT,
)

UPLOAD_DIR = "uploaded"
os.makedirs(UPLOAD_DIR, exist_ok=True)


class SearchRequest(BaseModel):
    query: str
    limit: int = 5


@app.post("/search")
async def search(req: SearchRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Empty query")
    try:
        hits = engine.query(req.query, limit=req.limit)
        return {"results": hits}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/ingest")
async def ingest(
    file: UploadFile = File(...),
    collection: str = Form("documents"),
    mode: str = Form("fixed"),
):
    filename = file.filename
    dest = os.path.join(UPLOAD_DIR, filename)

    if os.path.exists(dest):
        os.remove(dest)
        print(f"すでに存在する同名ファイルを削除しました: {dest}")

    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    args = ingest_args(argv=[])
    args.data_dir = UPLOAD_DIR
    args.collection = collection
    args.mode = mode
    args.port = Settings.QDRANT_PORT
    args.host = Settings.QDRANT_HOST
    

    try:
        ingest_directory(args)
        return {"status": "success", "filename": filename, "collection": collection}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/delete_all_points")
async def delete_all_points(
    collection: str = Form(...),
):
    cols = {c.name for c in qdrant.get_collections().collections}
    if collection not in cols:
        raise HTTPException(status_code=404, detail=f"Collection '{collection}' does not exist.")
    qdrant.delete_collection(collection)
    return {"status": "deleted", "collection": collection}


@app.post("/delete_point")
async def delete_point(
    collection: str = Form(...),
    point_id: str = Form(...),
):
    try:
        qdrant.delete(collection_name=collection, points_selector={"points": [point_id]})
        return {"status": "deleted", "collection": collection, "point_id": point_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deletion failed: {e}")


@app.post("/delete_uploaded_file")
async def delete_uploaded_file(
    filename: str = Form(...),
):
    path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"File '{filename}' not found in uploaded folder.")
    try:
        os.remove(path)
        return {"status": "deleted", "filename": filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {e}")


@app.post("/delete_uploaded_all_files")
async def delete_uploaded_all_files():
    try:
        for file in os.listdir(UPLOAD_DIR):
            full_path = os.path.join(UPLOAD_DIR, file)
            if os.path.isfile(full_path):
                os.remove(full_path)
        return {"status": "deleted_all", "folder": UPLOAD_DIR}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete uploaded folder contents: {e}")


@app.get("/")
async def root():
    return {"msg": "Use /search, /ingest, /delete_all_points, /delete_point, /delete_uploaded_file, /delete_uploaded_all_files endpoints."}
