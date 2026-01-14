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



    document.getElementById("grok-btn").addEventListener("click", () => {
        chrome.tabs.create({ url: "https://grok.com/imagine/favorites" });
    });

    document.getElementById("folder-btn").addEventListener("click", () => {
        chrome.downloads.showDefaultFolder();
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

