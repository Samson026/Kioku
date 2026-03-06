function getCurrentSubtitle() {
  const container = document.querySelector(".player-timedtext");
  if (!container) return "";
  const spans = container.querySelectorAll("span:not(:has(span))");
  return Array.from(spans).map(s => s.textContent.trim()).filter(Boolean).join(" ");
}

function showToast(message, isError = false) {
  const existing = document.getElementById("kioku-toast");
  if (existing) existing.remove();
  const toast = document.createElement("div");
  toast.id = "kioku-toast";
  toast.textContent = message;
  Object.assign(toast.style, {
    position: "fixed", top: "20px", right: "20px",
    padding: "12px 20px", borderRadius: "8px",
    background: isError ? "#c62828" : "#2e7d32",
    color: "#fff", fontSize: "14px", fontFamily: "system-ui, sans-serif",
    zIndex: "999999", opacity: "0.95", maxWidth: "400px",
  });
  document.body.appendChild(toast);
  setTimeout(() => { toast.style.opacity = "0"; setTimeout(() => toast.remove(), 300); }, 2500);
}

let currentSubtitleText = "";
let subtitleStartVideoTime = null;  // video.currentTime when current subtitle appeared

function setupObserver() {
  const container = document.querySelector(".player-timedtext");
  if (!container) { setTimeout(setupObserver, 1000); return; }

  new MutationObserver(() => {
    const text = getCurrentSubtitle();
    if (text === currentSubtitleText) return;

    currentSubtitleText = text;

    if (text) {
      const video = document.querySelector("video");
      subtitleStartVideoTime = video ? video.currentTime : null;
    }
  }).observe(container, { childList: true, subtree: true, characterData: true });
}
setupObserver();

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === "getSubtitle") {
    sendResponse({ text: currentSubtitleText || null });
  }

  if (msg.action === "seekToSubtitleStart") {
    const video = document.querySelector("video");
    const time = subtitleStartVideoTime;
    if (!video || time == null) { sendResponse({ ok: false }); return; }
    const timeMs = Math.max(0, (time - 0.1) * 1000);
    // Attach listener BEFORE dispatching so we can't miss a fast/sync seeked event.
    // Fallback timeout in case seeked never fires (e.g. already at that position).
    const timeout = setTimeout(() => sendResponse({ ok: true }), 2000);
    video.addEventListener("seeked", () => { clearTimeout(timeout); sendResponse({ ok: true }); }, { once: true });
    window.dispatchEvent(new CustomEvent("kioku-seek", { detail: { timeMs } }));
    return true; // async response
  }

  if (msg.action === "showToast") {
    showToast(msg.text, msg.isError);
    sendResponse({ ok: true });
  }

  if (msg.action === "ensurePlaying") {
    const video = document.querySelector("video");
    if (video?.paused) video.play();
    sendResponse({ ok: true });
  }

  if (msg.action === "pauseVideo") {
    const video = document.querySelector("video");
    if (video) video.pause();
    sendResponse({ ok: true });
  }

  // Watch for the current subtitle to finish, then notify background.
  // First waits for a subtitle to appear (in case we seeked to just before it),
  // then watches for it to change/disappear.
  if (msg.action === "watchSubtitleEnd") {
    const waitForSubtitle = () => {
      if (!currentSubtitleText) {
        requestAnimationFrame(waitForSubtitle);
        return;
      }
      const activeText = currentSubtitleText;
      const watchEnd = () => {
        if (currentSubtitleText !== activeText) {
          chrome.runtime.sendMessage({ action: "subtitleEnded" });
        } else {
          requestAnimationFrame(watchEnd);
        }
      };
      requestAnimationFrame(watchEnd);
    };
    requestAnimationFrame(waitForSubtitle);
    sendResponse({ ok: true });
  }
});

console.log("[Kioku] Content script loaded");
