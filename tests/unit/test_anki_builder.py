"""Unit tests for anki_builder service."""

import json
import re
from unittest.mock import Mock

import pytest

from kioku.services.anki_builder import (
    _anki_request,
    _audio_filename,
    _ensure_deck,
    _ensure_model,
    add_cards,
)


class TestAnkiRequest:
    """Tests for _anki_request function."""

    def test_anki_request_success(self, mock_anki_connect):
        """Test successful AnkiConnect request."""
        result = _anki_request("modelNames")
        assert result == ["English-Japanese Vocab (ankiGen)"]

    def test_anki_request_with_params(self, mock_anki_connect):
        """Test AnkiConnect request with parameters."""
        result = _anki_request("createDeck", deck="TestDeck")
        assert result is None

    def test_anki_request_error_response(self, monkeypatch):
        """Test AnkiConnect request with error response."""

        def mock_urlopen_error(request):
            mock_response = Mock()
            mock_response.read.return_value = json.dumps(
                {"result": None, "error": "Deck not found"}
            ).encode()
            mock_response.__enter__ = Mock(return_value=mock_response)
            mock_response.__exit__ = Mock(return_value=False)
            return mock_response

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen_error)

        with pytest.raises(RuntimeError, match="AnkiConnect error: Deck not found"):
            _anki_request("someAction")


class TestEnsureModel:
    """Tests for _ensure_model function."""

    def test_ensure_model_already_exists(self, mock_anki_connect):
        """Test ensure_model when model already exists."""
        _ensure_model("English-Japanese Vocab (ankiGen)")
        # Should not raise any errors

    def test_ensure_model_creates_new(self, monkeypatch):
        """Test ensure_model creates new model if it doesn't exist."""
        create_model_called = False

        def mock_urlopen_create(request):
            nonlocal create_model_called
            body = json.loads(request.data.decode())
            action = body.get("action")

            if action == "modelNames":
                result = []  # Model doesn't exist
            elif action == "createModel":
                create_model_called = True
                result = None
            else:
                result = None

            mock_response = Mock()
            mock_response.read.return_value = json.dumps(
                {"result": result, "error": None}
            ).encode()
            mock_response.__enter__ = Mock(return_value=mock_response)
            mock_response.__exit__ = Mock(return_value=False)
            return mock_response

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen_create)

        _ensure_model("English-Japanese Vocab (ankiGen)")
        assert create_model_called


class TestEnsureDeck:
    """Tests for _ensure_deck function."""

    def test_ensure_deck_success(self, mock_anki_connect):
        """Test ensure_deck creates deck."""
        _ensure_deck("TestDeck")
        # Should not raise any errors


class TestAddCards:
    """Tests for add_cards function."""

    def test_add_cards_success(self, sample_cards, mock_anki_connect):
        """Test successfully adding cards to Anki."""
        audio_map = {
            sample_cards[0].meaning: b"audio_data_1",
            sample_cards[0].example_sentence: b"audio_data_2",
            sample_cards[1].meaning: b"audio_data_3",
            sample_cards[1].example_sentence: b"audio_data_4",
        }

        count = add_cards(sample_cards, audio_map, deck_name="TestDeck")

        assert count == 2

    def test_add_cards_default_deck(self, sample_cards, mock_anki_connect):
        """Test adding cards with default deck name."""
        audio_map = {
            sample_cards[0].meaning: b"audio_data_1",
            sample_cards[0].example_sentence: b"audio_data_2",
            sample_cards[1].meaning: b"audio_data_3",
            sample_cards[1].example_sentence: b"audio_data_4",
        }

        count = add_cards(sample_cards, audio_map)
        assert count == 2

    def test_add_cards_stores_audio(self, sample_card_item, mock_anki_connect, monkeypatch):
        """Test that add_cards stores audio files."""
        audio_stored = []

        def mock_urlopen_track_audio(request):
            body = json.loads(request.data.decode())
            action = body.get("action")

            if action == "storeMediaFile":
                audio_stored.append(body["params"]["filename"])

            result = {
                "modelNames": ["English-Japanese Vocab (ankiGen)"],
                "createDeck": None,
                "storeMediaFile": None,
                "addNote": 1234567890,
            }.get(action)

            mock_response = Mock()
            mock_response.read.return_value = json.dumps(
                {"result": result, "error": None}
            ).encode()
            mock_response.__enter__ = Mock(return_value=mock_response)
            mock_response.__exit__ = Mock(return_value=False)
            return mock_response

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen_track_audio)

        audio_map = {
            sample_card_item.meaning: b"audio1",
            sample_card_item.example_sentence: b"audio2",
        }
        add_cards([sample_card_item], audio_map)

        assert any(name.startswith("word_") and name.endswith(".mp3") for name in audio_stored)
        assert any(name.startswith("sentence_") and name.endswith(".mp3") for name in audio_stored)

    def test_add_cards_anki_connect_error(self, sample_cards, monkeypatch):
        """Test add_cards handles AnkiConnect errors."""

        def mock_urlopen_error(request):
            mock_response = Mock()
            mock_response.read.return_value = json.dumps(
                {"result": None, "error": "Failed to add note"}
            ).encode()
            mock_response.__enter__ = Mock(return_value=mock_response)
            mock_response.__exit__ = Mock(return_value=False)
            return mock_response

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen_error)

        audio_map = {
            sample_cards[0].meaning: b"audio1",
            sample_cards[0].example_sentence: b"audio2",
            sample_cards[1].meaning: b"audio3",
            sample_cards[1].example_sentence: b"audio4",
        }

        with pytest.raises(RuntimeError, match="AnkiConnect error"):
            add_cards(sample_cards, audio_map)

    def test_add_cards_empty_list(self, mock_anki_connect):
        """Test adding empty card list."""
        audio_map = {}
        count = add_cards([], audio_map)
        assert count == 0

    def test_audio_filename_uses_text_and_hash(self):
        """Test audio filename is deterministic and text-derived."""
        filename = _audio_filename("word", "Hello world")
        assert filename.startswith("word_hello-world_")
        assert filename.endswith(".mp3")
        assert re.match(r"^word_[a-z0-9-]+_[0-9a-f]{10}\.mp3$", filename)
