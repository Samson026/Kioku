// Read current subtitle from Netflix DOM
function getCurrentSubtitle() {
  const container = document.querySelector(".player-timedtext");
  if (!container) return "";

  const spans = container.querySelectorAll("span");
  const text = Array.from(spans)
    .map((s) => s.textContent.trim())
    .filter(Boolean)
    .join(" ");

  return text;
}

// Show toast notification overlay on Netflix page
function showToast(message, isError = false) {
  const existing = document.getElementById("kioku-toast");
  if (existing) existing.remove();

  const toast = document.createElement("div");
  toast.id = "kioku-toast";
  toast.textContent = message;
  Object.assign(toast.style, {
    position: "fixed",
    top: "20px",
    right: "20px",
    padding: "12px 20px",
    borderRadius: "8px",
    background: isError ? "#c62828" : "#2e7d32",
    color: "#fff",
    fontSize: "14px",
    fontFamily: "system-ui, sans-serif",
    zIndex: "999999",
    opacity: "0.95",
    transition: "opacity 0.3s",
    maxWidth: "400px",
  });

  document.body.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    setTimeout(() => toast.remove(), 300);
  }, 2500);
}

// Send subtitle text to Kioku API via background service worker
async function sendToKioku(text) {
  if (!text) {
    showToast("No subtitle visible", true);
    return;
  }

  showToast(`Capturing: ${text.substring(0, 40)}...`);

  try {
    // Send to background service worker to make the actual API call
    const response = await chrome.runtime.sendMessage({
      action: "sendToApi",
      text: text
    });

    if (response.error) {
      throw new Error(response.error);
    }

    const count = response.cards ? response.cards.length : 0;
    showToast(`Captured ${count} card(s) - Open popup to review`);
  } catch (err) {
    showToast(`Error: ${err.message}`, true);
  }
}

// Capture and send current subtitle
function captureAndSend() {
  const text = getCurrentSubtitle();
  sendToKioku(text);
}

// Listen for messages from background script (keyboard shortcut)
chrome.runtime.onMessage.addListener((msg) => {
  console.log("[Kioku] Received message:", msg);
  if (msg.action === "capture") {
    console.log("[Kioku] Starting capture...");
    captureAndSend();
  }
});

console.log("[Kioku] Content script loaded on:", window.location.href);
