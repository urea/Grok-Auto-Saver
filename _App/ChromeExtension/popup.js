// popup.js - GrokSaver v2.1 (Fixed Path)
// プロンプト本文保存用キー
const PROMPT_TEXT_KEY = "grok_saver_prompt_texts";
const PROMPT_HASH_KEY = "grok_saver_prompts";

document.addEventListener("DOMContentLoaded", () => {
    loadPrompts();

    document.getElementById("clear-btn").addEventListener("click", () => {
        if (confirm("プロンプト履歴をすべて消去しますか？")) {
            chrome.storage.local.remove([PROMPT_TEXT_KEY, PROMPT_HASH_KEY], () => {
                loadPrompts();
            });
        }
    });

    document.getElementById("export-btn").addEventListener("click", () => {
        exportPrompts();
    });

    document.getElementById("grok-btn").addEventListener("click", () => {
        chrome.tabs.create({ url: "https://grok.com/imagine/favorites" });
    });
});

function loadPrompts() {
    const listEl = document.getElementById("prompt-list");
    const emptyMsg = document.getElementById("empty-msg");
    listEl.innerHTML = "";

    chrome.storage.local.get([PROMPT_TEXT_KEY], (result) => {
        const texts = result[PROMPT_TEXT_KEY] || [];

        if (texts.length === 0) {
            emptyMsg.style.display = "block";
            return;
        }

        emptyMsg.style.display = "none";

        texts.forEach((item) => {
            const li = document.createElement("li");
            li.className = "prompt-item";

            const btn = document.createElement("button");
            btn.className = "copy-btn";
            btn.textContent = "コピー";
            btn.onclick = () => {
                navigator.clipboard.writeText(item.text).then(() => {
                    btn.textContent = "完了!";
                    setTimeout(() => btn.textContent = "コピー", 1000);
                });
            };

            const dateDiv = document.createElement("div");
            dateDiv.className = "prompt-date";
            dateDiv.textContent = item.date;

            const textDiv = document.createElement("div");
            textDiv.className = "prompt-text";
            textDiv.textContent = item.text;

            li.appendChild(btn);
            li.appendChild(dateDiv);
            li.appendChild(textDiv);
            listEl.appendChild(li);
        });
    });
}

function exportPrompts() {
    chrome.storage.local.get([PROMPT_TEXT_KEY], (result) => {
        const texts = result[PROMPT_TEXT_KEY] || [];

        if (texts.length === 0) {
            alert("エクスポートする履歴がありません。");
            return;
        }

        let fileContent = "GrokSaver Prompt History\n";
        fileContent += "====================================\n\n";

        texts.forEach((item) => {
            fileContent += `[${item.date}]\n`;
            const formattedText = item.text.replace(/ -/g, '\n -').replace(/# /g, '\n# ');
            fileContent += `${formattedText}\n`;
            fileContent += "------------------------------------\n\n";
        });

        const now = new Date();
        const y = now.getFullYear();
        const m = String(now.getMonth() + 1).padStart(2, '0');
        const d = String(now.getDate()).padStart(2, '0');
        const h = String(now.getHours()).padStart(2, '0');
        const min = String(now.getMinutes()).padStart(2, '0');
        const s = String(now.getSeconds()).padStart(2, '0');

        // ★修正済み: ルートフォルダを Grok-Auto-Saver/_Data に統一
        const filename = `Grok-Auto-Saver/_Data/Prompts/prompts_${y}${m}${d}${h}${min}${s}.txt`;

        const bom = new Uint8Array([0xEF, 0xBB, 0xBF]);
        const blob = new Blob([bom, fileContent], { type: "text/plain" });
        const url = URL.createObjectURL(blob);

        chrome.downloads.download({
            url: url,
            filename: filename,
            saveAs: false,
            conflictAction: 'uniquify'
        }, (downloadId) => {
            if (chrome.runtime.lastError) {
                console.error("Export failed:", chrome.runtime.lastError);
                alert("保存に失敗しました: " + chrome.runtime.lastError.message);
            } else {
                setTimeout(() => URL.revokeObjectURL(url), 10000);
            }
        });
    });
}