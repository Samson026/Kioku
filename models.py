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
