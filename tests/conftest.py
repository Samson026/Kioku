"""Pytest configuration and shared fixtures."""

import io
import json
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from kioku.models import CardItem


@pytest.fixture(autouse=True)
def set_test_env(monkeypatch):
    """Set test environment variables for all tests."""
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("GROQ_MODEL", "test-model")
    monkeypatch.setenv("ANKI_CONNECT_URL", "http://test-anki:8765")


@pytest.fixture
def sample_card_item():
    """Single CardItem for testing."""
    return CardItem(
        japanese="こんにちは",
        meaning="Hello",
        example_sentence="こんにちは、元気ですか？",
        example_translation="Hello, how are you?",
    )


@pytest.fixture
def sample_cards():
    """List of CardItem objects for testing."""
    return [
        CardItem(
            japanese="こんにちは",
            meaning="Hello",
            example_sentence="こんにちは、元気ですか？",
            example_translation="Hello, how are you?",
        ),
        CardItem(
            japanese="元気",
            meaning="Well, healthy, energetic",
            example_sentence="元気です。",
            example_translation="I'm fine.",
        ),
    ]


@pytest.fixture
def sample_image_bytes():
    """Simple test image as bytes."""
    img = Image.new("RGB", (100, 100), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


@pytest.fixture
def mock_groq_client(monkeypatch):
    """Mock Groq API client."""
    mock_response = Mock()
    mock_response.choices = [
        Mock(
            message=Mock(
                content=json.dumps(
                    [
                        {
                            "japanese": "こんにちは",
                            "meaning": "Hello",
                            "example_sentence": "こんにちは、元気ですか？",
                            "example_translation": "Hello, how are you?",
                        }
                    ]
                )
            )
        )
    ]

    mock_client = Mock()
    mock_client.chat.completions.create.return_value = mock_response

    def mock_groq_init(self, api_key):
        return None

    # Mock Groq class
    mock_groq_class = Mock(return_value=mock_client)
    monkeypatch.setattr("kioku.services.image_processor.Groq", mock_groq_class)

    return mock_client


@pytest.fixture
def mock_pytesseract(monkeypatch):
    """Mock pytesseract to avoid requiring Tesseract binary."""
    mock_fn = Mock(return_value="Hello")
    monkeypatch.setattr("kioku.services.image_processor.pytesseract.image_to_string", mock_fn)
    return mock_fn


@pytest.fixture
def mock_edge_tts(monkeypatch):
    """Mock Edge TTS audio generation."""

    class MockCommunicate:
        def __init__(self, text, voice):
            self.text = text
            self.voice = voice

        async def stream(self):
            # Simulate audio chunks
            yield {"type": "audio", "data": b"mock_audio_chunk_1"}
            yield {"type": "audio", "data": b"mock_audio_chunk_2"}

    monkeypatch.setattr("kioku.services.audio_generator.edge_tts.Communicate", MockCommunicate)

    return MockCommunicate


@pytest.fixture
def mock_anki_connect(monkeypatch):
    """Mock AnkiConnect HTTP requests."""
    responses = {
        "modelNames": ["English-Japanese Vocab (ankiGen)"],
        "createDeck": None,
        "createModel": None,
        "storeMediaFile": None,
        "addNote": 1234567890,
    }

    def mock_urlopen(request):
        # Parse request to determine action
        body = json.loads(request.data.decode())
        action = body.get("action")
        result = responses.get(action)

        mock_response = Mock()
        mock_response.read.return_value = json.dumps(
            {"result": result, "error": None}
        ).encode()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)

        return mock_response

    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)

    return responses


@pytest.fixture
def test_client():
    """FastAPI TestClient for integration tests."""
    from kioku.main import app

    return TestClient(app)
