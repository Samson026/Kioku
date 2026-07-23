"""Integration tests for FastAPI endpoints."""

import io
import json
from unittest.mock import Mock

import httpx
import pytest
from anthropic import APIError, AuthenticationError


class TestExtractEndpoint:
    """Tests for POST /api/extract endpoint."""

    def test_extract_success(
        self, test_client, sample_image_bytes, mock_manga_ocr, mock_claude_client
    ):
        """Test successful image extraction."""
        files = {"file": ("test.png", io.BytesIO(sample_image_bytes), "image/png")}
        response = test_client.post("/api/extract", files=files)

        assert response.status_code == 200
        data = response.json()
        assert "cards" in data
        assert len(data["cards"]) >= 1
        assert "japanese" in data["cards"][0]
        assert "reading" in data["cards"][0]
        assert "meaning" in data["cards"][0]

    def test_extract_missing_file(self, test_client):
        """Test extraction without file returns 422."""
        response = test_client.post("/api/extract")
        assert response.status_code == 422

    def test_extract_empty_ocr_result(
        self, test_client, sample_image_bytes, mock_manga_ocr
    ):
        """Test extraction with empty OCR result returns 500."""
        mock_manga_ocr.return_value = ""

        files = {"file": ("test.png", io.BytesIO(sample_image_bytes), "image/png")}
        response = test_client.post("/api/extract", files=files)

        assert response.status_code == 500
        assert "Manga OCR returned no text" in response.json()["detail"]


class TestExtractTextEndpoint:
    """Tests for POST /api/extract-text endpoint."""

    def test_extract_text_success(self, test_client, mock_claude_client):
        """Test successful text extraction."""
        payload = {"text": "こんにちは"}
        response = test_client.post("/api/extract-text", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "cards" in data
        assert len(data["cards"]) >= 1
        assert data["cards"][0]["japanese"] == "こんにちは"

    def test_extract_text_empty_text(self, test_client):
        """Test extraction with empty text returns 500."""
        payload = {"text": ""}
        response = test_client.post("/api/extract-text", json=payload)

        assert response.status_code == 500
        assert "No text provided" in response.json()["detail"]

    def test_extract_text_missing_field(self, test_client):
        """Test extraction without text field returns 422."""
        payload = {}
        response = test_client.post("/api/extract-text", json=payload)

        assert response.status_code == 422

    def test_extract_text_whitespace_only(self, test_client):
        """Test extraction with whitespace-only text returns 500."""
        payload = {"text": "   "}
        response = test_client.post("/api/extract-text", json=payload)

        assert response.status_code == 500
        assert "No text provided" in response.json()["detail"]


class TestExtractKanjiEndpoint:
    """Tests for POST /api/extract-kanji endpoint."""

    def test_extract_kanji_success(self, test_client, mock_claude_client):
        mock_claude_client.messages.create.return_value.content[0].text = json.dumps(
            [
                {
                    "kanji": "日",
                    "onyomi": "ニチ",
                    "kunyomi": "ひ",
                    "meaning": "day; sun",
                    "example_word": "日本",
                    "example_word_reading": "にほん",
                }
            ]
        )

        response = test_client.post("/api/extract-kanji", json={"text": "日本"})

        assert response.status_code == 200
        assert response.json()["cards"][0]["kanji"] == "日"


@pytest.mark.parametrize(
    ("path", "service_name"),
    [
        ("/api/extract", "extract_cards"),
        ("/api/extract-text", "enrich_text"),
        ("/api/extract-kanji", "extract_kanji"),
    ],
)
def test_claude_api_errors_return_502(
    path,
    service_name,
    test_client,
    sample_image_bytes,
    monkeypatch,
):
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    error = APIError("Anthropic unavailable", request, body=None)
    monkeypatch.setattr(f"kioku.main.{service_name}", Mock(side_effect=error))

    if path == "/api/extract":
        files = {"file": ("test.png", io.BytesIO(sample_image_bytes), "image/png")}
        response = test_client.post(path, files=files)
    else:
        response = test_client.post(path, json={"text": "日本"})

    assert response.status_code == 502
    assert "Claude" in response.json()["detail"]


@pytest.mark.parametrize(
    ("path", "service_name"),
    [
        ("/api/extract", "extract_cards"),
        ("/api/extract-text", "enrich_text"),
        ("/api/extract-kanji", "extract_kanji"),
    ],
)
def test_claude_authentication_errors_return_401(
    path,
    service_name,
    test_client,
    sample_image_bytes,
    monkeypatch,
):
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(401, request=request)
    error = AuthenticationError("Invalid API key", response=response, body=None)
    monkeypatch.setattr(f"kioku.main.{service_name}", Mock(side_effect=error))

    if path == "/api/extract":
        files = {"file": ("test.png", io.BytesIO(sample_image_bytes), "image/png")}
        response = test_client.post(path, files=files)
    else:
        response = test_client.post(path, json={"text": "日本"})

    assert response.status_code == 401
    assert "CLAUDE_API_KEY" in response.json()["detail"]


class TestGenerateEndpoint:
    """Tests for POST /api/generate endpoint."""

    @pytest.mark.asyncio
    async def test_generate_success(
        self, test_client, sample_cards, mock_voicevox, mock_anki_connect
    ):
        """Test successful audio generation and Anki card creation."""
        payload = {
            "cards": [card.model_dump() for card in sample_cards],
            "deck_name": "TestDeck",
        }
        response = test_client.post("/api/generate", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "added" in data
        assert data["added"] == 2

    @pytest.mark.asyncio
    async def test_generate_empty_cards(
        self, test_client, mock_voicevox, mock_anki_connect
    ):
        """Test generation with empty cards list."""
        payload = {"cards": [], "deck_name": "TestDeck"}
        response = test_client.post("/api/generate", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["added"] == 0

    @pytest.mark.asyncio
    async def test_generate_default_deck_name(
        self, test_client, sample_cards, mock_voicevox, mock_anki_connect
    ):
        """Test generation uses default deck name when not provided."""
        payload = {"cards": [card.model_dump() for card in sample_cards]}
        response = test_client.post("/api/generate", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "added" in data

    @pytest.mark.asyncio
    async def test_generate_voicevox_failure(
        self, test_client, sample_cards, monkeypatch
    ):
        """Test generation handles VOICEVOX failures."""

        class MockAsyncClientFail:
            def __init__(self, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def post(self, url, **kwargs):
                import httpx

                raise httpx.ConnectError("Connection refused")

        monkeypatch.setattr("httpx.AsyncClient", MockAsyncClientFail)

        payload = {"cards": [card.model_dump() for card in sample_cards]}
        response = test_client.post("/api/generate", json=payload)

        assert response.status_code == 502
        assert "VOICEVOX request failed" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_generate_anki_connect_failure(
        self, test_client, sample_cards, mock_voicevox, monkeypatch
    ):
        """Test generation handles AnkiConnect failures."""

        def mock_urlopen_error(request):
            from unittest.mock import Mock

            mock_response = Mock()
            mock_response.read.return_value = json.dumps(
                {"result": None, "error": "Failed to connect to Anki"}
            ).encode()
            mock_response.__enter__ = Mock(return_value=mock_response)
            mock_response.__exit__ = Mock(return_value=False)
            return mock_response

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen_error)

        payload = {"cards": [card.model_dump() for card in sample_cards]}
        response = test_client.post("/api/generate", json=payload)

        assert response.status_code == 502
        assert "AnkiConnect error" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_generate_deduplicates_audio(
        self, test_client, mock_voicevox, mock_anki_connect
    ):
        """Test that generate endpoint deduplicates audio generation for same text."""
        # Create cards with duplicate japanese text
        cards = [
            {
                "japanese": "こんにちは",
                "reading": "こんにちは",
                "meaning": "Hello",
                "example_sentence": "こんにちは、元気ですか？",
                "example_translation": "Hello, how are you?",
            },
            {
                "japanese": "こんにちは",  # Duplicate
                "reading": "こんにちは",
                "meaning": "Hello",
                "example_sentence": "こんにちは、元気ですか？",  # Duplicate
                "example_translation": "Hello, how are you?",
            },
        ]

        payload = {"cards": cards}
        response = test_client.post("/api/generate", json=payload)

        assert response.status_code == 200
        # Should successfully handle duplicates without generating audio twice
