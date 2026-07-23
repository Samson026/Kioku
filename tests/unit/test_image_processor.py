"""Unit tests for image_processor service."""

import json
from unittest.mock import Mock

import pytest

from kioku.constants import CLAUDE_MODEL
from kioku.models import CardItem, KanjiCard
from kioku.services.image_processor import (
    _strip_code_fences,
    enrich_text,
    extract_cards,
    extract_kanji,
)


def _mock_claude_response(monkeypatch, content: str) -> Mock:
    mock_response = Mock(content=[Mock(type="text", text=content)])
    mock_client = Mock()
    mock_client.messages.create.return_value = mock_response
    monkeypatch.setattr(
        "kioku.services.image_processor.Anthropic",
        Mock(return_value=mock_client),
    )
    return mock_client


class TestStripCodeFences:
    """Tests for _strip_code_fences utility function."""

    def test_strip_code_fences_with_json(self):
        text = '```json\n{"key": "value"}\n```'
        assert _strip_code_fences(text) == '{"key": "value"}'

    def test_strip_code_fences_no_fences(self):
        text = '{"key": "value"}'
        assert _strip_code_fences(text) == '{"key": "value"}'

    def test_strip_code_fences_with_language(self):
        text = "```python\nprint('hello')\n```"
        assert _strip_code_fences(text) == "print('hello')"

    def test_strip_code_fences_whitespace(self):
        text = "  ```\n  content  \n```  "
        assert _strip_code_fences(text) == "content"


class TestEnrichText:
    """Tests for enrich_text."""

    def test_enrich_text_success(self, mock_claude_client):
        cards = enrich_text("こんにちは")

        assert len(cards) == 1
        assert isinstance(cards[0], CardItem)
        assert cards[0].japanese == "こんにちは"
        assert cards[0].reading == "こんにちは"
        assert cards[0].meaning == "Hello"
        mock_claude_client.messages.create.assert_called_once()

    def test_enrich_text_empty_text(self):
        with pytest.raises(RuntimeError, match="No text provided"):
            enrich_text("")

    def test_enrich_text_whitespace_only(self):
        with pytest.raises(RuntimeError, match="No text provided"):
            enrich_text("   ")

    def test_enrich_text_missing_api_key(self, monkeypatch):
        monkeypatch.delenv("CLAUDE_API_KEY", raising=False)
        with pytest.raises(RuntimeError, match="CLAUDE_API_KEY is required"):
            enrich_text("こんにちは")

    def test_enrich_text_invalid_json_response(self, monkeypatch):
        _mock_claude_response(monkeypatch, "not valid json")

        with pytest.raises(RuntimeError, match="Claude returned invalid JSON"):
            enrich_text("こんにちは")

    def test_enrich_text_non_list_response(self, monkeypatch):
        _mock_claude_response(monkeypatch, '{"key": "value"}')

        with pytest.raises(RuntimeError, match="Claude returned non-list JSON"):
            enrich_text("こんにちは")

    def test_enrich_text_filters_duplicates(self, monkeypatch):
        content = json.dumps(
            [
                {
                    "japanese": "こんにちは",
                    "reading": "こんにちは",
                    "meaning": "Hello",
                    "example_sentence": "こんにちは",
                    "example_translation": "Hello",
                },
                {
                    "japanese": "こんにちは",
                    "reading": "こんにちは",
                    "meaning": "Hello",
                    "example_sentence": "こんにちは",
                    "example_translation": "Hello",
                },
            ]
        )
        _mock_claude_response(monkeypatch, content)

        assert len(enrich_text("こんにちは")) == 1

    def test_enrich_text_filters_missing_reading(self, monkeypatch):
        content = json.dumps(
            [
                {
                    "japanese": "test",
                    "reading": "",
                    "meaning": "Test",
                    "example_sentence": "test",
                    "example_translation": "test",
                }
            ]
        )
        _mock_claude_response(monkeypatch, content)

        with pytest.raises(RuntimeError, match="No valid cards extracted"):
            enrich_text("test")

    def test_enrich_text_strips_code_fences(self, monkeypatch):
        content = (
            "```json\n"
            '[{"japanese":"こんにちは","reading":"こんにちは",'
            '"meaning":"Hello","example_sentence":"こんにちは",'
            '"example_translation":"Hello"}]\n'
            "```"
        )
        _mock_claude_response(monkeypatch, content)

        cards = enrich_text("こんにちは")
        assert len(cards) == 1
        assert cards[0].japanese == "こんにちは"


class TestExtractKanji:
    """Tests for extract_kanji."""

    @staticmethod
    def _kanji_content() -> str:
        return json.dumps(
            [
                {
                    "kanji": "日",
                    "onyomi": "ニチ",
                    "kunyomi": "ひ",
                    "meaning": "day; sun",
                    "example_word": "日本",
                    "example_word_reading": "にほん",
                },
                {
                    "kanji": "本",
                    "onyomi": "ホン",
                    "kunyomi": "もと",
                    "meaning": "book; origin",
                    "example_word": "本屋",
                    "example_word_reading": "ほんや",
                },
            ]
        )

    def test_extract_kanji_success(self, monkeypatch):
        mock_client = _mock_claude_response(monkeypatch, self._kanji_content())

        cards = extract_kanji("日本")

        assert [card.kanji for card in cards] == ["日", "本"]
        assert all(isinstance(card, KanjiCard) for card in cards)
        assert cards[0].example_word_reading == "にほん"
        mock_client.messages.create.assert_called_once()
        request = mock_client.messages.create.call_args.kwargs
        assert request["model"] == CLAUDE_MODEL
        assert "structured study entries" in request["system"]
        assert request["messages"] == [{"role": "user", "content": "日、本"}]
        assert request["max_tokens"] == 1024

    def test_extract_kanji_missing_api_key(self, monkeypatch):
        monkeypatch.delenv("CLAUDE_API_KEY", raising=False)

        with pytest.raises(RuntimeError, match="CLAUDE_API_KEY is required"):
            extract_kanji("日本")

    def test_extract_kanji_without_kanji_skips_claude(self, monkeypatch):
        mock_anthropic = Mock()
        monkeypatch.setattr(
            "kioku.services.image_processor.Anthropic",
            mock_anthropic,
        )

        assert extract_kanji("ひらがな") == []
        mock_anthropic.assert_not_called()

    def test_extract_kanji_invalid_json_response(self, monkeypatch):
        _mock_claude_response(monkeypatch, "not valid json")

        with pytest.raises(RuntimeError, match="Claude returned invalid JSON"):
            extract_kanji("日本")

    def test_extract_kanji_non_list_response(self, monkeypatch):
        _mock_claude_response(monkeypatch, '{"kanji": "日"}')

        with pytest.raises(RuntimeError, match="Claude returned non-list JSON"):
            extract_kanji("日本")

    def test_extract_kanji_filters_duplicates(self, monkeypatch):
        entries = json.loads(self._kanji_content())
        entries.append(entries[0])
        _mock_claude_response(monkeypatch, json.dumps(entries))

        cards = extract_kanji("日本日")
        assert [card.kanji for card in cards] == ["日", "本"]


class TestExtractCards:
    """Tests for extract_cards."""

    def test_extract_cards_success(
        self, sample_image_bytes, mock_manga_ocr, mock_claude_client
    ):
        cards = extract_cards(sample_image_bytes, "image/png")

        assert len(cards) >= 1
        assert all(isinstance(card, CardItem) for card in cards)
        mock_manga_ocr.assert_called_once()

    def test_extract_cards_empty_ocr_result(self, sample_image_bytes, mock_manga_ocr):
        mock_manga_ocr.return_value = ""

        with pytest.raises(RuntimeError, match="Manga OCR returned no text"):
            extract_cards(sample_image_bytes, "image/png")

    def test_extract_cards_whitespace_ocr_result(
        self, sample_image_bytes, mock_manga_ocr
    ):
        mock_manga_ocr.return_value = "   "

        with pytest.raises(RuntimeError, match="Manga OCR returned no text"):
            extract_cards(sample_image_bytes, "image/png")
