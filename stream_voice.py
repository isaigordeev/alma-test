import asyncio
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

TARGET_SR = 48000


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

speech_syn_config = speechsdk.SpeechConfig(
    subscription=speech_key, endpoint=endpoint
)
speech_syn_config.speech_synthesis_language = "fr-FR"

speech_syn_config.set_speech_synthesis_output_format(
    speechsdk.SpeechSynthesisOutputFormat.Raw16Khz16BitMonoPcm
)
speech_syn_config.speech_synthesis_voice_name = "fr-FR-DeniseNeural"


def handle_synth(start_voice_time):
    print(f"[audio] {time.time() - start_voice_time:.3f}s")


class RealTimePushCallback(speechsdk.audio.PushAudioOutputStreamCallback):
    def __init__(self):
        super().__init__()
        self.audio_data = bytearray()

    def write(self, audio_buffer: memoryview) -> int:
        # Called as soon as a chunk of audio is ready
        self.audio_data += audio_buffer
        print(f"Received {audio_buffer.nbytes} bytes of audio")
        # Here you could send audio_buffer to a speaker or data channel
        audio_array = np.frombuffer(audio_buffer, dtype=np.int16)
        sd.play(audio_array, 16000, blocking=False)
        return audio_buffer.nbytes

    def close(self) -> None:
        print("Audio stream closed")


stream_callback = RealTimePushCallback()
push_stream = speechsdk.audio.PushAudioOutputStream(stream_callback)
audio_sys_config = speechsdk.audio.AudioOutputConfig(stream=push_stream)
audio_sys_config = None

synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_syn_config)
connection = speechsdk.Connection.from_speech_synthesizer(synthesizer)
connection.open(True)  # True = block until connection established

# speech_config.set_property(
#     speechsdk.PropertyId.SpeechSynthesis_FrameTimeoutInterval, "100000000"
# )
# speech_config.set_property(
#     speechsdk.PropertyId.SpeechSynthesis_RtfTimeoutThreshold, "10"
# )

client = openai.OpenAI()


# -----------------------------
# WebRTC Offer Handler
# -----------------------------
@app.post("/offer")
async def offer(request: Request):
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pcs.add(pc)
    print("[LOG] RTCPeerConnection created.")

    # Create Azure recognizer for this peer
    push_stream = speechsdk.audio.PushAudioInputStream(
        stream_format=stream_format
    )
    audio_config = speechsdk.audio.AudioConfig(stream=push_stream)
    recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config, audio_config=audio_config
    )
    recognizers[pc] = (recognizer, push_stream)

    # recognizer.recognizing.connect(
    #     lambda evt: print(
    #         f"[Recognizing] {evt, evt.result.text if evt.result.text else 'No speech'}",
    #         flush=True,
    #     )
    # )

    @recognizer.recognizing.connect
    def on_recognizing(evt):
        text = evt.result.text
        if text:
            print(f"[Recognizing Text] {text}")

    @recognizer.recognized.connect
    def on_recognized(evt):
        text = evt.result.text
        conversation = [
            {
                "role": "system",
                "content": "You are a helpful voice assistant called Alma. You have 2 tools to call: create chat and send message. Respond in french and very briefly but concretely because I want to reduce latence.",
            }
        ]
        global_start_time = time.time()
        if text:
            print(f"[Recognized Text] {text}")
            # TTS for recognized chunk

            # create request with TextStream input type
            tts_request = speechsdk.SpeechSynthesisRequest(
                input_type=speechsdk.SpeechSynthesisRequestInputType.TextStream
            )
            # start_voice_time = time.time()

            # def handle_synth(evt, start_voice_time=start_voice_time):
            #     print(f"[audio] {time.time() - start_voice_time:.3f}s")

            # synthesizer.synthesizing.connect(handle_synth)

            tts_task = synthesizer.speak_async(tts_request)
            conversation.append({"role": "user", "content": text})

            try:
                start_time = time.time()
                stream = client.chat.completions.create(
                    model="gpt-4o-mini", messages=conversation, stream=True
                )

                print(stream)
                buffer = ""
                for event in stream:
                    # print(event)
                    end_time = time.time()
                    print("TTFT " + str(end_time - start_time), "s")
                    delta_text = event.choices[0].delta.content
                    if delta_text:
                        buffer += delta_text
                        tts_request.input_stream.write(delta_text)
                        print("delta_text", delta_text)
                print("[GPT END]", end="\n")
                tts_request.input_stream.close()

                # wait all tts audio bytes return
                start_voice_time = time.time()
                result = tts_task.get()
                print("result", result)
                print("result time ", time.time() - start_voice_time)
                print(f"overrall taken: {time.time() - global_start_time}")
                # response = client.chat.completions.create(
                #     model="gpt-4o-mini", messages=conversation
                # )
                # print(response.choices[0].message.content)
            except Exception as e:
                print(e)

            if (
                result.reason
                == speechsdk.ResultReason.SynthesizingAudioCompleted
            ):
                print(
                    "Speech synthesized to speaker for text [{}]".format(text)
                )
                audio_data = result.audio_data
                # Send back audio chunk via data channel
                for channel in pc.getTransceivers():
                    if hasattr(channel.sender, "transport") and isinstance(
                        channel.sender.transport, RTCDataChannel
                    ):
                        try:
                            channel.sender.transport.send(audio_data)
                        except Exception:
                            pass

    recognizer.canceled.connect(
        lambda evt: print(
            f"[Canceled] {evt, evt.reason if evt.result.text else 'No speech'}",
            flush=True,
        )
    )
    recognizer.start_continuous_recognition()
    print("[LOG] Azure recognizer started.")

    @pc.on("datachannel")
    def on_datachannel(channel: RTCDataChannel):
        print(
            f"[LOG] Data channel received: {channel.label}, readyState: {channel.readyState}"
        )

        @channel.on("open")
        def on_open():
            print(f"[LOG] Data channel {channel.label} is open.")

        @channel.on("close")
        def on_close():
            print(f"[LOG] Data channel {channel.label} closed.")

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
                pcm_bytes = float32_to_pcm16_resampled(
                    message, input_sr=input_sample_rate
                )
                push_stream.write(pcm_bytes)
            else:
                print(f"[WARN] Received non-bytes message: {message}")

    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    print("[LOG] SDP answer created and set.")

    return {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}


if __name__ == "__main__":
    print("[LOG] Starting FastAPI server on http://0.0.0.0:8080")
    uvicorn.run("stream_voice:app", host="0.0.0.0", port=8080, reload=True)
