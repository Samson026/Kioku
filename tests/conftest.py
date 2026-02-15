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
    monkeypatch.setenv("VOICEVOX_URL", "http://test-voicevox:50021")
    monkeypatch.setenv("VOICEVOX_SPEAKER", "0")


@pytest.fixture
def sample_card_item():
    """Single CardItem for testing."""
    return CardItem(
        japanese="こんにちは",
        reading="こんにちは",
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
            reading="こんにちは",
            meaning="Hello",
            example_sentence="こんにちは、元気ですか？",
            example_translation="Hello, how are you?",
        ),
        CardItem(
            japanese="元気",
            reading="げんき",
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
                            "reading": "こんにちは",
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
def mock_manga_ocr(monkeypatch):
    """Mock Manga OCR to avoid loading the model."""
    mock_ocr = Mock()
    mock_ocr.return_value = "こんにちは"

    # Mock the module-level _mocr instance
    monkeypatch.setattr("kioku.services.image_processor._mocr", mock_ocr)

    return mock_ocr


@pytest.fixture
def mock_voicevox(monkeypatch):
    """Mock VOICEVOX HTTP API."""

    class MockResponse:
        def __init__(self, json_data=None, content=None, status_code=200):
            self._json_data = json_data
            self.content = content
            self.status_code = status_code

        def json(self):
            return self._json_data

        def raise_for_status(self):
            if self.status_code >= 400:
                import httpx
                raise httpx.HTTPStatusError(
                    "HTTP Error",
                    request=Mock(),
                    response=self
                )

    class MockAsyncClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, **kwargs):
            if "audio_query" in url:
                return MockResponse(json_data={"query": "mock_audio_query"})
            elif "synthesis" in url:
                return MockResponse(content=b"mock_wav_audio_data")
            else:
                return MockResponse(status_code=404)

    monkeypatch.setattr("httpx.AsyncClient", MockAsyncClient)
    return MockAsyncClient


@pytest.fixture
def mock_anki_connect(monkeypatch):
    """Mock AnkiConnect HTTP requests."""
    responses = {
        "modelNames": ["Japanese Vocab (ankiGen)"],
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
