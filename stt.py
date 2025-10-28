import io
import time
import pyaudio
from openai import OpenAI


def byteplay(bytestream):
    pya = pyaudio.PyAudio()
    stream = pya.open(
        format=pya.get_format_from_width(width=2),
        channels=1,
        rate=24000,
        output=True,
    )
    stream.write(bytestream)
    stream.stop_stream()
    stream.close()
    pya.terminate()


client = OpenAI()

instructions = """Identity: French Santa Claus

Affect: Jolly, warm, and cheerful, with a playful and magical quality that fits Santa's personality.

Tone: Festive and welcoming, creating a joyful, holiday atmosphere for the caller.

Emotion: Joyful and playful, filled with holiday spirit, ensuring the caller feels excited and appreciated.

Pronunciation: French.

Pause: Brief pauses after each option and statement to allow for processing and to add a natural flow to the message.
"""

start_total = time.perf_counter()
with client.audio.speech.with_streaming_response.create(
    model="tts-1",
    voice="nova",
    input="ho ho ho bonjour je suis super contente",
    instructions=instructions,
    response_format="wav",
) as response:
    buffer = io.BytesIO()

    # --- measure latency ---
    first_chunk_time = None
    start_request = time.perf_counter()
    print(f"  • Time to first: {start_request - start_total:.2f} seconds")
    for chunk in response.iter_bytes():
        buffer.write(chunk)

    end_stream = time.perf_counter()

    buffer.seek(0)

    start_play = time.perf_counter()
    byteplay(buffer.getvalue())
    end_play = time.perf_counter()

end_total = time.perf_counter()

# --- summary ---
print(f"\n⏱️  Timing Summary:")
print(f"  • Stream duration: {end_stream - start_request:.2f} seconds")
print(f"  • Playback time: {end_play - start_play:.2f} seconds")
print(f"  • Total runtime: {end_total - start_total:.2f} seconds")
