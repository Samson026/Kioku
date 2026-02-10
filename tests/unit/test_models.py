"""Unit tests for Pydantic models."""

import pytest
from pydantic import ValidationError

from kioku.models import CardItem, ExtractionResult, GenerateRequest, TextExtractionRequest


class TestCardItem:
    """Tests for CardItem model."""

    def test_valid_card_item(self):
        """Test creating a valid CardItem."""
        card = CardItem(
            japanese="こんにちは",
            reading="こんにちは",
            meaning="Hello",
            example_sentence="こんにちは、元気ですか？",
            example_translation="Hello, how are you?",
        )
        assert card.japanese == "こんにちは"
        assert card.reading == "こんにちは"
        assert card.meaning == "Hello"
        assert card.example_sentence == "こんにちは、元気ですか？"
        assert card.example_translation == "Hello, how are you?"

    def test_card_item_missing_required_fields(self):
        """Test that missing required fields raise ValidationError."""
        with pytest.raises(ValidationError):
            CardItem(japanese="test")

    def test_card_item_all_fields_required(self):
        """Test that all fields are required."""
        with pytest.raises(ValidationError):
            CardItem(
                japanese="こんにちは",
                reading="こんにちは",
                meaning="Hello",
                example_sentence="こんにちは、元気ですか？",
                # Missing example_translation
            )


class TestExtractionResult:
    """Tests for ExtractionResult model."""

    def test_valid_extraction_result(self, sample_cards):
        """Test creating a valid ExtractionResult."""
        result = ExtractionResult(cards=sample_cards)
        assert len(result.cards) == 2
        assert all(isinstance(card, CardItem) for card in result.cards)

    def test_extraction_result_empty_list(self):
        """Test ExtractionResult with empty card list."""
        result = ExtractionResult(cards=[])
        assert result.cards == []


class TestGenerateRequest:
    """Tests for GenerateRequest model."""

    def test_generate_request_with_default_deck(self, sample_cards):
        """Test GenerateRequest uses default deck name."""
        request = GenerateRequest(cards=sample_cards)
        assert request.deck_name == "ankiGen"
        assert len(request.cards) == 2

    def test_generate_request_with_custom_deck(self, sample_cards):
        """Test GenerateRequest with custom deck name."""
        request = GenerateRequest(cards=sample_cards, deck_name="CustomDeck")
        assert request.deck_name == "CustomDeck"

    def test_generate_request_empty_cards(self):
        """Test GenerateRequest with empty cards list."""
        request = GenerateRequest(cards=[])
        assert request.cards == []


class TestTextExtractionRequest:
    """Tests for TextExtractionRequest model."""

    def test_valid_text_extraction_request(self):
        """Test creating a valid TextExtractionRequest."""
        request = TextExtractionRequest(text="こんにちは")
        assert request.text == "こんにちは"

    def test_text_extraction_request_missing_text(self):
        """Test that missing text field raises ValidationError."""
        with pytest.raises(ValidationError):
            TextExtractionRequest()
