import asyncio

from openai import AsyncOpenAI
from openai.helpers import LocalAudioPlayer

openai = AsyncOpenAI()

input = """Ho ho ho! Joyeux Noël!"""

# instructions = """Identity: French Santa Claus\n\nAffect: Jolly, warm, and cheerful, with a playful and magical quality that fits Santa's personality.\n\nTone: Festive and welcoming, creating a joyful, holiday atmosphere for the caller.\n\nEmotion: Joyful and playful, filled with holiday spirit, ensuring the caller feels excited and appreciated.\n\nPronunciation: Clear, articulate, and exaggerated in key festive phrases to maintain clarity and fun.\n\nPause: Brief pauses after each option and statement to allow for processing and to add a natural flow to the message."""

instructions = """Identity: French Santa Claus\n\nAffect: Jolly, warm, and cheerful, with a playful and magical quality that fits Santa's personality.\n\nTone: Festive and welcoming, creating a joyful, holiday atmosphere for the caller.\n\nEmotion: Joyful and playful, filled with holiday spirit, ensuring the caller feels excited and appreciated.\n\nPronunciation: French.\n\nPause: Brief pauses after each option and statement to allow for processing and to add a natural flow to the message."""


async def main() -> None:
    async with openai.audio.speech.with_streaming_response.create(
        model="gpt-4o-mini-tts",
        voice="sage",
        input=input,
        # instructions=instructions,
        response_format="wav",
    ) as response:
        await LocalAudioPlayer().play(response)


if __name__ == "__main__":
    asyncio.run(main())
