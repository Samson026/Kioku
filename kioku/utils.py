import hashlib


def audio_filename(text: str, prefix: str) -> str:
    """Generate unique filename based on text content.

    Args:
        text: The text content to hash
        prefix: Prefix for the filename (e.g., 'word' or 'sentence')

    Returns:
        A unique filename like 'word_a1b2c3d4e5f6.mp3'
    """
    text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()[:12]
    return f"{prefix}_{text_hash}.mp3"
