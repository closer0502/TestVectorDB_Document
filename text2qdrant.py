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

# === ファイルを読み込んでチャンクごとにベクトル化・Qdrant登録 ===
for filepath in glob.glob(f"{DATA_DIR}/*.*"):
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()
    title = Path(filepath).stem
    chunks = chunk_text(text)

    print(f"\n[+] 処理中: {title} ({len(chunks)}チャンク)")

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

print("\n[✓] 登録完了")

# === CLI検索 ===
while True:
    query = input("\n🔍 検索クエリを入力（終了は 'q'）： ")
    if query.lower() == 'q':
        break
    vec = model.encode(query).tolist()
    results = client.search(collection_name=COLLECTION_NAME, query_vector=vec, top=3)

    print("\n--- 検索結果 ---")
    for r in results:
        print(f"[{r.payload['title']} - chunk {r.payload['chunk_id']}]\n{r.payload['summary']}\n---")
