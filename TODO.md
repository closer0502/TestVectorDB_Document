# TODO List

## 🔜 MCP統合用機能
- [ ] `/ingest` ファイルアップロードAPI
- [ ] `/delete_collection` API実装
- [ ] `/collections` 管理API（切り替え、一覧取得）
- [ ] 検索クエリ整形オプション追加
- [ ] クエリログ保存・キャッシュ検討

## 🧠 実装検討中
- [ ] LLM統合・プロンプト用API (`/context`)

## 🏷️ 実装済み
- [x] PDFチャンクページ番号対応
- [x] Markdown-smart チャンク化

✅ MCP統合に向けて必要な主要機能一覧
🔹 1. 外部操作API
機能	内容
/search	クエリを投げて意味検索（既にある）
/ingest	テキスト/Markdown/PDFをアップロードしてDBに登録
/delete_collection	明示的にコレクションを削除（デバッグ・初期化用）
/status	登録済み件数、コレクション一覧などの情報提供
/collections/switch	使用するコレクションを動的に切り替える（プロジェクト単位）

🔹 2. HAL/LLM向けメタ設計
要素	内容
🔁 idempotency	再送時に誤動作しない（再インジェスト等）
📎 payloadにメタ情報	page, source_type, source_url, chunk_idなど
🧠 HALが「検索→再検索→再要約」できる設計	クエリ履歴や中間出力も管理できる設計だとベスト

🔹 3. MCP固有要件（HAL/LLMからの操作系）
機能	説明
ファイルアップロード（POST）	LLMから送られたファイルをDBに登録（型含む）
クエリ生成の自由度	"○○に関する仕様を探して"といった曖昧命令にも応答できる必要
検索結果整形	title, chunk_id, score, summary, page を人間 or LLM向けに整える
複数コレクションの切替	コマンドで "コレクション: 仕様書モード" と言われたら切替可能にする必要

🔹 4. LLM連携用（おまけ）
機能	役割
クエリログ保存	HALが過去の検索や結果を「参照」できる
/context?query=...	結果をプロンプト用に整形して返す（JSONではなく文字列）
キャッシュ処理	同一クエリの再検索時はキャッシュで返す設計も考慮

🎯 最初に作るべき最小構成（MVP）
✅ /search（既にある）

🆕 /ingest（ファイルアップロードして即インジェスト）

🆕 /delete_collection（安全に空にする）

🆕 /switch_collection or /use/{name}（対象切り替え）

次にやるなら：

/ingest を FastAPI の UploadFile 経由で追加

その後 /collections 系の管理APIも足す

進めていい？それとも優先順変える？

