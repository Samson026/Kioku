let audioStreamTabId = null;
let subtitleEndResolve = null;

// ── Keyboard shortcut ────────────────────────────────────────────────────────

chrome.commands.onCommand.addListener((command) => {
  if (command === "capture-subtitle") handleCapture();
});

async function handleCapture() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab) return;

  if (audioStreamTabId !== tab.id) {
    const ok = await initStream(tab.id);
    if (!ok) { console.log("[Kioku] Could not init audio stream"); return; }
  }

  const { text } = await chrome.tabs.sendMessage(tab.id, { action: "getSubtitle" }).catch(() => ({}));
  if (!text) { console.log("[Kioku] No subtitle"); return; }

  // Seek to subtitle start, then record through to the end
  await chrome.tabs.sendMessage(tab.id, { action: "seekToSubtitleStart" }).catch(() => {});
  await chrome.runtime.sendMessage({ action: "startRecording" });
  await chrome.tabs.sendMessage(tab.id, { action: "ensurePlaying" }).catch(() => {});
  chrome.tabs.sendMessage(tab.id, { action: "watchSubtitleEnd" });

  console.log("[Kioku] Recording — waiting for subtitle to end...");
  await new Promise((resolve) => {
    subtitleEndResolve = resolve;
    setTimeout(() => { subtitleEndResolve = null; resolve(); }, 15000);
  });

  const r = await chrome.runtime.sendMessage({ action: "stopRecording" });
  await chrome.tabs.sendMessage(tab.id, { action: "pauseVideo" }).catch(() => {});

  console.log("[Kioku] Storing. audio =", r?.audio ? `${r.audio.length} chars` : "null");
  await chrome.storage.local.set({ pendingText: text, pendingAudio: r?.audio || null });
  chrome.action.openPopup().catch(e => console.log("[Kioku] openPopup:", e.message));
}

// ── Stream / offscreen helpers ───────────────────────────────────────────────

async function initStream(tabId) {
  try {
    await ensureOffscreenDocument();
    const streamId = await chrome.tabCapture.getMediaStreamId({ targetTabId: tabId });
    const r = await chrome.runtime.sendMessage({ action: "initStream", streamId });
    if (r?.ok) { audioStreamTabId = tabId; console.log("[Kioku] Stream ready for tab", tabId); return true; }
    console.log("[Kioku] initStream failed:", r?.error);
    return false;
  } catch (e) { console.log("[Kioku] initStream error:", e.message); return false; }
}

async function ensureOffscreenDocument() {
  const contexts = await chrome.runtime.getContexts({ contextTypes: ["OFFSCREEN_DOCUMENT"] });
  if (contexts.length === 0) {
    await chrome.offscreen.createDocument({
      url: "offscreen.html",
      reasons: ["USER_MEDIA"],
      justification: "Recording tab audio for Anki flashcards",
    });
  }
}

// ── Message handler ──────────────────────────────────────────────────────────

async function getApiUrl() {
  const { apiUrl } = await chrome.storage.local.get(["apiUrl"]);
  return apiUrl || "http://localhost:8000";
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "subtitleEnded") {
    if (subtitleEndResolve) { subtitleEndResolve(); subtitleEndResolve = null; }
    return;
  }

  if (message.action === "sendToApi") {
    getApiUrl().then(apiUrl =>
      fetch(`${apiUrl}/api/extract-text`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: message.text }),
      })
      .then(r => r.ok ? r.json() : r.json().then(e => Promise.reject(e.detail || `HTTP ${r.status}`)))
      .then(async data => {
        await chrome.storage.local.set({ cards: data.cards || [], timestamp: Date.now() });
        sendResponse({ cards: data.cards });
      })
      .catch(err => sendResponse({ error: String(err) }))
    );
    return true;
  }

  if (message.action === "generateCards") {
    getApiUrl().then(apiUrl =>
      fetch(`${apiUrl}/api/generate`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          cards: message.cards, deck_name: message.deckName,
          sentence_audio_b64: message.sentenceAudioB64 || null,
        }),
      })
      .then(r => r.ok ? r.json() : r.json().then(e => Promise.reject(e.detail || `HTTP ${r.status}`)))
      .then(data => sendResponse({ added: data.added }))
      .catch(err => sendResponse({ error: String(err) }))
    );
    return true;
  }
});

console.log("[Kioku] Background loaded");
