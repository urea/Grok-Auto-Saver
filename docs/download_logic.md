# Grok Imagine 画像ダウンロード判定条件

`https://grok.com/imagine` ページにおいて、拡張機能が画像を「保存対象」と判定し、ダウンロード処理を開始するための条件は以下の通りです。

## 1. 検出トリガー (Trigger)
画面上の変化を常に監視 (`MutationObserver`) しており、以下のタイミングで判定処理が走ります。
- 新しい画像要素 (`<img>`) がDOMに追加された時
- 既存の画像要素の `src` 属性（URL）が変更された時

## 2. 必須条件 (Requirements)
以下の**すべて**を満たす場合に保存対象となります。

### A. 画像の特定 (Target Identification)
以下の**いずれか**に該当すること：
- `alt` 属性が `"Generated image"` である
- `src` (URL) に文字列 `"grok"` が含まれている

### B. サイズ要件 (Size Requirement)
- 推定ファイルサイズが **50KB以上** であること
  - Base64画像の場合: データ長から計算
  - 通常URL画像の場合: 一律100KBとみなして通過（実際のサイズフィルタは保存後にOrganizerが行う）

### C. 読み込み状態 (Loading State)
- 画像の読み込みが完了していること (`img.complete` is true)
- 画像の幅が0ではないこと (`img.naturalWidth` > 0)

### D. 重複除外 (Client-side Deduplication)
- そのページを表示してから、既に同じURLの処理を行っていないこと
  - (`processedCache` に URL が存在しないこと)

## 3. 処理フロー
1. 条件合致 -> `background.js` へダウンロードリクエスト送信
2. 画面上の該当画像に **緑色の枠線** を一瞬表示 (Favoritesの場合はピンク)
3. URLをキャッシュに登録し、同一ページ内での再ダウンロードを防止

---
*参照ファイル: `_App/ChromeExtension/content.js` (lines 44-76)*
