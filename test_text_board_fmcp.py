# textboard_fastmcp.py
from fastmcp import FastMCP, tool      # pip install fastmcp>=2.0

mcp = FastMCP("TextBoard Server")

# ────────────────────────────────────
# メッセージを保持するだけの超シンプル状態
messages: list[str] = []

# ① メッセージを追加
@tool(
    name="append_message",
    description="Post a single text message to the shared board.",
    input_schema={
        "type": "object",
        "properties": {"msg": {"type": "string"}},
        "required": ["msg"]
    },
    output_schema={
        "type": "object",
        "properties": {
            "status":    {"type": "string"},
            "msg_count": {"type": "integer"}
        },
        "required": ["status", "msg_count"]
    },
)
def append_message(msg: str) -> dict:        # ↖ 型ヒントは任意
    messages.append(msg)
    return {"status": "ok", "msg_count": len(messages)}

# ② 全メッセージを取得
@tool(
    name="get_messages",
    description="Return an array of all posted messages.",
    input_schema={
        "type": "object",
        "properties": {}
    },
    output_schema={
        "type": "object",
        "properties": {
            "messages": {
                "type":  "array",
                "items": {"type": "string"}
            }
        },
        "required": ["messages"]
    },
)
def get_messages() -> dict:
    return {"messages": messages}

# エントリポイント ─────────────────
if __name__ == "__main__":
    # --transport sse で /mcp/messages/** が生える
    # 8000 番で待ち受け。必要なら --host/--port で変更可
    # python test_text_board_fmcp.py
    mcp.run(transport="sse", host="0.0.0.0", port=8000)
