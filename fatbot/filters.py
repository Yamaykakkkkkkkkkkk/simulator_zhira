from aiogram.filters import Filter
from aiogram.types import Message


class TextEquals(Filter):
    def __init__(self, *variants: str):
        self.variants = {v.lower() for v in variants}

    async def __call__(self, message: Message) -> bool:
        return bool(message.text) and message.text.strip().lower() in self.variants
