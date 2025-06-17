"""Simple interactive CLI on top of search.py/SearchEngine."""
import argparse
from textwrap import indent

from search import SearchEngine


def parse_args():
    p = argparse.ArgumentParser(description="Interactive CLI for Qdrant semantic search")
    p.add_argument("--collection", default="documents")
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", type=int, default=6333)
    p.add_argument("--limit", type=int, default=3)
    return p.parse_args()


def main():
    args = parse_args()
    engine = SearchEngine(collection=args.collection, host=args.host, port=args.port)

    print("[✓] Semantic search CLI ready. Type your query (q to quit)\n")
    while True:
        try:
            q = input("🔍 ")
        except (EOFError, KeyboardInterrupt):
            break
        if q.lower() in {"q", "quit", "exit"}:
            break
        if not q.strip():
            continue
        hits = engine.query(q, limit=args.limit)
        if not hits:
            print("[!] No hits\n")
            continue
        for h in hits:
            print("—" * 60)
            header = f"{h.get('title', 'N/A')}  |  chunk {h.get('chunk_id')}  |  score {h['score']:.3f}"
            print(header)
            print(indent(h.get("summary", ""), prefix="  "))
        print()


if __name__ == "__main__":
    main()
