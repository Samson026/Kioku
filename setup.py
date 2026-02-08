from pathlib import Path

from setuptools import find_packages, setup


def load_requirements() -> list[str]:
    req_path = Path(__file__).parent / "requirements.txt"
    lines = req_path.read_text(encoding="utf-8").splitlines()
    return [
        line.strip()
        for line in lines
        if line.strip() and not line.strip().startswith("#")
    ]


setup(
    name="anki-card-generator",
    version="0.1.0",
    description="Generate Japanese Anki cards from images with audio",
    packages=find_packages(include=["anki_card_generator", "services", "services.*"]),
    py_modules=["main", "config", "models"],
    install_requires=load_requirements(),
    entry_points={
        "console_scripts": [
            "anki-card-generator=anki_card_generator.__main__:main",
        ]
    },
)
