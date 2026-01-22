# Grok Organizer Logic Specification

## 1. 概要
`grok_organizer.py` は、拡張機能によってダウンロードされたデータを整理・加工・可視化するためのPythonスクリプトです。

## 2. フォルダ構成
整理後のディレクトリ構造 (`_App` / `_Dev` 対応) に基づきます。
詳細は [top.md](../top.md) または `_Data` フォルダを参照してください。

## 3. 実行フロー (`main`関数)
スクリプト実行時、以下の順序で関数が呼び出されます。

1. **`move_videos()`**: ダウンロードフォルダ直下の動画を整理
2. **`clean_garbage_images()`**: 不要画像の削除
3. **`organize_prompts()`**: プロンプトテキストの統合
4. **`organize_favorites()`**: Favoritesログの統合
5. **`generate_viewer_html()`**: Viewer (HTML) の生成

## 4. 詳細ロジック

### A. 動画移動 (`move_videos`)
- **対象**: `Downloads/grok-video-*.mp4`
- **処理**:
  1. ファイルのタイムスタンプから日付フォルダ (`_Data/Images/YYYYMMDD`) を決定。
  2. ファイル名に日時 (`YYYYMMDD_HHMMSS`) を付与してリネーム移動。
  3. 同名ファイルがある場合は連番を付与。

### B. 画像クリーニング (`clean_garbage_images`)
- **対象**: `_Data/**/*.jpg|png|webp`
- **除外**: `System`, `Prompts` フォルダ内の画像は対象外。
- **削除条件**:
  1. **ファイルサイズ**: 100KB 未満。
  2. **解像度**: 幅または高さの最小値が 500px 未満 (Pillowライブラリが必要)。
  3. **プロファイル画像**: `profile-picture.webp`。

### C. プロンプト統合 (`organize_prompts`)
- **読み込み**: `_Data/Prompts/*.txt` および既存の `All_Prompts_Merged.txt`。
- **解析**: 正規表現で `[YYYY/MM/DD ...]` 形式のヘッダを認識。
- **マージ**:
  - 全てのエントリを日付順（新しい順）にソート。
  - 内容が**完全に連続して重複**している場合のみ排除。
  - 最新の `All_Prompts_Merged.txt` を生成。
- **アーカイブ (1世代管理)**:
  - 処理済みの個別テキストファイル (`prompt_*.txt`) は `Archived` フォルダへ移動。
  - **移動前に `Archived` フォルダを空にする** ことで、常に最新の1世代分（＝直近の実行で処理された分）のみをバックアップとして残す。

### D. Favoritesログ統合 (`organize_favorites`)
- **対象**: `_Data/System/FavLogs/*.json`
- **処理**:
  - JSONログから `filename` と `uuid` のペアを抽出。
  - `_Data/System/All_Favorites_Merged.json` に追記保存。
- **アーカイブ**: プロンプト同様、1世代管理ポリシーで `FavLogs/Archived` に移動。

### E. Viewer生成 (`generate_viewer_html`)
- **データ収集**: `_Data` 以下の全画像・動画・プロンプト・Favorites情報を集約。
- **HTML出力**:
  - `Grok_Viewer.html` をルートディレクトリに出力。
  - JavaScriptを含んだ単一のHTMLファイルとして生成（外部依存なし）。
  - 機能: タイムライン表示、Favoritesフィルタ、キーワード検索、モーダルプレビュー。
