# README for AI Assistants

このファイルは、このリポジトリを作業する **AI アシスタント向け** のハンドブックです。新たな機能を開発したり、環境を構築したりする前に必ず一読してください。

## 1. プロジェクト構成 (Repository Map)

- `_App/`: アプリケーションのコアソースコード。
  - `ChromeExtension/`: Chrome 拡張機能のソース。
  - `Organizer/`: Python による画像整理ツールのソース。
- `_Data/`: ユーザーデータ、実行時の統計、設定ファイル。
- `_Dev/`: 開発者用リソース（ここを最優先で確認すること）。
  - `Tools/`: 既存のビルドスクリプト、バックアップツール、共通 `requirements.txt`。
  - `docs/`: 仕様書 (`specs/`) や開発メモ (`misc/`)。
- `_Data/System/`: アプリケーションの状態管理ファイル。

## 2. 既存ツールと再利用ルール (Existing Tools)

AI は、**新しいツールを開発する前に必ず `_Dev/Tools/` を再帰的に検索**しなければなりません。

| ツール名 | パス | 用途 |
| :--- | :--- | :--- |
| **build_organizer.bat** | `_Dev/Tools/build_organizer.bat` | `grok_organizer.py` を EXE 化する。新しい `.spec` は作らずこれを使うこと。 |
| **archive_grok_tools.py** | `_Dev/Tools/archive_grok_tools.py` | プロジェクトのバックアップ（ZIP化）を行う。 |
| **requirements.txt** | `_Dev/Tools/requirements.txt` | プロジェクトで必要な全依存パッケージの定義。 |
| **仮想環境 (.venv)** | `_Dev/Tools/.venv/` | 開発用 Python 仮想環境。 |

## 3. 開発ポリシー (Development Policies)

1.  **既存調査の徹底**: 実装を開始する前に `grep` や `ls -R` を駆使して既存ロジックを調査すること。
2.  **ドキュメントの更新**: 重要な変更を加えた後は `CHANGELOG.md` を更新し、`_Dev/docs/misc/` 以下に変更内容を反映したドキュメントを作成すること。
3.  **言語**: ユーザーへの回答およびドキュメントは、特段の指示がない限り **日本語** で作成すること。
4.  **破壊的変更の禁止**: 既存の `_Dev/Tools` 内のバッチファイルやスクリプトを、理由なくルートディレクトリへ移動させたり、重複して作成したりしないこと。

## 4. ビルド手順

EXE を更新する必要がある場合は、以下のコマンドを使用してください：
```powershell
cmd /c "_Dev\Tools\build_organizer.bat"
```
独自に `pyinstaller` コマンドを組み立てるのではなく、バッチファイル内の設定に従ってください。
