// Listen for keyboard command and relay to content script
chrome.commands.onCommand.addListener((command) => {
  console.log("[Kioku] Command received:", command);
  if (command === "capture-subtitle") {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      console.log("[Kioku] Active tabs:", tabs);
      if (tabs[0]) {
        console.log("[Kioku] Sending message to tab:", tabs[0].id);
        chrome.tabs.sendMessage(tabs[0].id, { action: "capture" });
      }
    });
  }
});

console.log("[Kioku] Background service worker loaded");

// Get API URL from storage or use default
async function getApiUrl() {
  const data = await chrome.storage.local.get(['apiUrl']);
  return data.apiUrl || 'http://localhost:8000';
}

// Handle API calls from content script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "sendToApi") {
    // Make the API call from the service worker (not subject to mixed content restrictions)
    getApiUrl().then(apiUrl => {
      fetch(`${apiUrl}/api/extract-text`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: message.text }),
      })
        .then(async (resp) => {
          if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.detail || `HTTP ${resp.status}`);
          }
          return resp.json();
        })
        .then(async (data) => {
          // Store cards in chrome.storage for popup to display
          await chrome.storage.local.set({
            cards: data.cards || [],
            timestamp: Date.now()
          });

          // Auto-open popup after extraction
          if (data.cards && data.cards.length > 0) {
            chrome.action.openPopup().catch(() => {
              // If popup can't be opened programmatically (e.g., user gesture required),
              // the content script toast will still inform the user
            });
          }

          sendResponse({ cards: data.cards });
        })
        .catch((err) => {
          sendResponse({ error: err.message });
        });
    });

    // Return true to indicate async response
    return true;
  }

  if (message.action === "generateCards") {
    // Handle the generate API call for the popup
    getApiUrl().then(apiUrl => {
      fetch(`${apiUrl}/api/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          cards: message.cards,
          deck_name: message.deckName
        }),
      })
        .then(async (resp) => {
          if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.detail || `HTTP ${resp.status}`);
          }
          return resp.json();
        })
        .then((data) => {
          sendResponse({ added: data.added });
        })
        .catch((err) => {
          sendResponse({ error: err.message });
        });
    });

    return true;
  }
});
