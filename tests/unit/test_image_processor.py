"""Unit tests for image_processor service."""

import json
from unittest.mock import Mock

import pytest

from kioku.models import CardItem
from kioku.services.image_processor import _strip_code_fences, enrich_text, extract_cards


class TestStripCodeFences:
    """Tests for _strip_code_fences utility function."""

    def test_strip_code_fences_with_json(self):
        """Test stripping code fences from JSON."""
        text = "```json\n{\"key\": \"value\"}\n```"
        result = _strip_code_fences(text)
        assert result == '{"key": "value"}'

    def test_strip_code_fences_no_fences(self):
        """Test text without code fences is unchanged."""
        text = '{"key": "value"}'
        result = _strip_code_fences(text)
        assert result == '{"key": "value"}'

    def test_strip_code_fences_with_language(self):
        """Test stripping code fences with language identifier."""
        text = "```python\nprint('hello')\n```"
        result = _strip_code_fences(text)
        assert result == "print('hello')"

    def test_strip_code_fences_whitespace(self):
        """Test stripping code fences handles whitespace."""
        text = "  ```\n  content  \n```  "
        result = _strip_code_fences(text)
        assert result == "content"


class TestEnrichText:
    """Tests for enrich_text function."""

    def test_enrich_text_success(self, mock_groq_client, monkeypatch):
        """Test successful text enrichment with Groq."""
        text = "こんにちは"
        cards = enrich_text(text)

        assert len(cards) == 1
        assert isinstance(cards[0], CardItem)
        assert cards[0].japanese == "こんにちは"
        assert cards[0].reading == "こんにちは"
        assert cards[0].meaning == "Hello"

    def test_enrich_text_empty_text(self):
        """Test enrichment with empty text raises error."""
        with pytest.raises(RuntimeError, match="No text provided"):
            enrich_text("")

    def test_enrich_text_whitespace_only(self):
        """Test enrichment with whitespace-only text raises error."""
        with pytest.raises(RuntimeError, match="No text provided"):
            enrich_text("   ")

    def test_enrich_text_missing_api_key(self, monkeypatch):
        """Test enrichment without API key raises error."""
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        with pytest.raises(RuntimeError, match="GROQ_API_KEY is required"):
            enrich_text("こんにちは")

    def test_enrich_text_invalid_json_response(self, monkeypatch):
        """Test enrichment with invalid JSON response."""
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="not valid json"))]

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_groq_class = Mock(return_value=mock_client)
        monkeypatch.setattr("kioku.services.image_processor.Groq", mock_groq_class)

        with pytest.raises(RuntimeError, match="invalid JSON"):
            enrich_text("こんにちは")

    def test_enrich_text_non_list_response(self, monkeypatch):
        """Test enrichment with non-list JSON response."""
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content='{"key": "value"}'))]

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_groq_class = Mock(return_value=mock_client)
        monkeypatch.setattr("kioku.services.image_processor.Groq", mock_groq_class)

        with pytest.raises(RuntimeError, match="non-list JSON"):
            enrich_text("こんにちは")

    def test_enrich_text_filters_duplicates(self, monkeypatch):
        """Test enrichment filters duplicate japanese entries."""
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
                                "example_sentence": "こんにちは",
                                "example_translation": "Hello",
                            },
                            {
                                "japanese": "こんにちは",  # Duplicate
                                "reading": "こんにちは",
                                "meaning": "Hello",
                                "example_sentence": "こんにちは",
                                "example_translation": "Hello",
                            },
                        ]
                    )
                )
            )
        ]

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_groq_class = Mock(return_value=mock_client)
        monkeypatch.setattr("kioku.services.image_processor.Groq", mock_groq_class)

        cards = enrich_text("こんにちは")
        assert len(cards) == 1

    def test_enrich_text_filters_missing_reading(self, monkeypatch):
        """Test enrichment filters entries without reading."""
        mock_response = Mock()
        mock_response.choices = [
            Mock(
                message=Mock(
                    content=json.dumps(
                        [
                            {
                                "japanese": "test",
                                "reading": "",  # Empty reading
                                "meaning": "Test",
                                "example_sentence": "test",
                                "example_translation": "test",
                            }
                        ]
                    )
                )
            )
        ]

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_groq_class = Mock(return_value=mock_client)
        monkeypatch.setattr("kioku.services.image_processor.Groq", mock_groq_class)

        with pytest.raises(RuntimeError, match="No valid cards extracted"):
            enrich_text("test")

    def test_enrich_text_strips_code_fences(self, monkeypatch):
        """Test enrichment strips code fences from Groq response."""
        mock_response = Mock()
        mock_response.choices = [
            Mock(
                message=Mock(
                    content='```json\n[{"japanese": "こんにちは", "reading": "こんにちは", "meaning": "Hello", "example_sentence": "こんにちは", "example_translation": "Hello"}]\n```'
                )
            )
        ]

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_groq_class = Mock(return_value=mock_client)
        monkeypatch.setattr("kioku.services.image_processor.Groq", mock_groq_class)

        cards = enrich_text("こんにちは")
        assert len(cards) == 1
        assert cards[0].japanese == "こんにちは"


class TestExtractCards:
    """Tests for extract_cards function."""

    def test_extract_cards_success(self, sample_image_bytes, mock_manga_ocr, mock_groq_client):
        """Test successful card extraction from image."""
        cards = extract_cards(sample_image_bytes, "image/png")

        assert len(cards) >= 1
        assert all(isinstance(card, CardItem) for card in cards)
        mock_manga_ocr.assert_called_once()

    def test_extract_cards_empty_ocr_result(self, sample_image_bytes, mock_manga_ocr):
        """Test extraction with empty OCR result raises error."""
        mock_manga_ocr.return_value = ""

        with pytest.raises(RuntimeError, match="Manga OCR returned no text"):
            extract_cards(sample_image_bytes, "image/png")

    def test_extract_cards_whitespace_ocr_result(self, sample_image_bytes, mock_manga_ocr):
        """Test extraction with whitespace-only OCR result raises error."""
        mock_manga_ocr.return_value = "   "

        with pytest.raises(RuntimeError, match="Manga OCR returned no text"):
            extract_cards(sample_image_bytes, "image/png")
