"""
FastMCP を使用したシンプルなテスト用サーバー
文章の追加・取得・削除機能を提供

使用例:
    python test_server.py
"""
import datetime
from typing import List, Dict, Any, Optional
from fastmcp import FastMCP

# グローバル変数として文章を保存する配列
messages: List[Dict[str, Any]] = []
message_counter = 0

# FastMCPサーバーの作成
mcp = FastMCP("Simple Text Storage Server")


@mcp.tool()
def add_message(text: str, author: str = "Anonymous") -> Dict[str, Any]:
    """文章をメッセージ配列に追加する（POST相当）"""
    global message_counter
    message_counter += 1
    
    message = {
        "id": message_counter,
        "text": text,
        "author": author,
        "timestamp": datetime.datetime.now().isoformat(),
        "length": len(text)
    }
    
    messages.append(message)
    
    return {
        "status": "success",
        "message": "Message added successfully",
        "data": message,
        "total_messages": len(messages)
    }


@mcp.tool()
def get_messages(limit: int = 10, offset: int = 0) -> Dict[str, Any]:
    """メッセージ配列を取得する（GET相当）"""
    try:
        # ページネーション
        start = offset
        end = offset + limit
        paginated_messages = messages[start:end]
        
        return {
            "status": "success",
            "data": paginated_messages,
            "pagination": {
                "total": len(messages),
                "limit": limit,
                "offset": offset,
                "returned": len(paginated_messages)
            }
        }
    except Exception as e:
        return {"error": f"Failed to get messages: {str(e)}"}



if __name__ == "__main__":
    # 初期データを追加（テスト用）
    #add_message("Hello, World!", "System")
    #add_message("This is a test message.", "TestUser")
    #add_message("FastMCPを使ったシンプルなメッセージストレージです。", "Admin")
    
    print("Simple Text Storage Server starting...")
    print("Available tools:")
    print("- add_message: Add a new message")
    print("- get_messages: Get all messages (with pagination)")
    """
    print("- get_message_by_id: Get specific message by ID")
    print("- update_message: Update message text")
    print("- delete_message: Delete message by ID")
    print("- clear_all_messages: Delete all messages")
    print("- get_statistics: Get message statistics")
    print("- search_messages: Search messages by keyword")
    print("- add_bulk_messages: Add multiple messages at once")
    """
    
    
    mcp.run()