import os
import glob
import uuid
from pathlib import Path
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from tqdm import tqdm

# === 設定 ===
DATA_DIR = "texts"
COLLECTION_NAME = "documents"
CHUNK_SIZE = 500  # 文字数でチャンク化

# === モデルとQdrantの初期化 ===
model = SentenceTransformer("all-MiniLM-L6-v2")  # 日本語なら bge-small-ja にしてもOK
client = QdrantClient("localhost", port=6333)

# === コレクション作成（なければ） ===
if COLLECTION_NAME not in [col.name for col in client.get_collections().collections]:
    client.recreate_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=model.get_sentence_embedding_dimension(), distance=Distance.COSINE)
    )

# === チャンク処理 ===
def chunk_text(text, chunk_size=CHUNK_SIZE):
    chunks = []
    buf = ""
    for line in text.splitlines():
        if line.strip() == "":
            continue
        buf += line.strip() + "\n"
        if len(buf) >= chunk_size:
            chunks.append(buf.strip())
            buf = ""
    if buf:
        chunks.append(buf.strip())
    return chunks


# === ファイルが存在するか確認 ===
files = glob.glob(f"{DATA_DIR}/*.*")
if not files:
    print(f"[!] エラー: '{DATA_DIR}' フォルダに処理対象ファイルがありません。")
    exit(1)

# === ファイルを読み込んでチャンクごとにベクトル化・Qdrant登録 ===
for filepath in files:
    try:
        print(f"\n[+] ファイル読み込み中: {filepath}")
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()
        title = Path(filepath).stem
        chunks = chunk_text(text)

        if not chunks:
            print(f"[!] スキップ: 空のテキスト or チャンクなし -> {title}")
            continue

        print(f"[✓] チャンク数: {len(chunks)} - ベクトル化中...")
        vectors = model.encode(chunks, show_progress_bar=True)

        points = []
        for i, (vec, chunk) in enumerate(zip(vectors, chunks)):
            points.append(PointStruct(
                id=str(uuid.uuid4()),
                vector=vec.tolist(),
                payload={
                    "title": title,
                    "chunk_id": i + 1,
                    "summary": chunk,
                    "source": os.path.basename(filepath),
                }
            ))

        client.upsert(collection_name=COLLECTION_NAME, points=points)
        print(f"[✓] 登録完了: {title} ({len(points)} 件)")

    except Exception as e:
        print(f"[!] エラー: {filepath} の処理中に問題が発生しました -> {e}")

print("\n[✓] 登録完了")


# === CLI検索 ===
while True:
    query = input("\n🔍 検索クエリを入力（終了は 'q'）： ")
    if query.lower() == 'q':
        break
    vec = model.encode(query).tolist()
    results = client.search(collection_name=COLLECTION_NAME, query_vector=vec, limit=3)

    print("\n--- 検索結果 ---")
    for r in results:
        print(f"[{r.payload['title']} - chunk {r.payload['chunk_id']}]\n{r.payload['summary']}\n---")
