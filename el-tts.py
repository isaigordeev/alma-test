from io import BytesIO
import queue
import subprocess
import time
from elevenlabs import ElevenLabs
import simpleaudio as sa
import threading

client = ElevenLabs(
    base_url="https://api.elevenlabs.io",
)


# Start ffplay to read mp3 data from stdin and play immediately
ffplay = subprocess.Popen(
    ["ffplay", "-autoexit", "-nodisp", "-"],
    stdin=subprocess.PIPE,
    stderr=subprocess.DEVNULL,
)

# Stream ElevenLabs audio directly into ffplay
start_time = time.time()  # Start timer

first_chunk_time = None

# Stream audio from ElevenLabs
for chunk in client.text_to_speech.stream(
    voice_id="O31r762Gb3WFygrEOGh0",
    output_format="mp3_44100_128",
    text="[whispers] Je suis désolé, je n'ai pas compris votre demande. Pouvez-vous reformuler s'il vous plaît ?",
    # model_id="eleven_turbo_v2_5",
    # model_id="eleven_flash_v2_5",
    # model_id="eleven_v3",
    voice_settings={
        "stability": 0.5,  # 0.0–1.0, how consistent voice tone is
        "similarity_boost": 0.3,  # 0.0–1.0, affects expressiveness
        "use_speaker_boost": True,
    },
):
    if chunk:
        if first_chunk_time is None:
            first_chunk_time = time.time()  # Mark first audio chunk
        print(chunk)
        ffplay.stdin.write(chunk)

ffplay.stdin.close()
ffplay.wait()

if first_chunk_time:
    print(
        f"Time to first audio chunk: {first_chunk_time - start_time:.3f} seconds"
    )
else:
    print("No audio chunks received.")
