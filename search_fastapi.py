"""SearchEngineを使用して/searchエンドポイントを公開するFastAPIラッパー。
    環境変数でQdrantのホスト、ポート、コレクション名を設定できます。
    デフォルトはそれぞれlocalhost、6333、documentsです。
    uvicorn search_fastapi:app --reload
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from search import SearchEngine

app = FastAPI(title="Qdrant セマンティック検索 API")
engine = SearchEngine()  # 環境変数 / デフォルト値を使用

class SearchRequest(BaseModel):
    query: str
    limit: int = 5


@app.post("/search")
async def search(req: SearchRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="空のクエリ")
    try:
        hits = engine.query(req.query, limit=req.limit)
        return {"results": hits}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/")
async def root():
    return {"msg": "POST /search を使用してください。形式: {'query': '...', 'limit': N}"}
