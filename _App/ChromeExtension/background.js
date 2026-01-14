// background.js - GrokSaver v2.6
// 変更点: Favoritesログ生成、高画質リカバリー、動的ファイル名リネーム対応
// 履歴の正確性と、ページ更新等による二重保存の防止を両立しました。

const STORAGE_KEY = "grok_saver_history";
const FILENAME_KEY = "grok_saver_filenames";
const PROMPT_TEXT_KEY = "grok_saver_prompt_texts";
const MIN_FILE_SIZE_KB = 20;
const ROOT_FOLDER = "Grok-Auto-Saver";

const monitoredDownloadIds = new Map();
const processingCache = new Set(); // In-flight check to prevent race conditions

// ------------------------------------
// 共通ヘルパー関数
// ------------------------------------
async function generateHash(message) {
    const msgUint8 = new TextEncoder().encode(message);
    const hashBuffer = await crypto.subtle.digest('SHA-256', msgUint8);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}

function getDateString() {
    const now = new Date();
    const y = now.getFullYear();
    const m = String(now.getMonth() + 1).padStart(2, '0');
    const d = String(now.getDate()).padStart(2, '0');
    return `${y}${m}${d}`;
}

function createFallbackFilename(ext = ".jpg") {
    const now = new Date();
    const timeStr = now.toTimeString().split(' ')[0].replace(/:/g, '');
    const randomStr = Math.floor(Math.random() * 10000).toString().padStart(4, '0');
    return `grok_image_${getDateString()}_${timeStr}_${randomStr}${ext}`;
}

function getSafeFilenameFromUrl(url) {
    try {
        const urlObj = new URL(url);
        let rawFilename = urlObj.pathname.substring(urlObj.pathname.lastIndexOf('/') + 1);
        let filename = decodeURIComponent(rawFilename);
        filename = filename.replace(/[^a-zA-Z0-9._-]/g, '_').replace(/_+/g, '_').trim().replace(/[. ]+$/, '');
        if (filename.length > 100) filename = filename.substring(0, 100);
        if (!filename || filename === "." || filename === ".." || filename === "_") return null;
        if (!filename.includes('.')) filename += ".jpg";
        return filename;
    } catch (e) { }
    return null;
}

function tryGetHighResUrl(url) {
    try {
        // パターン: https://imagine-public.x.ai/cdn-cgi/image/width=500,.../imagine-public/images/UUID.jpg
        // 目標: https://imagine-public.x.ai/imagine-public/images/UUID.jpg
        if (url.includes("imagine-public.x.ai") && url.includes("/cdn-cgi/image/")) {
            const parts = url.split("/imagine-public/images/");
            if (parts.length > 1) {
                return "https://imagine-public.x.ai/imagine-public/images/" + parts[1];
            }
        }
    } catch (e) { }
    return url;
}

// ------------------------------------
// 履歴管理
// ------------------------------------
async function isDuplicateHash(id) {
    return new Promise((resolve) => {
        chrome.storage.local.get([STORAGE_KEY], (result) => {
            const history = result[STORAGE_KEY] || [];
            resolve(history.includes(id));
        });
    });
}

async function isDuplicateFilename(filename) {
    return new Promise((resolve) => {
        chrome.storage.local.get([FILENAME_KEY], (result) => {
            const history = result[FILENAME_KEY] || [];
            resolve(history.includes(filename));
        });
    });
}

function addToHistory(hashId, filename) {
    chrome.storage.local.get([STORAGE_KEY, FILENAME_KEY], (result) => {
        const hashHistory = result[STORAGE_KEY] || [];
        if (hashId && !hashHistory.includes(hashId)) {
            if (hashHistory.length > 5000) hashHistory.shift();
            hashHistory.push(hashId);
        }
        const nameHistory = result[FILENAME_KEY] || [];
        if (filename && !nameHistory.includes(filename)) {
            if (nameHistory.length > 5000) nameHistory.shift();
            nameHistory.push(filename);
        }
        chrome.storage.local.set({ [STORAGE_KEY]: hashHistory, [FILENAME_KEY]: nameHistory });
    });
}

function savePromptText(text) {
    chrome.storage.local.get([PROMPT_TEXT_KEY], (result) => {
        const texts = result[PROMPT_TEXT_KEY] || [];
        texts.unshift({ date: new Date().toLocaleString('ja-JP'), text: text });
        if (texts.length > 200) texts.pop(); // 履歴保持数を少し拡張
        chrome.storage.local.set({ [PROMPT_TEXT_KEY]: texts });
    });
}

// ------------------------------------
// メッセージ受信
// ------------------------------------
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "download_image" && request.src) {
        handleImageRequest(request.src, request.isFavorites);
    }
    else if (request.action === "save_prompt" && request.text) {
        handlePromptRequest(request.text);
    }
});

function saveFavoritesLog(filename, uniqueId) {
    const simpleName = filename.split(/[/\\]/).pop();
    const data = [{
        filename: simpleName,
        uuid: uniqueId,
        timestamp: Date.now()
    }];
    const jsonStr = JSON.stringify(data, null, 2);
    const dataUrl = "data:application/json;charset=utf-8," + encodeURIComponent(jsonStr);
    const logFilename = `${ROOT_FOLDER}/_Data/System/FavLogs/fav_${Date.now()}_${Math.floor(Math.random() * 1000)}.json`;

    downloadQueue.push({
        url: dataUrl,
        filename: logFilename,
        uniqueId: null,
        isLog: true
    });
    processDownloadQueue();
}

// ------------------------------------
// キュー処理システム
// ------------------------------------
let isProcessingQueue = false;
const downloadQueue = [];

function processDownloadQueue() {
    if (isProcessingQueue || downloadQueue.length === 0) return;
    isProcessingQueue = true;
    const item = downloadQueue.shift();

    chrome.downloads.download({
        url: item.url,
        filename: item.filename,
        conflictAction: "uniquify",
        saveAs: false
    }, (downloadId) => {
        if (chrome.runtime.lastError) {
            if (!item.isRetry && !item.isLog) {
                const ext = item.filename.includes('.txt') ? '.txt' : '.jpg';
                const simpleName = `grok_fallback_${Date.now()}${ext}`;
                downloadQueue.unshift({ ...item, filename: simpleName, isRetry: true });
            }
        } else {
            monitoredDownloadIds.set(downloadId, { ...item });
            if (!item.isLog) {
                const simpleFilename = item.filename.split('/').pop();
                addToHistory(item.uniqueId, simpleFilename);
                // Keep in processingCache to prevent re-download in same session if needed, 
                // or let it rely on history from now on. 
                // For safety against race conditions during "complete" event handling, we keep it for a bit or rely on history.
                // Since addToHistory is async, there is a tiny gap, but processingCache covers it.
            }
        }
        setTimeout(() => {
            isProcessingQueue = false;
            processDownloadQueue();
        }, 300);
    });
}

// ------------------------------------
// リクエストハンドラ
// ------------------------------------
async function handleImageRequest(src, isFavorites) {
    let uniqueId = src;
    if (src.startsWith("data:")) uniqueId = await generateHash(src);

    let filenameOnly = null;

    // 拡張子の推定 (URLから取得できれば使用)
    let ext = ".jpg";
    try {
        const urlPath = new URL(src).pathname;
        if (urlPath.includes(".")) {
            const possibleExt = "." + urlPath.split(".").pop();
            if (possibleExt.length <= 5) ext = possibleExt;
        }
    } catch (e) { }

    if (src.startsWith("data:")) {
        filenameOnly = createFallbackFilename();
    } else {
        const candidate = getSafeFilenameFromUrl(src);

        // 汎用的な名前やUUIDの場合は、日時ベースの名前に置き換える
        // Favoritesの場合は、順序保持のため常に日時ベースを使用する
        const isGeneric = candidate && (
            candidate.includes("preview_image") ||
            /^[0-9a-fA-F-]{30,}/.test(candidate)
        );

        if (isFavorites || !candidate || isGeneric) {
            filenameOnly = createFallbackFilename(ext);
        } else {
            filenameOnly = candidate;
        }
    }

    let finalUrl = src;
    if (isFavorites) {
        finalUrl = tryGetHighResUrl(src);
    }


    // Favoritesの場合、High-Res URLのハッシュで重複チェックを行う
    if (isFavorites) {
        // Strict UUID Extraction: URLからUUID部分のみを抽出してIDとする
        // パターン: 任意の場所にある36文字のUUIDを探す
        const uuidRegex = /([0-9a-fA-F-]{36})/;
        const uuidMatch = finalUrl.match(uuidRegex);

        if (uuidMatch) {
            uniqueId = uuidMatch[1]; // Use raw UUID found in URL
        } else {
            // Fallback: UUIDが見つからない場合は、クエリパラメータを除去したURLでハッシュ化
            // これにより、時間経過で変わるトークン等の影響を排除する
            try {
                const urlObj = new URL(finalUrl);
                // origin + pathname のみをID生成に使用
                const stableUrl = urlObj.origin + urlObj.pathname;
                uniqueId = await generateHash(stableUrl);
            } catch (e) {
                uniqueId = await generateHash(finalUrl);
            }
        }
    }

    let shouldSave = false;
    // Smart Duplicate Check: Favoritesでも履歴重複チェックを有効化
    // In-Memory Cache (processingCache) と Storage History の両方をチェック
    if (processingCache.has(uniqueId)) {
        console.log(`[GrokSaver] Skipped duplicate (Processing): ${filenameOnly}`);
        return;
    }

    const exists = await isDuplicateHash(uniqueId);
    if (!exists) {
        shouldSave = true;
        processingCache.add(uniqueId); // Mark as processing immediately
    } else {
        console.log(`[GrokSaver] Skipped duplicate (History): ${filenameOnly}`);
    }

    if (shouldSave) {
        // User Request: Use UUID as filename if available (especially for Favorites)
        // Organizer will rely on file creation timestamp for sorting if date-string is missing.
        if (isFavorites && /^[0-9a-fA-F-]{36}$/.test(uniqueId)) {
            filenameOnly = uniqueId + ext;
        }

        // 高画質画像として保存するため、Favoritesの場合も日付フォルダに保存する
        let targetFolder = `${ROOT_FOLDER}/_Data/Images/${getDateString()}`;
        downloadQueue.push({ url: finalUrl, filename: `${targetFolder}/${filenameOnly}`, uniqueId: uniqueId, isLog: false, isFavorites: isFavorites });
    }
    processDownloadQueue();
}

async function handlePromptRequest(text) {
    // 連続重複チェック: 最新の保存済みテキストと比較
    const isContinuousDuplicate = await new Promise((resolve) => {
        chrome.storage.local.get([PROMPT_TEXT_KEY], (result) => {
            const texts = result[PROMPT_TEXT_KEY] || [];
            // texts[0] が最新の履歴
            if (texts.length > 0) {
                const lastItem = texts[0];
                const now = new Date();
                const currentDate = now.toLocaleDateString('ja-JP');
                const lastDate = lastItem.date ? lastItem.date.split(' ')[0] : ""; // date format is "YYYY/MM/DD HH:mm:ss"

                // 内容が同一で、かつ日付が変わっていない場合のみ重複とみなす
                if (lastItem.text === text && currentDate === lastDate) {
                    resolve(true);
                } else {
                    resolve(false);
                }
            } else {
                resolve(false);
            }
        });
    });

    if (isContinuousDuplicate) {
        console.log("[GrokSaver] 直前のプロンプトと同一内容のため、重複保存をスキップしました。");
        return;
    }

    savePromptText(text);

    const now = new Date();
    const dateStr = now.getFullYear() + "/" + (now.getMonth() + 1).toString().padStart(2, '0') + "/" + now.getDate().toString().padStart(2, '0') + " " + now.getHours().toString().padStart(2, '0') + ":" + now.getMinutes().toString().padStart(2, '0') + ":" + now.getSeconds().toString().padStart(2, '0');
    const fileContent = `[${dateStr}]\n${text}\n------------------------------------\n`;
    const dataUrl = "data:text/plain;charset=utf-8," + encodeURIComponent("\uFEFF" + fileContent);
    const timeStr = now.toTimeString().split(' ')[0].replace(/:/g, '');
    const randomStr = Math.floor(Math.random() * 10000).toString().padStart(4, '0');
    const filename = `${ROOT_FOLDER}/_Data/Prompts/prompt_${getDateString()}_${timeStr}_${randomStr}.txt`;

    downloadQueue.push({ url: dataUrl, filename: filename, uniqueId: null, isLog: false, isPrompt: true });
    processDownloadQueue();
}

chrome.downloads.onChanged.addListener((delta) => {
    if (!monitoredDownloadIds.has(delta.id)) return;
    if (delta.state && delta.state.current === "complete") {
        chrome.downloads.search({ id: delta.id }, (results) => {
            if (results && results.length > 0) {
                const item = results[0];
                const fileSizeKB = item.fileSize / 1024;
                const isSafeFile = item.filename.endsWith(".mp4") || item.filename.endsWith(".txt") || item.filename.endsWith(".json");

                // メタデータの取得
                const meta = monitoredDownloadIds.get(delta.id);

                if (!isSafeFile && fileSizeKB < MIN_FILE_SIZE_KB) {
                    chrome.downloads.removeFile(delta.id, () => {
                        chrome.downloads.erase({ id: delta.id });
                        monitoredDownloadIds.delete(delta.id);
                    });
                } else {
                    // Favoritesの場合はログを保存
                    if (meta && meta.isFavorites) {
                        saveFavoritesLog(item.filename, meta.uniqueId);
                    }
                    chrome.downloads.erase({ id: delta.id });
                    monitoredDownloadIds.delete(delta.id);
                }
            }
        });
    }
});