import asyncio
from collections import deque
import openai
from contextlib import asynccontextmanager
import json
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCDataChannel
from fastapi.middleware.cors import CORSMiddleware
import numpy as np
import uvicorn
import time

import sounddevice as sd

import numpy as np
from scipy.signal import resample_poly

import azure.cognitiveservices.speech as speechsdk
from azure.cognitiveservices.speech import ResultFuture

TARGET_SR = 48000

from groq import Groq

client = Groq()


def float32_to_pcm16_resampled(float32_bytes, input_sr, target_sr=TARGET_SR):
    """
    Convert raw float32 audio bytes (mono) into PCM16 at target sample rate.
    """
    # Interpret as float32
    audio = np.frombuffer(float32_bytes, dtype=np.float32)

    # Handle silence or NaN
    if audio.size == 0:
        return b""
    audio = np.nan_to_num(audio)

    # If sample rates differ, resample
    if input_sr != target_sr:
        audio = resample_poly(audio, target_sr, input_sr)

    # Clip to [-1,1]
    audio = np.clip(audio, -1.0, 1.0)

    # Convert to PCM16
    pcm16 = (audio * 32767).astype(np.int16)
    return pcm16.tobytes()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup code (optional)
    print("Server starting...")
    yield
    # Shutdown code
    print("Server shutting down...")
    for pc in pcs:
        await pc.close()
        recognizer, push_stream = recognizers[pc]
        push_stream.close()
        recognizer.stop_continuous_recognition()


import threading
import queue

# Thread-safe queue for TTS results
result_queue = queue.Queue()
stop_flag = threading.Event()


def tts_worker():
    """Thread that waits on TTS tasks from the queue"""
    while True:
        tts_task: ResultFuture = (
            result_queue.get()
        )  # blocks until a task is available
        print(f"TTS worker {tts_task}")
        if tts_task is None:
            break  # sentinel to exit thread

        stop_flag.clear()
        try:
            # Wait for TTS result in a thread, can be preempted
            while not stop_flag.is_set():
                result = tts_task.get()
                if (
                    result.reason
                    == speechsdk.ResultReason.SynthesizingAudioCompleted
                ):
                    print("[TTS speech] is done")
                    break
        except Exception as e:
            print("[TTS worker error]", e)
        finally:
            print("[TTS worker] done or stopped")


# Launch TTS worker thread
threading.Thread(target=tts_worker, daemon=True).start()

app = FastAPI(lifespan=lifespan)

# Allow all origins (for development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*"
    ],  # You can set specific origins like ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pcs = set()

# -----------------------------
# Azure Speech SDK Setup
# -----------------------------
# Dictionary to store recognizer per peer
recognizers = {}

BUFFER_SIZE = 16000  # 0.5 second at 16kHz, PCM16

# per channel buffer
chunk_buffers = {}
input_sample_rate = 48000

rec_endpoint = "https://swedencentral.api.cognitive.microsoft.com/"
endpoint = "wss://swedencentral.tts.speech.microsoft.com/cognitiveservices/websocket/v2"
speech_config = speechsdk.SpeechConfig(
    subscription=speech_key, endpoint=rec_endpoint
)
stream_format = speechsdk.audio.AudioStreamFormat(
    samples_per_second=TARGET_SR, bits_per_sample=16, channels=1
)

speech_config.speech_recognition_language = "fr-FR"
# speech_config.speech_recognition_language = "ru-RU"
# speech_config.speech_recognition_language = "en-US"

speech_syn_config = speechsdk.SpeechConfig(
    subscription=speech_key, endpoint=endpoint
)
# speech_syn_config.speech_synthesis_language = "ru-RU"
speech_syn_config.speech_synthesis_language = "fr-FR"
# speech_syn_config.speech_synthesis_language = "en-US"

speech_syn_config.set_speech_synthesis_output_format(
    speechsdk.SpeechSynthesisOutputFormat.Raw48Khz16BitMonoPcm
)
speech_syn_config.speech_synthesis_voice_name = (
    "fr-FR-VivienneMultilingualNeural"
)
# speech_syn_config.speech_synthesis_voice_name = "fr-FR-EloiseNeural"
# speech_syn_config.speech_synthesis_voice_name = "fr-FR-Vivienne:DragonHDLatestNeural"
# speech_syn_config.speech_synthesis_voice_name = "ru-RU-SvetlanaNeural"
# speech_syn_config.speech_synthesis_voice_name = "en-US-Ava:MultilingualNeural"


synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_syn_config)
connection = speechsdk.Connection.from_speech_synthesizer(synthesizer)
connection.open(True)  # True = block until connection established

# speech_config.set_property(
#     speechsdk.PropertyId.SpeechSynthesis_FrameTimeoutInterval, "100000000"
# )
# speech_config.set_property(
#     speechsdk.PropertyId.SpeechSynthesis_RtfTimeoutThreshold, "10"
# )

# client = openai.OpenAI(
# )

recognized_text_queue = asyncio.Queue()
tts_audio_queue = asyncio.Queue()

conversation = [
    {
        "role": "system",
        "content": "Tu es un assistant vocal utile nommé Alma. Tu disposes de 2 outils : créer un chat et envoyer un message. Réponds en français et de manière très brève mais précise, car je veux réduire la latence. L’utilisateur peut poser des questions concernant l’application, par exemple aller sur une page ou envoyer un message.",
    }
]


# conversation = [
#     {
#         "role": "system",
#         "content": "Ты — полезный голосовой ассистент по имени Alma. У тебя есть 2 инструмента: создать чат и отправить сообщение. Отвечай по-русски и очень кратко, но конкретно, потому что я хочу уменьшить задержку. Пользователь может задавать какие то вопросы по приложению, например перейти на страницу или отправить сообщение. Если ответ может быть кратким то ты можешь просто на данную просьбу отправить 3 тюльпана.",
#     }
# ]


loop = asyncio.get_event_loop()
print("loop", loop)

# Create Azure recognizer for this peer
push_stream = speechsdk.audio.PushAudioInputStream(stream_format=stream_format)
audio_config = speechsdk.audio.AudioConfig(stream=push_stream)
recognizer = speechsdk.SpeechRecognizer(
    speech_config=speech_config, audio_config=audio_config
)

task_pool = deque([])
result_pool = deque([])


@recognizer.recognizing.connect
def on_recognizing(evt):
    text = evt.result.text
    if text:
        print(f"[Recognizing Text] {text}")
        loop.call_soon_threadsafe(recognized_text_queue.put_nowait, text)

    # print(result_queue)
    # print(result_queue.empty())
    # if not result_queue.empty():
    print("[LOG] stopping current TTS")
    stop_flag.set()
    synthesizer.stop_speaking_async()


@recognizer.recognized.connect
def on_recognized(evt):
    text = evt.result.text
    global_start_time = time.time()
    if text:
        print(f"[Recognized Text] {text}")

        # create request with TextStream input type
        tts_request = speechsdk.SpeechSynthesisRequest(
            input_type=speechsdk.SpeechSynthesisRequestInputType.TextStream
        )
        tts_task = synthesizer.speak_async(tts_request)
        conversation.append({"role": "user", "content": text})

        try:
            start_time = time.time()
            stream = client.chat.completions.create(
                model="gpt-4o-mini", messages=conversation, stream=True
            )

            flag = False
            print(stream)
            buffer = ""
            for event in stream:
                # print(event)
                if not flag:
                    print("Starting...")
                    print("Time to first token: ", time.time() - start_time)
                    flag = True
                end_time = time.time()
                print("TTFT " + str(end_time - start_time), "s")
                delta_text = event.choices[0].delta.content
                if delta_text:
                    buffer += delta_text
                    tts_request.input_stream.write(delta_text)
                    print("delta_text", delta_text)
            print("[GPT END]", end="\n")

            task_pool.append("curr_task")
            tts_request.input_stream.close()

            result_queue.put(tts_task)

            conversation.append({"role": "assistant", "content": buffer})
            print(conversation)
            # wait all tts audio bytes return
            start_voice_time = time.time()
            # result = tts_task.get()
            # print("result", result)
            print("result time ", time.time() - start_voice_time)
            print(f"overrall taken: {time.time() - global_start_time}")
        except Exception as e:
            print(e)

        # if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        # print("Speech synthesized to speaker for text [{}]".format(text))


recognizer.canceled.connect(
    lambda evt: print(
        f"[Canceled] {evt, evt.reason if evt.result.text else 'No speech'}",
        flush=True,
    )
)
recognizer.start_continuous_recognition()
print("[LOG] Azure recognizer started.")


# -----------------------------
# WebRTC Offer Handler
# -----------------------------
@app.post("/offer")
async def offer(request: Request):
    params = await request.json()
    print(params)
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pcs.add(pc)
    print("[LOG] RTCPeerConnection created.")

    @pc.on("datachannel")
    def on_datachannel(channel: RTCDataChannel):
        print(
            f"[LOG] Data channel received: {channel.label}, readyState: {channel.readyState} {channel}"
        )

        @channel.on("open")
        def on_open():
            print(f"[LOG] Data channel {channel.label} is open.")

        @channel.on("close")
        def on_close():
            print(f"[LOG] Data channel {channel.label} closed.")

        if channel.label == "audio":

            @channel.on("message")
            def on_message(message):
                # Log message type and length
                if isinstance(message, bytes):
                    if channel not in chunk_buffers:
                        chunk_buffers[channel] = bytearray()
                    if len(message) % 2 != 0:
                        print(
                            f"[ERROR] Received chunk length {len(message)} is not divisible by 2 (invalid PCM16)"
                        )
                    else:
                        # Optional: check first few samples
                        import struct

                        first_samples = struct.unpack(
                            "<5h", message[:10]
                        )  # little-endian 16-bit
                        # print(
                        #     f"[LOG] Checked {len(message)} bytes, first 5 samples: {first_samples}"
                        # )

                    # print(
                    #     f"[LOG] Received audio chunk: {len(message)} bytes, first 10 bytes: {list(message[:10])}"
                    # )
                    # print("chuck", (message[:5]))
                    # print(f"[WARN] Received bytes message: {len(message)}")
                    pcm_bytes = float32_to_pcm16_resampled(
                        message, input_sr=input_sample_rate
                    )
                    push_stream.write(pcm_bytes)
                else:
                    print(f"[WARN] Received non-bytes message: {message}")

        elif channel.label == "text-out":
            # Function to push recognized text to client
            print(f"[WARN] Received LLM message: {recognized_text_queue}")

            async def push_text_loop():
                while True:
                    text = await recognized_text_queue.get()
                    print(
                        f"[LOG] Received LLM message: {recognized_text_queue}"
                    )
                    if text is None:  # end signal
                        break
                    if channel.readyState == "open":
                        channel.send(text)

            # Get the current running event loop
            loop = asyncio.get_event_loop()
            loop.create_task(push_text_loop())

        # elif channel.label == "audio-out":
        #     # Function to push raw TTS chunks to client
        #     async def push_audio():
        #         while True:
        #             audio_chunk = (
        #                 await tts_audio_queue.get()
        #             )  # asyncio.Queue for raw TTS chunks
        #             if audio_chunk is None:
        #                 break
        #             channel.send(audio_chunk)

        #     asyncio.create_task(push_audio())

    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    print("[LOG] SDP answer created and set.")

    return {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}


if __name__ == "__main__":
    print("[LOG] Starting FastAPI server on http://0.0.0.0:8080")
    uvicorn.run(
        "stream_voice_clean:app", host="0.0.0.0", port=8080, reload=True
    )
