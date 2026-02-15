let currentCards = [];
let cardMode = 'all'; // 'all' or 'sentence'
let theme = 'light';
let apiUrl = 'http://localhost:8000';

// Initialize settings from storage
async function initSettings() {
  const data = await chrome.storage.local.get(['cardMode', 'theme', 'apiUrl']);
  cardMode = data.cardMode || 'all';
  theme = data.theme || 'light';
  apiUrl = data.apiUrl || 'http://localhost:8000';

  // Apply theme
  document.documentElement.setAttribute('data-theme', theme);
  updateThemeIcon();

  // Update API URL input
  document.getElementById('api-url').value = apiUrl;

  // Update card mode buttons
  document.querySelectorAll('.toggle-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.mode === cardMode);
  });
}

// Toggle theme
function toggleTheme() {
  theme = theme === 'light' ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', theme);
  chrome.storage.local.set({ theme });
  updateThemeIcon();
}

// Update theme icon
function updateThemeIcon() {
  const icon = document.getElementById('theme-toggle');
  icon.textContent = theme === 'light' ? '☾' : '☼';
}

// Toggle settings panel
function toggleSettings() {
  const panel = document.getElementById('settings-panel');
  const isVisible = panel.style.display !== 'none';
  panel.style.display = isVisible ? 'none' : 'block';
}

// Set card mode
function setCardMode(mode) {
  cardMode = mode;
  chrome.storage.local.set({ cardMode });

  // Update button states
  document.querySelectorAll('.toggle-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.mode === mode);
  });

  // Reload cards with filter
  loadCards();
}

// Filter cards based on mode
function filterCards(cards) {
  if (cardMode === 'sentence') {
    return cards.filter(c => c.japanese === c.example_sentence);
  }
  return cards;
}

// Check for pending extracted text and show extraction panel if present
async function checkPendingExtraction() {
  const data = await chrome.storage.local.get(['pendingText']);

  if (data.pendingText) {
    showExtractionPanel(data.pendingText);
    return true;
  }
  return false;
}

// Show the extraction panel with the extracted text
function showExtractionPanel(text) {
  const extractionPanel = document.getElementById('extraction-panel');
  const extractedText = document.getElementById('extracted-text');
  const cardsContainer = document.getElementById('cards-container');
  const status = document.getElementById('status');
  const actions = document.getElementById('actions');

  extractedText.value = text;
  extractionPanel.style.display = 'block';
  cardsContainer.style.display = 'none';
  status.style.display = 'none';
  actions.style.display = 'none';

  // Focus the textarea and select all text for easy editing
  setTimeout(() => {
    extractedText.focus();
    extractedText.select();
  }, 100);
}

// Hide the extraction panel
function hideExtractionPanel() {
  const extractionPanel = document.getElementById('extraction-panel');
  const cardsContainer = document.getElementById('cards-container');

  extractionPanel.style.display = 'none';
  cardsContainer.style.display = 'block';
}

// Process the extracted text through the API
async function processExtractedText() {
  const extractedText = document.getElementById('extracted-text').value.trim();
  const status = document.getElementById('status');

  if (!extractedText) {
    status.textContent = 'Please enter some text to process';
    status.className = 'status error';
    status.style.display = 'block';
    return;
  }

  status.textContent = 'Processing text...';
  status.className = 'status';
  status.style.display = 'block';

  try {
    // Send to background service worker to make the actual API call
    const response = await chrome.runtime.sendMessage({
      action: "sendToApi",
      text: extractedText
    });

    if (response.error) {
      throw new Error(response.error);
    }

    // Clear pending text
    await chrome.storage.local.remove('pendingText');

    // Hide extraction panel and show cards
    hideExtractionPanel();

    // Load the cards
    await loadCards();

    const count = response.cards ? response.cards.length : 0;
    status.textContent = `Processed ${count} card(s)`;
    status.className = 'status success';

  } catch (err) {
    status.textContent = `Error: ${err.message}`;
    status.className = 'status error';
  }
}

// Cancel extraction
async function cancelExtraction() {
  await chrome.storage.local.remove('pendingText');
  hideExtractionPanel();
  loadCards();
}

// Load and display cards from storage
async function loadCards() {
  const data = await chrome.storage.local.get(['cards', 'timestamp']);
  const allCards = data.cards || [];
  currentCards = filterCards(allCards);

  const container = document.getElementById('cards-container');
  const status = document.getElementById('status');
  const actions = document.getElementById('actions');
  const extractionPanel = document.getElementById('extraction-panel');

  // Make sure extraction panel is hidden
  extractionPanel.style.display = 'none';
  container.style.display = 'block';

  if (currentCards.length === 0) {
    status.textContent = 'No cards captured yet';
    status.style.display = 'block';
    container.innerHTML = '';
    actions.style.display = 'none';
    return;
  }

  status.style.display = 'none';
  actions.style.display = 'flex';

  container.innerHTML = currentCards.map((card, index) => `
    <div class="card" data-index="${index}">
      <button class="delete-btn" data-index="${index}">×</button>
      <div class="field">
        <label>Japanese:</label>
        <input type="text" class="card-field" data-index="${index}" data-field="japanese" value="${escapeHtml(card.japanese)}">
      </div>
      <div class="field">
        <label>Reading:</label>
        <input type="text" class="card-field" data-index="${index}" data-field="reading" value="${escapeHtml(card.reading)}">
      </div>
      <div class="field">
        <label>Meaning:</label>
        <input type="text" class="card-field" data-index="${index}" data-field="meaning" value="${escapeHtml(card.meaning)}">
      </div>
      <div class="field">
        <label>Example:</label>
        <input type="text" class="card-field" data-index="${index}" data-field="example_sentence" value="${escapeHtml(card.example_sentence)}">
      </div>
      <div class="field">
        <label>Translation:</label>
        <input type="text" class="card-field" data-index="${index}" data-field="example_translation" value="${escapeHtml(card.example_translation)}">
      </div>
    </div>
  `).join('');

  // Add event listeners for editing
  container.querySelectorAll('.card-field').forEach(input => {
    input.addEventListener('input', handleFieldEdit);
  });

  // Add event listeners for delete buttons
  container.querySelectorAll('.delete-btn').forEach(btn => {
    btn.addEventListener('click', handleDelete);
  });
}

// Handle field edits
function handleFieldEdit(e) {
  const index = parseInt(e.target.dataset.index);
  const field = e.target.dataset.field;
  currentCards[index][field] = e.target.value;
}

// Handle card deletion
async function handleDelete(e) {
  const index = parseInt(e.target.dataset.index);
  currentCards.splice(index, 1);
  await chrome.storage.local.set({ cards: currentCards });
  loadCards();
}

// Clear all cards
async function clearCards() {
  currentCards = [];
  await chrome.storage.local.set({ cards: [] });
  loadCards();
}

// Add cards to Anki via background service worker
async function addToAnki() {
  const deckName = document.getElementById('deck-name').value || 'Kioku';
  const status = document.getElementById('status');

  if (currentCards.length === 0) {
    status.textContent = 'No cards to add';
    status.style.display = 'block';
    return;
  }

  status.textContent = 'Adding to Anki...';
  status.style.display = 'block';

  try {
    const response = await chrome.runtime.sendMessage({
      action: "generateCards",
      cards: currentCards,
      deckName: deckName
    });

    if (response.error) {
      throw new Error(response.error);
    }

    status.textContent = `Successfully added ${response.added} card(s) to Anki!`;
    status.className = 'status success';

    // Clear cards after successful add
    setTimeout(() => {
      clearCards();
    }, 1500);

  } catch (err) {
    status.textContent = `Error: ${err.message}`;
    status.className = 'status error';
  }
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Save API URL when it changes
function saveApiUrl() {
  const input = document.getElementById('api-url');
  let url = input.value.trim();

  // Remove trailing slash if present
  if (url.endsWith('/')) {
    url = url.slice(0, -1);
  }

  // Validate URL format
  if (url && !url.match(/^https?:\/\/.+/)) {
    input.style.borderColor = 'var(--error-text)';
    return;
  }

  input.style.borderColor = '';
  apiUrl = url || 'http://localhost:8000';
  chrome.storage.local.set({ apiUrl });
}

// Event listeners
document.getElementById('add-to-anki').addEventListener('click', addToAnki);
document.getElementById('clear-btn').addEventListener('click', clearCards);
document.getElementById('theme-toggle').addEventListener('click', toggleTheme);
document.getElementById('settings-toggle').addEventListener('click', toggleSettings);
document.getElementById('api-url').addEventListener('input', saveApiUrl);
document.getElementById('process-text').addEventListener('click', processExtractedText);
document.getElementById('cancel-extraction').addEventListener('click', cancelExtraction);

// Card mode toggle buttons
document.querySelectorAll('.toggle-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    setCardMode(btn.dataset.mode);
  });
});

// Initialize and load
initSettings().then(async () => {
  // Check for pending extraction first, if none then load cards
  const hasPendingExtraction = await checkPendingExtraction();
  if (!hasPendingExtraction) {
    loadCards();
  }
});
