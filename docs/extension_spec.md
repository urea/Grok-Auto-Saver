# Chrome Extension Specification

## 1. Architecture Overview
本拡張機能は、Manifest V3 に準拠した構成となっています。

### コンポーネント
- **manifest.json**: 権限設定 (`downloads`, `storage`, `tabs`, `host_permissions`)。
- **content.js**: ページ内監視、画像・動画検知、プロンプト取得。
- **background.js**: ダウンロード管理、重複チェック、データ保存、ログ記録。
- **popup.html/js**: ユーザーインターフェース（履歴表示、フォルダアクセス、設定）。

## 2. データフロー
1. **検知 (Content Script)**:
   - `MutationObserver` がDOM変化を監視。
   - 条件合致する `<img>` やプロンプトテキストを検出。
   - `chrome.runtime.sendMessage` で `background.js` へ送信。
2. **処理 (Service Worker)**:
   - メッセージを受信し、キュー (`downloadQueue`) に追加。
   - `chrome.storage.local` を参照して重複チェックを実行。
   - `chrome.downloads.download` でファイル保存を実行。
3. **完了 (Download API)**:
   - `chrome.downloads.onChanged` で完了を検知。
   - ファイル名やハッシュ値を履歴 (`chrome.storage.local`) に保存。
   - Favoritesの場合は追跡ログ (`fav_*.json`) を生成。

## 3. 主要ロジック詳細

### A. 重複防止システム (Duplicate Prevention)
- **通常画像**: URLまたはデータURIのSHA-256ハッシュ値を計算し、過去5000件の履歴と比較。
- **Favorites**:
  - URLからUUID (36文字) を抽出してIDとする。
  - 抽出できない場合は、クエリパラメータを除去したURLでハッシュ化。
  - `processingCache` (メモリ) と `storage` (ディスク) の両方をチェックし、Race Conditionを防ぐ。

### B. プロンプト保存
- **要素ベース管理**: DOM要素に `dataset.processed` フラグを付与し、同じテキストでも別要素なら保存対象とする。
- **連続重複排除**: 直前に保存したテキストと完全に一致する場合はスキップ。

### C. ファイル命名規則
- **Favorites**: `UUID.jpg` (UUID検知時)。
- **通常**: `grok_image_YYYYMMDD_HHMMSS_RAND.jpg`。
- **プロンプト**: `prompt_YYYYMMDD_... .txt`。

## 4. ストレージ設計 (`chrome.storage.local`)
| Key | 内容 | 用途 |
| :--- | :--- | :--- |
| `grok_saver_history` | ハッシュ値リスト (Max 5000) | 画像重複チェック |
| `grok_saver_filenames` | ファイル名リスト (Max 5000) | ファイル名重複チェック |
| `grok_saver_prompt_texts` | プロンプト履歴 (Max 200) | ポップアップ表示用 |
| `processed_posts` | 処理済みURLリスト | 動画自動クリック制御 |

## 5. UI機能 (Popup)
- **フォルダ**: `chrome.downloads.showDefaultFolder()` でダウンロードフォルダを開く。
- **Grok**: Favoritesページを開く。
- **履歴クリア**: `prompt_texts` を全消去。
