# Kioku Chrome Extension

Chrome extension for capturing Netflix subtitles and creating Anki flashcards via the Kioku API.

## Features

- **Alt+K keyboard shortcut** to capture the currently displayed subtitle on Netflix
- **Auto-popup** after extraction completes to review cards immediately
- **Dark mode** support with theme toggle (☾/☼)
- **Card filtering**: Choose between "All Cards" or "Sentence Only"
- Review and edit captured cards in the extension popup
- One-click "Add to Anki" to generate audio and push cards to Anki
- Inline card editing and deletion
- Toast notifications on Netflix page for immediate feedback
- Settings persist across sessions

## Installation

1. Make sure the Kioku API is running on `http://localhost:8000`
2. Open Chrome and navigate to `chrome://extensions`
3. Enable "Developer mode" (toggle in top right)
4. Click "Load unpacked"
5. Select the `kioku-chrome-extension` directory

## Usage

1. Open Netflix and play content with Japanese subtitles enabled
2. When a subtitle appears, press **Alt+K** to capture it
3. A toast notification will confirm the capture
4. Click the Kioku extension icon to open the popup
5. Review/edit the captured cards
6. Click "Add to Anki" to generate audio and push to your Anki deck

## Requirements

- Chrome browser
- Kioku API running locally on port 8000
- Anki desktop app with AnkiConnect add-on installed
- Netflix subscription with Japanese subtitle content

## Development

The extension uses plain JavaScript (no build tools required):

- `manifest.json` - Extension configuration
- `background.js` - Keyboard command listener
- `content.js` - Netflix subtitle reader and API communication
- `popup.html/js/css` - Card review UI

## Future Enhancements

- YouTube subtitle support
- Custom keyboard shortcut configuration
- Multiple language support
- Auto-pause on capture (optional)
