@echo off
echo [✓] Python仮想環境を作成中...
python.exe -m pip install --upgrade pip
python -m venv venv

echo [✓] 仮想環境を有効化...
call venv\Scripts\activate

echo [✓] ライブラリをインストール中...
python.exe -m pip install --upgrade pip
python.exe -m pip install sentence-transformers qdrant-client tqdm

echo [✓] 必要なディレクトリを作成中...
mkdir texts
mkdir embeddings
mkdir qdrant_data

echo [✓] QdrantをDockerで起動中...
docker run -d -p 6333:6333 -v %cd%\qdrant_data:/qdrant/storage --name qdrant_local qdrant/qdrant

echo.
echo [✓] セットアップ完了！
echo [i] venvはこのウィンドウで有効化されています。
echo [i] texts フォルダに .txt や .md を入れて text2qdrant.py を実行してね。
echo [i] Qdrant 管理API: http://localhost:6333
echo.
pause
