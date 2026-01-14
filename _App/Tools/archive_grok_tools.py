import os
import shutil
from datetime import datetime

def create_grok_backup():
    # 1. 設定：ソースディレクトリと対象フォルダ
    base_source_dir = r"C:\Users\urear\Downloads\Grok-Auto-Saver"
    target_folders = ["ChromeExtension", "Organizer"]
    
    # 2. 実行パス（スクリプトの場所）を取得
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 3. 保存ファイル名の決定 (YYYYMMDDhhmmss形式)
    # hhmmssを追加し、1秒単位でユニークなファイル名を作成します
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d%H%M%S")
    zip_filename_base = f"Grok-Auto-Saver{timestamp}"
    zip_full_path = os.path.join(current_dir, zip_filename_base)

    # 一時的な作業ディレクトリの作成
    temp_dir = os.path.join(current_dir, f"temp_{timestamp}")
    
    try:
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)

        # フォルダのコピー（存在確認とエラー指摘）
        for folder in target_folders:
            source_path = os.path.join(base_source_dir, folder)
            if os.path.exists(source_path):
                shutil.copytree(source_path, os.path.join(temp_dir, folder))
            else:
                # 指摘：指定されたフォルダが見つからない場合は処理を中断します
                print(f"【指摘】エラー: ソースフォルダが存在しません: {source_path}")
                return

        # 4. ZIP圧縮の実行
        # 生成される物理ファイル名は「Grok-Auto-SaverYYYYMMDDhhmmss.zip」となります
        shutil.make_archive(zip_full_path, 'zip', temp_dir)
        
        print(f"成功: {zip_filename_base}.zip を作成しました。")
        print(f"保存場所: {current_dir}")

    except Exception as e:
        print(f"エラーが発生しました: {e}")
        
    finally:
        # 一時フォルダのクリーンアップ
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

if __name__ == "__main__":
    create_grok_backup()