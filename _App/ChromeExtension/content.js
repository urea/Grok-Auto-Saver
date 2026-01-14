// content.js - GrokSaver v2.6
// 機能: 画像保存、プロンプト監視、動画自動クリック、Favorites判定
// 変更点: プロンプトの重複判定を「文字列」から「要素」に変更し、同一プロンプトの再利用に対応

const CONFIG = {
    minSizeKB: 20,
    targetAlt: "Generated image",
    videoUrlPattern: "/post/",
    downloadButtonSelector: 'button[aria-label="ダウンロード"]',
    promptSelector: "div.bg-surface-l1.px-4.py-2.z-10.w-fit.truncate.rounded-full.sticky"
};

const processedCache = new Set();
let processedPosts = new Set();

let lastUrl = window.location.href;

function log(msg) {
    console.log(`[GrokSaver] ${msg}`);
}

chrome.storage.local.get(["processed_posts"], (result) => {
    if (result.processed_posts) {
        processedPosts = new Set(result.processed_posts);
    }
});

function savePostHistory(url) {
    processedPosts.add(url);
    chrome.storage.local.set({ "processed_posts": Array.from(processedPosts) });
}

function estimateSizeKB(src) {
    if (src.startsWith("data:")) {
        const base64Length = src.length - (src.indexOf(",") + 1);
        return (base64Length * 0.75) / 1024;
    }
    return 100;
}

// ------------------------------------
// 画像保存ロジック
// ------------------------------------
function checkAndSend(img) {
    const src = img.src;
    if (!src) return;

    if (processedCache.has(src)) return;

    const isTarget = (img.alt === CONFIG.targetAlt) || (src.includes("grok"));
    if (!isTarget) return;

    const size = estimateSizeKB(src);
    if (size < CONFIG.minSizeKB) return;

    if (!img.complete || img.naturalWidth === 0) return;

    const currentUrl = window.location.href;
    const isFavorites = currentUrl.includes("/favorites");

    chrome.runtime.sendMessage({
        action: "download_image",
        src: src,
        pageUrl: currentUrl,
        isFavorites: isFavorites
    });

    processedCache.add(src);

    const borderColor = isFavorites ? "#ff00ff" : "#00ff00";
    img.style.transition = "outline 0.3s";
    img.style.outline = `4px solid ${borderColor}`;
    setTimeout(() => {
        img.style.outline = "none";
    }, 1500);
}

// ------------------------------------
// プロンプト監視ロジック
// ------------------------------------
function checkPrompts() {
    const elements = document.querySelectorAll(CONFIG.promptSelector);
    elements.forEach(el => {
        const text = el.innerText;
        if (!text || text.trim().length === 0) return;

        // ★変更: 文字列ベースの重複チェックを廃止し、要素ベースのマーキングに変更
        // これにより、同じプロンプトを再度打ち込んだ際にも正しく保存される
        if (el.dataset.grokSaverProcessed === "true") return;

        chrome.runtime.sendMessage({
            action: "save_prompt",
            text: text.trim()
        });

        el.dataset.grokSaverProcessed = "true";
        el.style.borderBottom = "2px solid #00ff00";
    });
}

// ------------------------------------
// 動画 & ダウンロードボタン監視ロジック
// ------------------------------------
function checkVideoAndClick() {
    const currentUrl = window.location.href;
    if (!currentUrl.includes(CONFIG.videoUrlPattern)) return;
    if (processedPosts.has(currentUrl)) return;

    const videoLabel = Array.from(document.querySelectorAll('span.sr-only, span.font-semibold'))
        .find(el => el.textContent.trim() === "動画");

    if (videoLabel) {
        if (!videoLabel.classList.contains("text-primary")) {
            return;
        }
    }

    const videos = document.querySelectorAll('video');
    let hasVideo = false;
    for (const v of videos) {
        if (v.src && v.src.length > 0) { hasVideo = true; break; }
        const sources = v.querySelectorAll('source');
        for (const s of sources) {
            if (s.src && s.src.length > 0) { hasVideo = true; break; }
        }
    }

    if (!hasVideo) return;

    const btn = document.querySelector(CONFIG.downloadButtonSelector);
    if (btn) {
        log(`動画検知: DLボタン自動クリック`);
        savePostHistory(currentUrl);
        btn.style.border = "3px solid #0000ff";
        setTimeout(() => btn.style.border = "none", 1000);
        btn.click();
    }
}

// ------------------------------------
// 監視メインループ
// ------------------------------------
const observer = new MutationObserver((mutations) => {
    if (window.location.href !== lastUrl) {
        log("ページ遷移検知: 重複チェック用キャッシュをクリアしました");
        processedCache.clear();
        lastUrl = window.location.href;
    }

    checkVideoAndClick();
    checkPrompts();

    mutations.forEach((mutation) => {
        mutation.addedNodes.forEach((node) => {
            if (node.nodeType === 1) {
                if (node.tagName === "IMG") checkAndSend(node);
                const childImgs = node.querySelectorAll && node.querySelectorAll("img");
                if (childImgs && childImgs.length > 0) childImgs.forEach(checkAndSend);
            }
        });

        if (mutation.type === "attributes" && mutation.attributeName === "src") {
            const target = mutation.target;
            if (target.tagName === "IMG") checkAndSend(target);
        }
    });
});

observer.observe(document.body, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ["src"]
});

log("監視を開始しました（v2.1 / プロンプト重複チェック解除版）。");