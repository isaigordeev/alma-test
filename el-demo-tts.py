import base64
import os
import json
import asyncio
import subprocess
import time
import openai
import websockets
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
VOICE_ID = "FvmvwvObRqIHojkEGh5N"  # Change to your preferred voice
MODEL_ID = "eleven_flash_v2_5"
# MODEL_ID = "eleven_multilingual_v2"
# MODEL_ID = "eleven_v3"
OUTPUT_FORMAT = "mp3_44100_128"

WEBSOCKET_URI = f"wss://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}/multi-stream-input?model_id={MODEL_ID}&output_format={OUTPUT_FORMAT}"

# ffplay setup for MP3 streaming
ffplay = subprocess.Popen(
    ["ffplay", "-autoexit", "-nodisp", "-f", "mp3", "-"],
    stdin=subprocess.PIPE,
    stderr=subprocess.DEVNULL,
)

# Voice settings to add some emotion
EMOTIONAL_SETTINGS = {
    "stability": 0.75,  # 0.0–1.0, how consistent voice tone is
    "similarity_boost": 0.85,  # 0.0–1.0, affects expressiveness
}


async def send_text_in_context(
    websocket, text, context_id, voice_settings=None
):
    message = {"text": text, "context_id": context_id}
    if voice_settings:
        message["voice_settings"] = voice_settings
    await websocket.send(json.dumps(message))


async def continue_context(websocket, text, context_id):
    await websocket.send(json.dumps({"text": text, "context_id": context_id}))


async def flush_context(websocket, context_id):
    await websocket.send(json.dumps({"context_id": context_id, "flush": True}))


async def handle_interruption(
    websocket, old_context_id, new_context_id, new_response
):
    await websocket.send(
        json.dumps({"context_id": old_context_id, "close_context": True})
    )
    await send_text_in_context(
        websocket,
        new_response,
        new_context_id,
        voice_settings=EMOTIONAL_SETTINGS,
    )


async def end_conversation(websocket):
    await websocket.send(json.dumps({"close_socket": True}))


async def receive_messages(websocket, start):
    first_audio_time = None
    try:
        async for message in websocket:
            data = json.loads(message)
            context_id = data.get("contextId", "default")
            audio_b64 = data.get("audio")
            if audio_b64:
                if first_audio_time is None:
                    first_audio_time = time.perf_counter()
                    ttfa = first_audio_time - start
                    print(
                        f"🎧 Time to first audio chunk (TTFA): {ttfa:.3f} seconds"
                    )
                audio_bytes = base64.b64decode(audio_b64)
                ffplay.stdin.write(audio_bytes)
                ffplay.stdin.flush()
                print(f"Lecture audio pour le contexte '{context_id}'")

            if data.get("is_final"):
                print(f"Contexte '{context_id}' terminé")
                ffplay.stdin.flush()
    except (websockets.exceptions.ConnectionClosed, asyncio.CancelledError):
        print("Arrêt de la réception des messages")


client = openai.OpenAI()


client = Groq()


async def send_streamed_response(websocket, prompt, context_id="default"):
    """
    Stream LLM text from OpenAI and send it incrementally over websocket.
    """
    # OpenAI streaming response
    stream = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        stream=True,
    )

    buffer = ""
    for event in stream:
        delta_text = event.choices[0].delta.content
        if delta_text:
            # if event.type == "content.delta":
            # delta = event
            # if delta:
            #     buffer += delta
            #     print(delta)
            # Send partial content over WebSocket as it arrives
            print(delta_text)
            await websocket.send(
                json.dumps(
                    {
                        "context_id": context_id,
                        "text": delta_text,
                        # "partial": True,
                        "voice_settings": EMOTIONAL_SETTINGS,
                    }
                )
            )
    await websocket.send(
        json.dumps(
            {
                "context_id": context_id,
                "close_context": True,
            }
        )
    )


global start


async def conversation_agent_demo():
    async with websockets.connect(
        WEBSOCKET_URI,
        max_size=16 * 1024 * 1024,
        additional_headers={"xi-api-key": ELEVENLABS_API_KEY},
    ) as websocket:
        start_time = time.perf_counter()
        receive_task = asyncio.create_task(
            receive_messages(websocket, start_time)
        )

        await send_streamed_response(
            websocket,
            "Bonjour ! Racconte moi une phrase courte drôle et hahaha à la fin aussi!",
            # "Bonjour ! Racconte moi une histoire de 15 phrases drôle!",
            context_id="greeting",
        )
        # # Premier message en français, chaleureux et amical
        # await send_text_in_context(
        #     websocket,
        #     "Bonjour ! Je suis votre assistant virtuel. Je peux vous aider avec une large gamme de sujets. Sur quoi voulez-vous en savoir plus aujourd'hui ?",
        #     "greeting",
        #     voice_settings=EMOTIONAL_SETTINGS,
        # )

        # await asyncio.sleep(2)

        # # Simulate user interruption
        # print("UTILISATEUR INTERRUPTION : 'Peux-tu me parler de la météo ?'")
        # await handle_interruption(
        #     websocket,
        #     "greeting",
        #     "weather_response",
        #     "Bien sûr ! Actuellement, il fait 22 degrés et le soleil brille. Il y a juste une légère chance de pluie cet après-midi.",
        # )

        # await continue_context(
        #     websocket,
        #     " Si vous prévoyez de sortir, vous pourriez prendre une petite veste, juste au cas où.",
        #     "weather_response",
        # )

        # await flush_context(websocket, "weather_response")
        # await asyncio.sleep(3)

        # print("UTILISATEUR : 'Et demain ?'")
        # await send_text_in_context(
        #     websocket,
        #     "Demain, les températures devraient être autour de 24 degrés avec un ciel partiellement nuageux. Une belle journée en perspective !",
        #     "tomorrow_weather",
        #     voice_settings=EMOTIONAL_SETTINGS,
        # )

        # await flush_context(websocket, "tomorrow_weather")
        # await websocket.send(
        #     json.dumps({"context_id": "tomorrow_weather", "close_context": True})
        # )

        # Send final message to indicate end of stream
        await websocket.send(json.dumps({"close_socket": True}))
        await asyncio.sleep(4)
        await end_conversation(websocket)

        ffplay.stdin.close()
        ffplay.wait()

        receive_task.cancel()
        try:
            await receive_task
        except asyncio.CancelledError:
            pass


if __name__ == "__main__":
    asyncio.run(conversation_agent_demo())
