import os
from textwrap import indent

from vector_db.ingest import ingest_directory, parse_args
from vector_db.search import SearchEngine


def main() -> None:
    args = parse_args(argv=None)
    ingest_directory(args)

    engine = SearchEngine(collection=args.collection, host=args.host, port=args.port)
    print("\n[✓] 登録完了")

    while True:
        query = input("\n🔍 検索クエリを入力（終了は 'q'）： ")
        if query.lower() == 'q':
            break
        hits = engine.query(query, limit=3)
        print("\n--- 検索結果 ---")
        for h in hits:
            header = f"[{h.get('title')} - chunk {h.get('chunk_id')}] score {h['score']:.3f}"
            print(header)
            print(indent(h.get('summary', ''), '  '))
            print("---")


if __name__ == "__main__":
    main()
