"""
Qdrantからコレクションを安全に削除するユーティリティスクリプト。

使い方：
    python delete_collection.py --collection documents

現在のポイント数を表示し、確認後に削除を実行します。
"""
import argparse
from qdrant_client import QdrantClient


def parse_args():
    """
    コマンドライン引数を解析する関数。
    
    Returns:
        argparse.Namespace: 解析された引数オブジェクト
    """
    p = argparse.ArgumentParser(description="Qdrantコレクションを削除（確認付き）")
    p.add_argument("--collection", required=True, help="削除対象のコレクション名")
    p.add_argument("--host", default="localhost", help="Qdrantホスト名")
    p.add_argument("--port", type=int, default=6333, help="QdrantのRESTポート番号")
    return p.parse_args()


def main():
    """
    指定したQdrantコレクションを削除するメイン関数。
    
    1. コレクションの存在確認
    2. ポイント数の表示
    3. ユーザーに削除確認
    4. 削除実行または中断
    """
    args = parse_args()
    client = QdrantClient(args.host, port=args.port)

    # コレクション一覧を取得し、存在確認
    cols = {c.name: c for c in client.get_collections().collections}
    if args.collection not in cols:
        print(f"[!] Collection '{args.collection}' does not exist - nothing to delete.")
        return

    # ポイント数を取得し表示
    points = client.count(args.collection, exact=False).count
    print(f"[i] Collection '{args.collection}' exists with ~{points} points.")
    confirm = input("❗ 本当にこのコレクションを削除しますか？続行するには 'yes' と入力してください: ")
    if confirm.lower() == "yes":
        client.delete_collection(args.collection)
        print("[✓] コレクションを削除しました。")
    else:
        print("[-] 削除を中断しました。")


if __name__ == "__main__":
    main()
