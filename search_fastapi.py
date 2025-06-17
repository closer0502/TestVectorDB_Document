"""FastAPI wrapper exposing /search endpoint using SearchEngine."""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from search import SearchEngine

app = FastAPI(title="Qdrant Semantic Search API")
engine = SearchEngine()  # uses env vars / defaults


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


@app.get("/")
async def root():
    return {"msg": "Use POST /search with {'query': '...', 'limit': N}"}
