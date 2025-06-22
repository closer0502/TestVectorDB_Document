# TestVectorDB_Document

ローカルのテキスト・Markdownファイルをベクトル化してQdrantに保存し、自然言語で類似検索を行うプロトタイプシステムです。

## 🎯 システム概要

**処理の流れ**
1. ファイル読み込み（.txt/.md） → 2. チャンク分割（500文字単位） → 3. ベクトル化（sentence-transformers） → 4. Qdrantに保存 → 5. 自然言語クエリで類似検索

**技術構成**
- **チャンク処理**: Python（500文字 or 段落単位）
- **ベクトル化**: sentence-transformers（all-MiniLM-L6-v2）
- **ベクトルDB**: Qdrant（Dockerでローカル起動）
- **UI**: CLI（Web UIは今後追加予定）

## 📁 ディレクトリ構成

```
project-root/
├── texts/              # 入力ファイル（.txt や .md）
│   └── sample.md
├── embeddings/         # 一時ファイルやデバッグ用
├── qdrant_data/        # Docker用Qdrantデータ
├── vector_db/
│   ├── ingest.py          # インジェストロジック
│   └── search.py          # 検索ロジック
├── text2qdrant.py      # メインスクリプト
├── requirements.txt    # 必要ライブラリ
└── README.md          # このファイル
```

## 🔧 前提条件・セットアップ

### 必要環境
- Python 3.11.2
- Docker（Qdrant用）

### 1. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 2. Qdrantの起動

Dockerを使用してQdrantを起動します：

```bash
docker run -p 6333:6333 qdrant/qdrant
```

### 3. テキストファイルの配置

`texts/`ディレクトリに処理したい`.txt`または`.md`ファイルを配置します。

### 4. メインスクリプトの実行

```bash
python text2qdrant.py
```

## 🚀 使用方法

1. **ファイル処理**: `texts/`フォルダ内のすべてのファイルが自動的に処理されます
2. **ベクトル化**: 各ファイルが500文字単位でチャンクに分割され、ベクトル化されます
3. **検索**: スクリプト実行後、対話形式で検索クエリを入力できます
4. **終了**: 検索プロンプトで`q`を入力すると終了します

## ⚙️ 設定項目

`vector_db.ingest.parse_args` のデフォルト値を変更することで設定できます：

```python
DATA_DIR = "texts"              # 入力ファイルディレクトリ
COLLECTION_NAME = "documents"   # Qdrantコレクション名
CHUNK_SIZE = 500               # チャンクサイズ（文字数）
```

## 📋 必要ライブラリ

- `sentence-transformers`: テキストのベクトル化
- `qdrant-client`: Qdrantベクトルデータベースとの通信
- `tqdm`: プログレスバー表示

## 🔮 今後の拡張予定

- [ ] GPT等による要約機能の追加
- [ ] Web UI（FastAPI + React）の実装
- [ ] 日本語特化モデル（bge-small-ja）への対応
- [ ] Markdownの見出し単位での分割
- [ ] メタデータの拡充（作成日時、更新日時等）
- [ ] 複数コレクションの管理機能

## 🐛 トラブルシューティング

### Qdrantに接続できない場合
- Dockerコンテナが起動しているか確認
- ポート6333が使用可能か確認

### メモリ不足エラー
- `CHUNK_SIZE`を小さくする
- 大きなファイルを事前に分割する

### 日本語が正しく処理されない場合
- ファイルがUTF-8エンコーディングで保存されているか確認
- 日本語対応モデル（bge-small-ja）への変更を検討

## 📄 ライセンス

MIT License