from fastapi import FastAPI
from fastapi_mcp import FastApiMCP
from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel


"""uvicorn test_text_board_fapi_mcp:app --host 0.0.0.0 --port 8000
"""


app = FastAPI()
messages = []

class AddInput(BaseModel):
    msg: str
    

# 1️⃣ 先に JSON を返す /mcp を登録
TOOLS_JSON = {
"tools": [
        {
            "name": "append_message",
            "description": "Post a single text message to the shared board.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "msg": {"type": "string"}
                },
                "required": ["msg"]
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "msg_count": {"type": "integer"}
                },
                "required": ["status", "msg_count"]
            }
        },
        {
            "name": "get_messages",
            "description": "Returns an array of all posted messages.",
            "input_schema": {
                "type": "object",
                "properties": {}
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "messages": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                },
                "required": ["messages"]
            }
        }
    ]
}

@app.get("/mcp", include_in_schema=False)
@app.post("/mcp", include_in_schema=False)
def mcp_root():
    # application/json で返す
    return JSONResponse(TOOLS_JSON)


# 2️⃣ その **あとで** FastApiMCP をマウント
mcp = FastApiMCP(app)
mcp.mount()                     # これが /mcp/messages/** と /mcp/call/** だけを追加

@app.post(
    "/add",
    operation_id="append_message",
    description="メッセージを投稿し、履歴に追加します"
)
def add(data: AddInput):
    messages.append(data.msg)
    return {"status": "ok", "msg_count": len(messages)}

@app.get(
    "/all",
    operation_id="get_messages",
    description="すべての投稿メッセージを取得します"
)
def get_all():
    return {"messages": messages}
