"""
FastMCP を使用したMCPサーバー実装
Qdrant semantic search をMCPツールとして提供

使用例:
    python mcp_server.py
"""
import os
import shutil
import json
from typing import Optional, List, Dict, Any
from fastmcp import FastMCP
from pydantic import BaseModel

# 既存のモジュールをインポート
from search import SearchEngine
from ingest_qdrant import ingest_directory, parse_args as ingest_args, ensure_collection
from qdrant_client import QdrantClient

# グローバル変数
engine = SearchEngine()
qdrant = QdrantClient("localhost", port=6333)
UPLOAD_DIR = "uploaded"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# FastMCPサーバーの作成
mcp = FastMCP("Qdrant Semantic Search Server")


# データモデル
class SearchQuery(BaseModel):
    query: str
    limit: int = 5


class IngestRequest(BaseModel):
    file_path: str
    collection: str = "documents"
    mode: str = "fixed"


class DeleteCollectionRequest(BaseModel):
    collection: str


class DeletePointRequest(BaseModel):
    collection: str
    point_id: str


class DeleteFileRequest(BaseModel):
    filename: str


@mcp.tool()
def search(query: str, limit: int = 5) -> Dict[str, Any]:
    """Qdrantベクトルデータベースでセマンティック検索を実行"""
    if not query.strip():
        return {"error": "Empty query"}
    
    try:
        hits = engine.query(query, limit=limit)
        return {
            "status": "success",
            "query": query,
            "limit": limit,
            "results": hits
        }
    except Exception as e:
        return {"error": f"Search failed: {str(e)}"}


@mcp.tool()
def ingest_file(file_path: str, collection: str = "documents", mode: str = "fixed") -> Dict[str, Any]:
    """ファイルをアップロードしてQdrantにインデックス化"""
    if not file_path or not os.path.exists(file_path):
        return {"error": f"File not found: {file_path}"}
    
    # ファイルをアップロードディレクトリにコピー
    filename = os.path.basename(file_path)
    dest = os.path.join(UPLOAD_DIR, filename)
    
    if os.path.exists(dest):
        os.remove(dest)
        print(f"すでに存在する同名ファイルを削除しました: {dest}")
    
    try:
        shutil.copy2(file_path, dest)
        
        # インジェスト処理
        args = ingest_args(argv=[])
        args.data_dir = UPLOAD_DIR
        args.collection = collection
        args.mode = mode
        
        ingest_directory(args)
        
        return {
            "status": "success",
            "filename": filename,
            "collection": collection,
            "mode": mode
        }
    except Exception as e:
        return {"error": f"Ingest failed: {str(e)}"}


@mcp.tool()
def delete_collection(collection: str) -> Dict[str, Any]:
    """Qdrantコレクション内のすべてのポイントを削除"""
    try:
        cols = {c.name for c in qdrant.get_collections().collections}
        if collection not in cols:
            return {"error": f"Collection '{collection}' does not exist"}
        
        qdrant.delete_collection(collection)
        return {
            "status": "deleted",
            "collection": collection
        }
    except Exception as e:
        return {"error": f"Collection deletion failed: {str(e)}"}


@mcp.tool()
def delete_point(collection: str, point_id: str) -> Dict[str, Any]:
    """Qdrantコレクション内の特定のポイントを削除"""
    try:
        qdrant.delete(collection_name=collection, points_selector={"points": [point_id]})
        return {
            "status": "deleted",
            "collection": collection,
            "point_id": point_id
        }
    except Exception as e:
        return {"error": f"Point deletion failed: {str(e)}"}


@mcp.tool()
def delete_uploaded_file(filename: str) -> Dict[str, Any]:
    """アップロードディレクトリから特定のファイルを削除"""
    path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(path):
        return {"error": f"File '{filename}' not found in uploaded folder"}
    
    try:
        os.remove(path)
        return {
            "status": "deleted",
            "filename": filename
        }
    except Exception as e:
        return {"error": f"File deletion failed: {str(e)}"}


@mcp.tool()
def delete_all_uploaded_files() -> Dict[str, Any]:
    """アップロードディレクトリ内のすべてのファイルを削除"""
    try:
        deleted_files = []
        for file in os.listdir(UPLOAD_DIR):
            full_path = os.path.join(UPLOAD_DIR, file)
            if os.path.isfile(full_path):
                os.remove(full_path)
                deleted_files.append(file)
        
        return {
            "status": "deleted_all",
            "folder": UPLOAD_DIR,
            "deleted_files": deleted_files
        }
    except Exception as e:
        return {"error": f"Failed to delete uploaded files: {str(e)}"}


@mcp.tool()
def list_collections() -> Dict[str, Any]:
    """利用可能なQdrantコレクションの一覧を取得"""
    try:
        collections = qdrant.get_collections()
        collection_names = [c.name for c in collections.collections]
        return {
            "status": "success",
            "collections": collection_names
        }
    except Exception as e:
        return {"error": f"Failed to list collections: {str(e)}"}


@mcp.tool()
def list_uploaded_files() -> Dict[str, Any]:
    """アップロードディレクトリ内のファイル一覧を取得"""
    try:
        files = [f for f in os.listdir(UPLOAD_DIR) if os.path.isfile(os.path.join(UPLOAD_DIR, f))]
        return {
            "status": "success",
            "uploaded_files": files,
            "upload_directory": UPLOAD_DIR
        }
    except Exception as e:
        return {"error": f"Failed to list uploaded files: {str(e)}"}


@mcp.tool()
def get_collection_info(collection: str) -> Dict[str, Any]:
    """指定されたコレクションの詳細情報を取得"""
    try:
        cols = {c.name for c in qdrant.get_collections().collections}
        if collection not in cols:
            return {"error": f"Collection '{collection}' does not exist"}
        
        collection_info = qdrant.get_collection(collection)
        count_result = qdrant.count(collection)
        
        return {
            "status": "success",
            "collection": collection,
            "points_count": count_result.count,
            "vectors_config": collection_info.config.params.vectors,
            "distance": collection_info.config.params.vectors.get('distance', 'Unknown') if hasattr(collection_info.config.params.vectors, 'get') else 'Unknown'
        }
    except Exception as e:
        return {"error": f"Failed to get collection info: {str(e)}"}


if __name__ == "__main__":
    mcp.run()