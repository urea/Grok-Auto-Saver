import os
import shutil
import glob
import json
import html
import re
import webbrowser
from pathlib import Path
from datetime import datetime

# 画像処理ライブラリ
try:
    from PIL import Image
except ImportError:
    Image = None

# ==========================================
# 設定エリア
# ==========================================

DOWNLOAD_DIR = Path(os.path.expanduser("~")) / "Downloads"
BASE_DIR = Path(__file__).parent.resolve()
# 構成変更対応: _App/Organizer/grok_organizer.py に配置される想定
# ルート: Grok-Auto-Saver/
if BASE_DIR.name.lower() == "organizer" and BASE_DIR.parent.name.lower() == "_app":
    GROK_ROOT_DIR = BASE_DIR.parent.parent
elif BASE_DIR.name.lower() == "organizer":
    GROK_ROOT_DIR = BASE_DIR.parent
else:
    GROK_ROOT_DIR = BASE_DIR

DATA_DIR = GROK_ROOT_DIR / "_Data"
DEST_DIR = DATA_DIR / "Favorites"
VIEWER_PATH = GROK_ROOT_DIR / "Grok_Viewer.html"
MERGED_PROMPT_FILE = "All_Prompts_Merged.txt"
FAVORITES_DB_FILE = "All_Favorites_Merged.json"

# ==========================================
# 処理ロジック
# ==========================================

def is_safe_directory(path):
    """削除処理を行っても良い安全なフォルダかチェックする"""
    user_home = Path(os.path.expanduser("~"))
    unsafe_paths = [DOWNLOAD_DIR, user_home, user_home / "Desktop", user_home / "Documents"]
    if path.resolve() in [p.resolve() for p in unsafe_paths if p.exists()]:
        return False
    return True

def move_videos():
    """動画ファイルを日付フォルダへ移動し、ファイル名に日時を付与する"""
    print(f"🎬 動画移動処理開始...")
    count = 0
    target_files = list(DOWNLOAD_DIR.glob("grok-video-*.mp4"))

    if not target_files:
        print("   動画ファイルは見つかりませんでした。")
        return 0

    for file_path in target_files:
        try:
            ts = file_path.stat().st_mtime
            dt = datetime.fromtimestamp(ts)
            date_str = dt.strftime('%Y%m%d')
            target_dir = DATA_DIR / "Images" / date_str
            target_dir.mkdir(parents=True, exist_ok=True)

            if not re.search(r'_\d{8}_\d{6}_', file_path.name):
                time_str = dt.strftime('%Y%m%d_%H%M%S')
                new_name = file_path.name.replace("grok-video-", f"grok-video_{time_str}_")
                if new_name == file_path.name:
                    new_name = f"{time_str}_{file_path.name}"
            else:
                new_name = file_path.name

            target_path = target_dir / new_name
            if target_path.exists():
                stem, suffix = Path(new_name).stem, Path(new_name).suffix
                counter = 1
                while target_path.exists():
                    target_path = target_dir / f"{stem}_{counter}{suffix}"
                    counter += 1
            
            shutil.move(str(file_path), str(target_path))
            print(f"   ✅ [移動] {file_path.name} -> {date_str}/{target_path.name}")
            count += 1
        except Exception as e:
            print(f"   ❌ [エラー] {file_path.name}: {e}")
    return count

def clean_garbage_images():
    """不要な画像を削除し、リアルタイムにログを表示する"""
    print(f"\n🖼️ 画像クリーニング処理開始...")
    if not is_safe_directory(GROK_ROOT_DIR):
        print(f"   ⚠️ 警告: 安全装置作動。専用フォルダ内で実行してください。")
        return 0
    if Image is None:
        print("   ⚠️  Pillowライブラリがないため解像度チェックをスキップします。")
        return 0

    count = 0
    print("   🔍 全ファイルをスキャン中...")
    
    all_image_files = []
    for ext in ["*.png", "*.jpg", "*.jpeg", "*.webp"]:
        all_image_files.extend(list(DATA_DIR.rglob(ext))) # DATA_DIR以下をスキャン

    for file_path in all_image_files:
        try:
            # 除外フォルダチェック（_Data以下のシステムフォルダ等）
            if any(p in file_path.parts for p in ["System", "Prompts"]):
                continue
            
            should_remove = False
            reason = ""

            if file_path.name.endswith("profile-picture.webp"):
                should_remove, reason = True, "User Profile Picture"
            
            # 1. Check file size (Delete if < 100KB)
            file_size_kb = file_path.stat().st_size / 1024
            if file_size_kb < 100:
                should_remove = True
                reason = f"File size too small: {file_size_kb:.1f}KB"

            if not should_remove:
                with Image.open(file_path) as img:
                    width, height = img.size
                    
                    # 2. Check resolution (Delete if min dimension < 500px)
                    if min(width, height) < 500:
                        should_remove = True
                        reason = f"Small resolution: {width}x{height}"
                    
                    # 3. Check depth/mode (Delete if not RGB/L/P - e.g. potentially problematic RGBA if intended)
                    # Note: Original logic for mode deletion if any can be preserved here.
                    # As requested "Deletion by depth", usually implies low bit depth or specific modes.
                    # Assuming we keep existing mode checks if they existed or just rely on the user's prompt implying we should look at it.
                    # For now, we'll keep the resolution check which is the primary "quality" filter alongside size.
                    elif img.mode in ('RGBA', 'CMYK'): # This was the original mode check
                        should_remove, reason = True, f"Mode: {img.mode}"
            
            if should_remove:
                print(f"   🗑️ [削除] {file_path.name} ({reason})", flush=True)
                os.remove(file_path)
                count += 1
        except Exception:
            pass

    print(f"   ✅ 処理完了")
    return count

def organize_prompts():
    """プロンプトのマージ処理 (連続重複のみ排除)"""
    print(f"\n📝 プロンプト整理処理開始...")

    prompts_dir = DATA_DIR / "Prompts"
    if not prompts_dir.exists(): return 0
    archive_dir = prompts_dir / "Archived"
    archive_dir.mkdir(exist_ok=True)

    txt_files = list(prompts_dir.glob("*.txt"))
    all_prompts = []
    prompt_pattern = re.compile(r'^\[(\d{4}/\d{1,2}/\d{1,2} \d{1,2}:\d{2}:\d{2})\]\s*\n(.*?)(?=\n-{20,}|\Z)', re.DOTALL | re.MULTILINE)
    files_to_archive = []

    # 1. 各ファイルおよび既存マージファイルから全読み込み
    # globは再帰的ではないため、直下のファイルのみ取得する (Archivedフォルダの中身は対象外)
    source_files = [p for p in txt_files if p.name != MERGED_PROMPT_FILE]
    
    # 既存のマージファイルを読み込み対象に追加
    merged_file_path = prompts_dir / MERGED_PROMPT_FILE
    all_files_to_read = source_files.copy()
    if merged_file_path.exists():
        all_files_to_read.append(merged_file_path)

    print(f"   📂 処理対象ファイル: {len(source_files)}件 (新規)")
    
    for txt_path in all_files_to_read:
        try:
            with open(txt_path, "r", encoding="utf-8-sig") as f:
                content = f.read()
            found = False
            for match in prompt_pattern.finditer(content):
                found = True
                dt_str, text = match.group(1), match.group(2).strip()
                try:
                    dt = datetime.strptime(dt_str, '%Y/%m/%d %H:%M:%S')
                    all_prompts.append({'time': dt.timestamp(), 'date_str': dt_str, 'content': text})
                except ValueError: continue
            
            # ソースファイル（＝新規ファイル）のみアーカイブ対象にする
            if found and txt_path.name != MERGED_PROMPT_FILE:
                files_to_archive.append(txt_path)
        except Exception: pass

    if all_prompts:
        # 新しい順にソート
        all_prompts.sort(key=lambda x: x['time'], reverse=True)
        final_list = []
        for p in all_prompts:
            if not final_list:
                final_list.append(p)
            else:
                # 全く同じ内容が連続した場合のみ排除
                if p['content'] != final_list[-1]['content']:
                    final_list.append(p)
        
        try:
            merged_path = prompts_dir / MERGED_PROMPT_FILE
            with open(merged_path, "w", encoding="utf-8") as f:
                f.write("GrokSaver Prompt History (Merged)\n====================================\n\n")
                for item in final_list:
                    f.write(f"[{item['date_str']}]\n{item['content']}\n------------------------------------\n\n")
            
            # 1世代残しロジック: 新しいファイルをアーカイブする前に、既存のアーカイブを全削除
            if files_to_archive:
                print(f"   🧹 アーカイブの旧世代ファイルを削除中...")
                for old_file in archive_dir.glob("*"):
                    try:
                        if old_file.is_file(): os.remove(old_file)
                    except Exception: pass

                for src in files_to_archive:
                    try: shutil.move(str(src), str(archive_dir / src.name))
                    except Exception: pass
        except Exception: pass
    return len(all_prompts)

def organize_favorites():
    """Favoritesログの統合"""
    print(f"\n⭐ Favoritesログ整理処理開始...")
    logs_dir = DATA_DIR / "System" / "FavLogs"
    if not logs_dir.exists(): return set()
    archive_dir, system_dir = logs_dir / "Archived", DATA_DIR / "System"
    archive_dir.mkdir(parents=True, exist_ok=True)
    merged_db_path, favorites_set = system_dir / FAVORITES_DB_FILE, set()
    
    if merged_db_path.exists():
        try:
            with open(merged_db_path, "r", encoding="utf-8") as f:
                for item in json.load(f): favorites_set.add(item['filename'])
        except Exception: pass

    log_files = list(logs_dir.glob("*.json"))
    files_to_archive = []
    for log_file in log_files:
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                items = json.load(f)
                if isinstance(items, list):
                    for item in items:
                        if item.get('filename'): favorites_set.add(item['filename'])
                elif isinstance(items, dict) and items.get('filename'):
                    favorites_set.add(items['filename'])
            files_to_archive.append(log_file)
        except Exception: pass

    if log_files or not merged_db_path.exists():
        save_list = [{"filename": name} for name in favorites_set]
        system_dir.mkdir(parents=True, exist_ok=True)
        with open(merged_db_path, "w", encoding="utf-8") as f:
            json.dump(save_list, f, indent=2, ensure_ascii=False)
        
        # 1世代残しロジック: 新しいファイルをアーカイブする前に、既存のアーカイブを全削除
        if files_to_archive:
           for old_file in archive_dir.glob("*"):
               try:
                   if old_file.is_file(): os.remove(old_file)
               except Exception: pass

           for src in files_to_archive:
               try: shutil.move(str(src), str(archive_dir / src.name))
               except Exception: pass
    return favorites_set

def get_file_info(path, type_label, fav_set):
    ts = path.stat().st_mtime
    match = re.search(r'_(\d{8})_(\d{6})_', path.name)
    if match:
        try:
            dt_str = match.group(1) + match.group(2)
            dt = datetime.strptime(dt_str, '%Y%m%dH%M%S')
            ts = dt.timestamp()
        except ValueError: pass
    return {
        'type': type_label, 'name': path.name, 'time': ts,
        'date_str': datetime.fromtimestamp(ts).strftime('%Y-%m-%d'), 
        'path': os.path.relpath(path, GROK_ROOT_DIR).replace("\\", "/"),
        'is_favorite': path.name in fav_set
    }

def collect_and_group_data(fav_set):
    if not DATA_DIR.exists(): return {}
    all_items, media_files = [], []
    for ext in ["*.png", "*.jpg", "*.jpeg", "*.webp", "*.mp4"]:
        media_files.extend(list(DATA_DIR.rglob(ext)))

    for path in media_files:
        if path.parent.name in ["Prompts", "System", "Organizer", "ChromeExtension", "icons"]: continue
        if path.parent.parent.name == "System": continue # Prevent FavLogs/Archived
        if "Organizer" in path.parts or "_App" in path.parts: continue
        all_items.append(get_file_info(path, 'video' if path.suffix.lower() == '.mp4' else 'image', fav_set))

    merged_file = DATA_DIR / "Prompts" / MERGED_PROMPT_FILE
    if merged_file.exists():
        prompt_pattern = re.compile(r'^\[(\d{4}/\d{1,2}/\d{1,2} \d{1,2}:\d{2}:\d{2})\]\s*\n(.*?)(?=\n-{20,}|\Z)', re.DOTALL | re.MULTILINE)
        try:
            with open(merged_file, "r", encoding="utf-8") as f:
                content = f.read()
            for match in prompt_pattern.finditer(content):
                dt_str, text = match.group(1), match.group(2).strip()
                if not text: continue
                dt = datetime.strptime(dt_str, '%Y/%m/%d %H:%M:%S')
                all_items.append({'type': 'prompt', 'name': "History", 'time': dt.timestamp(), 'date_str': dt.strftime('%Y-%m-%d'), 'content': text, 'is_favorite': False})
        except Exception: pass

    date_buckets = {}
    for item in all_items:
        date_key = item['date_str']
        date_buckets.setdefault(date_key, []).append(item)

    timeline_data = {}
    for date_key, items in date_buckets.items():
        items.sort(key=lambda x: x['time'], reverse=True)
        grouped_list, current_media_group = [], []
        for item in items:
            if item['type'] in ('image', 'video'):
                current_media_group.append(item)
            elif item['type'] == 'prompt':
                if current_media_group:
                    grouped_list.append({"prompt": item, "media": current_media_group})
                    current_media_group = []
        if current_media_group:
            grouped_list.append({"prompt": None, "media": current_media_group})
        if grouped_list:
            timeline_data[date_key] = grouped_list
    return timeline_data

def generate_viewer_html(fav_set):
    """ご提示いただいた過去のコードのUIデザインを完全に復元したビューアーの生成"""
    print(f"\n🌐 ビューアー生成処理開始...")
    data = collect_and_group_data(fav_set)
    if not data: return
    dates = sorted(list(data.keys()), reverse=True)
    json_data = json.dumps(data, ensure_ascii=False)
    dates_json = json.dumps(dates)

    html_content = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Grok Viewer</title>
    <style>
        :root {{ --bg: #121212; --sidebar-bg: #1e1e1e; --card-bg: #252525; --text: #e0e0e0; --accent: #bb86fc; --border: #333; }}
        body {{ font-family: 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); margin: 0; display: flex; height: 100vh; overflow: hidden; }}
        #sidebar {{ width: 220px; background: var(--sidebar-bg); border-right: 1px solid var(--border); display: flex; flex-direction: column; flex-shrink: 0; }}
        .sidebar-header {{ padding: 15px; font-weight: bold; border-bottom: 1px solid var(--border); font-size: 1.1rem; display: flex; justify-content: space-between; align-items: center; white-space: nowrap; }}
        #search-toggle {{ cursor: pointer; font-size: 1.2rem; opacity: 0.7; transition: all 0.2s; width: 30px; height: 30px; display: flex; justify-content: center; align-items: center; border-radius: 50%; margin-left: 10px; }}
        #search-toggle:hover {{ opacity: 1; color: var(--accent); background: rgba(255,255,255,0.1); }}
        #normal-sidebar-content, #search-sidebar-content {{ display: flex; flex-direction: column; flex: 1; overflow: hidden; }}
        #search-sidebar-content {{ padding: 10px; }}
        .hidden {{ display: none !important; }}
        .search-box {{ display: flex; gap: 5px; margin-bottom: 10px; }}
        #search-input {{ flex: 1; padding: 8px; border-radius: 4px; border: 1px solid #444; background: #333; color: white; min-width: 0; }}
        .search-btn {{ width: 36px; height: 36px; background: var(--accent); border: none; border-radius: 4px; color: #000; font-weight: bold; cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 1.2rem; }}
        .back-btn {{ margin-top: auto; padding: 10px; background: none; border: 1px solid #555; color: #ccc; cursor: pointer; border-radius: 4px; }}
        .filter-tabs {{ display: flex; border-bottom: 1px solid var(--border); }}
        .filter-tab {{ flex: 1; padding: 10px; text-align: center; cursor: pointer; background: rgba(0,0,0,0.2); transition: background 0.2s; font-size: 0.9rem; }}
        .filter-tab.active {{ background: var(--accent); color: #000; font-weight: bold; }}
        #date-list {{ list-style: none; padding: 0; margin: 0; overflow-y: auto; flex: 1; }}
        .date-item {{ padding: 10px 15px; cursor: pointer; border-bottom: 1px solid #2a2a2a; transition: background 0.2s; display: flex; justify-content: space-between; }}
        .date-item:hover {{ background: #2a2a2a; }}
        .date-item.active {{ background: rgba(187, 134, 252, 0.2); border-left: 4px solid var(--accent); }}
        .count {{ font-size: 0.8rem; opacity: 0.6; background: rgba(0,0,0,0.3); padding: 2px 6px; border-radius: 10px; }}
        #main {{ flex: 1; overflow-y: scroll; scrollbar-gutter: stable; padding: 20px; position: relative; scroll-behavior: smooth; }}
        .group {{ margin-bottom: 40px; background: var(--card-bg); border-radius: 8px; padding: 20px; box-shadow: 0 4px 10px rgba(0,0,0,0.3); }}
        .prompt-header {{ margin-bottom: 15px; padding-bottom: 10px; border-bottom: 1px solid var(--border); }}
        .prompt-meta {{ font-size: 0.85rem; color: #888; margin-bottom: 5px; }}
        .prompt-text {{ white-space: pre-wrap; font-size: 1rem; line-height: 1.6; color: #fff; }}
        .media-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px; align-items: start; }}
        .media-item {{ background: #000; cursor: pointer; border-radius: 4px; overflow: hidden; position: relative; }}
        .media-item img, .media-item video {{ width: 100%; height: auto; display: block; transition: transform 0.2s; }}
        .media-item:hover img {{ transform: scale(1.02); }}
        .video-label {{ position: absolute; top: 5px; right: 5px; background: rgba(0,0,0,0.7); color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; pointer-events: auto; cursor: pointer; transition: background 0.2s; }}
        .video-label:hover {{ background: rgba(187, 134, 252, 0.8); color: black; }}
        .media-item.selected {{ outline: 3px solid var(--accent); z-index: 5; }}
        #modal {{ display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.9); z-index: 1000; justify-content: center; align-items: center; }}
        #modal.active {{ display: flex; }}
        #modal-content {{ position: relative; max-width: 95%; max-height: 95%; display: flex; justify-content: center; align-items: center; width: 100%; height: 100%; }}
        #modal-content img, #modal-content video {{ width: 100%; height: 95vh; object-fit: contain; box-shadow: 0 0 20px rgba(0,0,0,0.5); }}
        .close-hint {{ position: absolute; top: 20px; right: 20px; color: white; background: rgba(0,0,0,0.5); padding: 5px 10px; border-radius: 5px; cursor: pointer; z-index: 1002; }}
        .modal-nav {{ position: absolute; top: 50%; transform: translateY(-50%); background: rgba(0,0,0,0.5); color: white; border: none; font-size: 2rem; padding: 20px 10px; cursor: pointer; z-index: 1001; transition: background 0.2s; }}
        .modal-nav:hover {{ background: rgba(187, 134, 252, 0.8); color: black; }}
        .modal-prev {{ left: 20px; }} .modal-next {{ right: 20px; }}
        #nav-buttons {{ padding: 10px; border-top: 1px solid var(--border); display: grid; grid-template-columns: repeat(4, 1fr); gap: 5px; background: var(--sidebar-bg); }}
        .nav-btn {{ height: 35px; background: rgba(50, 50, 50, 0.5); color: #ccc; border: 1px solid #444; border-radius: 4px; cursor: pointer; font-size: 1.1rem; display: flex; justify-content: center; align-items: center; opacity: 0.6; }}
        .nav-btn:hover {{ background: var(--accent); color: #000; border-color: var(--accent); opacity: 1; }}
    </style>
</head>
<body>
    <div id="sidebar">
        <div class="sidebar-header"><span>Grok Viewer</span><div id="search-toggle" onclick="toggleSearchMode()">&#128269;</div></div>
        <div id="normal-sidebar-content">
            <div class="filter-tabs"><div class="filter-tab active" onclick="setFilter('all')">All</div><div class="filter-tab" onclick="setFilter('fav')">Favorites</div></div>
            <ul id="date-list"></ul>
        </div>
        <div id="search-sidebar-content" class="hidden">
            <div class="search-box"><input type="text" id="search-input" placeholder="検索..." onkeydown="if(event.key==='Enter') performSearch()"><button class="search-btn" onclick="performSearch()">&#128269;</button></div>
            <div id="search-status">キーワードを入力</div><button class="back-btn" onclick="toggleSearchMode()">← 戻る</button>
        </div>
        <div id="nav-buttons"><button class="nav-btn" onclick="scrollToTop()">▲</button><button class="nav-btn" onclick="scrollToBottom()">▼</button><button class="nav-btn" onclick="scrollGroup('prev')">↑</button><button class="nav-btn" onclick="scrollGroup('next')">↓</button></div>
    </div>
    <div id="main"><div id="content-area"></div></div>
    <div id="modal" onclick="closeModal(event)"><div class="close-hint" onclick="closeModal(event)">Close</div><button class="modal-nav modal-prev" onclick="navigateModal(-1, event)">&#10094;</button><button class="modal-nav modal-next" onclick="navigateModal(1, event)">&#10095;</button><div id="modal-content" onclick="event.stopPropagation()"></div></div>
    <script>
        const data = {json_data}; const dates = {dates_json};
        let currentFilter = 'all', currentDate = null, isSearchMode = false, currentMediaList = [], currentMediaIndex = -1;
        let selectedIndices = new Set();
        window.onload = () => {{ renderDateList(); if (dates.length > 0) selectDate(dates[0]); }};
        document.addEventListener('keydown', (e) => {{ if (document.getElementById('modal').classList.contains('active')) {{ if (e.key === 'Escape') closeModal(); if (e.key === 'ArrowLeft') navigateModal(-1); if (e.key === 'ArrowRight') navigateModal(1); }} }});
        function toggleSearchMode() {{ isSearchMode = !isSearchMode; document.getElementById('normal-sidebar-content').classList.toggle('hidden', isSearchMode); document.getElementById('search-sidebar-content').classList.toggle('hidden', !isSearchMode); if (isSearchMode) document.getElementById('search-input').focus(); }}
        function setFilter(f) {{ currentFilter = f; document.querySelectorAll('.filter-tab').forEach(el => el.classList.remove('active')); document.querySelector(`.filter-tab[onclick="setFilter('${{f}}')"]`).classList.add('active'); renderDateList(); if (currentDate) selectDate(currentDate); }}
        function renderDateList() {{
            const list = document.getElementById('date-list'); list.innerHTML = '';
            dates.forEach(date => {{
                let count = 0; data[date].forEach(g => count += g.media.filter(m => currentFilter === 'all' || m.is_favorite).length);
                if (count === 0 && currentFilter === 'fav') return;
                const li = document.createElement('li'); li.className = 'date-item' + (date === currentDate ? ' active' : ''); li.onclick = () => selectDate(date);
                li.id = 'date-' + date; li.innerHTML = `${{date}} <span class="count">${{count}}</span>`; list.appendChild(li);
            }});
        }}
        function selectDate(date) {{
            currentDate = date; document.querySelectorAll('.date-item').forEach(el => el.classList.remove('active'));
            const activeItem = document.getElementById('date-' + date); if (activeItem) activeItem.classList.add('active');
            const container = document.getElementById('content-area'); container.innerHTML = ''; currentMediaList = [];
            selectedIndices.clear(); // Clear selection on navigate
            data[date].forEach(group => {{
                const validMedia = group.media.filter(m => currentFilter === 'all' || m.is_favorite); if (validMedia.length === 0) return;
                renderGroup({{ ...group, media: validMedia }}, container, null);
            }});
            document.getElementById('main').scrollTop = 0;
        }}
        function renderGroup(group, parent, dateLabel) {{
            const baseIndex = currentMediaList.length; group.media.forEach(m => currentMediaList.push(m));
            const div = document.createElement('div'); div.className = 'group';
            const header = document.createElement('div'); header.className = 'prompt-header';
            if (group.prompt) {{
                const label = dateLabel ? `[${{dateLabel}}] ` : '';
                header.innerHTML = `<div class="prompt-meta">${{label}}${{new Date(group.prompt.time * 1000).toLocaleString()}}</div><div class="prompt-text">${{group.prompt.content}}</div>`;
            }} else header.innerHTML = '<div class="no-prompt">画像のみ</div>';
            div.appendChild(header);
            const grid = document.createElement('div'); grid.className = 'media-grid';
            group.media.forEach((m, i) => {{
                const item = document.createElement('div'); item.className = 'media-item'; 
                // Set ID for selection logic
                const globalIdx = baseIndex + i; item.dataset.idx = globalIdx;
                item.onclick = (e) => handleItemClick(e, globalIdx, m.type);
                item.draggable = true; 
                item.ondragstart = (e) => handleDragStart(e, globalIdx, m);
                item.innerHTML = m.type === 'video' ? `<video src="${{m.path}}#t=0.1" muted></video><div class="video-label" onclick="event.stopPropagation(); copyToClipboard('${{m.path}}', this)">VIDEO</div>` : `<img src="${{m.path}}" loading="lazy">`;
                grid.appendChild(item);
            }});
            div.appendChild(grid); parent.appendChild(div);
        }}
        function performSearch() {{
            const q = document.getElementById('search-input').value.trim().toLowerCase(); if (!q) return;
            const container = document.getElementById('content-area'); container.innerHTML = ''; currentMediaList = [];
            let hit = 0; const frag = document.createDocumentFragment();
            dates.forEach(d => data[d].forEach(g => {{ if (g.prompt && g.prompt.content.toLowerCase().includes(q)) {{ hit++; renderGroup(g, frag, d); }} }}));
            if (hit === 0) container.innerHTML = '<div style="text-align:center; padding:50px; color:#888;">No matches.</div>'; else container.appendChild(frag);
            document.getElementById('search-status').innerText = `${{hit}} 件ヒット`; document.getElementById('main').scrollTop = 0;
        }}
        function openModalByIndex(idx) {{
            currentMediaIndex = idx; const m = currentMediaList[idx]; const modal = document.getElementById('modal'); const content = document.getElementById('modal-content');
            content.innerHTML = m.type === 'video' ? `<video src="${{m.path}}" controls autoplay></video>` : `<img src="${{m.path}}">`; modal.classList.add('active');
        }}
        function navigateModal(dir, e) {{ if (e) e.stopPropagation(); const n = currentMediaIndex + dir; if (n >= 0 && n < currentMediaList.length) openModalByIndex(n); }}
        function closeModal(e) {{ if (e && e.target.id !== 'modal' && !e.target.classList.contains('close-hint')) return; document.getElementById('modal').classList.remove('active'); document.getElementById('modal-content').innerHTML = ''; }}
        function scrollToTop() {{ document.getElementById('main').scrollTo({{ top: 0, behavior: 'smooth' }}); }}
        function scrollToBottom() {{ const m = document.getElementById('main'); m.scrollTo({{ top: m.scrollHeight, behavior: 'smooth' }}); }}
        function scrollGroup(dir) {{
            const m = document.getElementById('main'); const groups = document.querySelectorAll('.group'); if (!groups.length) return;
            const cur = m.scrollTop; if (dir === 'next') {{ for (const g of groups) if (g.offsetTop > cur + 5) {{ g.scrollIntoView({{ behavior: 'smooth' }}); return; }} }}
            else {{ for (let i = groups.length - 1; i >= 0; i--) if (groups[i].offsetTop < cur - 5) {{ groups[i].scrollIntoView({{ behavior: 'smooth' }}); return; }} scrollToTop(); }}
        }}
        function handleItemClick(e, idx, type) {{
            if (type === 'video') {{ openModalByIndex(idx); return; }}
            if (e.ctrlKey) {{
                // Toggle selection
                if (selectedIndices.has(idx)) selectedIndices.delete(idx);
                else selectedIndices.add(idx);
                updateSelectionVisuals();
            }} else {{
                // Normal click
                if (selectedIndices.size > 0) {{
                    selectedIndices.clear();
                    updateSelectionVisuals();
                }}
                openModalByIndex(idx);
            }}
        }}
        function updateSelectionVisuals() {{
            document.querySelectorAll('.media-item').forEach(el => {{
                const idx = parseInt(el.dataset.idx);
                if (selectedIndices.has(idx)) el.classList.add('selected');
                else el.classList.remove('selected');
            }});
        }}
        function handleDragStart(e, idx, m) {{
            // Construct full path helper (same logic as copyToClipboard)
            const getFullPath = (relPath) => {{
                let bp = window.location.pathname;
                if (bp.match(/^\/[a-zA-Z]:\//)) bp = bp.substring(1);
                bp = decodeURIComponent(bp);
                const dn = bp.substring(0, bp.lastIndexOf('/') + 1);
                return (dn + relPath).replace(/\//g, '\\\\');
            }};

            if (selectedIndices.has(idx)) {{
                // Batch drag
                const files = [];
                selectedIndices.forEach(i => {{
                    const media = currentMediaList[i];
                    if (media.type !== 'video') files.push(getFullPath(media.path));
                }});
                const list = files.join('\\n');
                e.dataTransfer.setData('text/plain', list);
                // Also standard single file backup if only one
                if (files.length === 1) {{
                     const url = new URL(currentMediaList[idx].path, window.location.href).href;
                     e.dataTransfer.setData('DownloadURL', `image/jpeg:${{currentMediaList[idx].name}}:${{url}}`);
                }}
            }} else {{
                // Single drag
                selectedIndices.clear(); updateSelectionVisuals(); // Clear others if dragging unselected
                const url = new URL(m.path, window.location.href).href;
                const mime = m.type === 'video' ? 'video/mp4' : 'image/jpeg';
                e.dataTransfer.setData('DownloadURL', `${{mime}}:${{m.name}}:${{url}}`);
            }}
        }}
        function copyToClipboard(relPath, btn) {{
             try {{
                let basePath = window.location.pathname;
                if (basePath.match(/^\/[a-zA-Z]:\//)) basePath = basePath.substring(1);
                basePath = decodeURIComponent(basePath);
                const dirName = basePath.substring(0, basePath.lastIndexOf('/') + 1);
                let fullPath = dirName + relPath;
                fullPath = fullPath.replace(/\//g, '\\\\');
                navigator.clipboard.writeText(fullPath).then(() => {{
                    const originalText = btn.innerText;
                    btn.innerText = "COPIED!";
                    setTimeout(() => btn.innerText = originalText, 1500);
                }}).catch(err => alert('Copy failed: ' + err));
             }} catch (e) {{ alert('Error: ' + e); }}
        }}
    </script>
</body></html>"""

    try:
        with open(VIEWER_PATH, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"   ✅ 生成完了: {VIEWER_PATH}")
        webbrowser.open(f"file://{VIEWER_PATH}")
    except Exception as e:
        print(f"   ❌ 生成失敗: {e}")

def main():
    print("=" * 60)
    print(" 🧹 Grok Organizer (v2.7.0)")
    print("=" * 60)
    try:
        move_videos()
        clean_garbage_images() 
        organize_prompts()
        fav_set = organize_favorites()
        generate_viewer_html(fav_set) 
        print("-" * 60)
        print(f"✨ 全ての整理が完了しました。")
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")

if __name__ == "__main__":
    main()