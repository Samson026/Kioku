from pydantic import BaseModel


class CardItem(BaseModel):
    japanese: str
    reading: str
    meaning: str
    example_sentence: str
    example_translation: str


class ExtractionResult(BaseModel):
    cards: list[CardItem]


class GenerateRequest(BaseModel):
    cards: list[CardItem]
    deck_name: str = "ankiGen"
    sentence_audio_b64: str | None = None


class TextExtractionRequest(BaseModel):
    text: str


class KanjiCard(BaseModel):
    kanji: str
    onyomi: str
    kunyomi: str
    meaning: str
    example_word: str
    example_word_reading: str


class KanjiExtractionResult(BaseModel):
    cards: list[KanjiCard]


class KanjiGenerateRequest(BaseModel):
    cards: list[KanjiCard]
    deck_name: str = "ankiGen"
