#!/bin/bash

echo "[✓] Python仮想環境を作成中..."
python3 -m pip install --upgrade pip
python3 -m venv venv

echo "[✓] 仮想環境を有効化..."
source venv/bin/activate

echo "[✓] ライブラリをインストール中..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "[✓] 必要なディレクトリを作成中..."
mkdir -p texts
mkdir -p embeddings
mkdir -p qdrant_data

echo "[✓] QdrantをDockerで起動中..."
docker run -d -p 6333:6333 -v $(pwd)/qdrant_data:/qdrant/storage --name qdrant_local qdrant/qdrant

echo
echo "[✓] セットアップ完了！"
echo "[i] 仮想環境を有効化するには: source venv/bin/activate"
echo "[i] texts フォルダに .txt や .md を入れて text2qdrant.py を実行してね。"
echo "[i] Qdrant 管理API: http://localhost:6333"
echo
