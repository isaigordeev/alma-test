import time
import azure.cognitiveservices.speech as speechsdk

# 1. Configure the speech service
endpoint = "https://swedencentral.api.cognitive.microsoft.com/"
speech_config = speechsdk.SpeechConfig(
    subscription=speech_key, endpoint=endpoint
)

speech_config.speech_recognition_language = "fr-FR"

# 2. Define the audio format (16kHz, 16-bit PCM, mono)
stream_format = speechsdk.audio.AudioStreamFormat(
    samples_per_second=48000, bits_per_sample=16, channels=1
)

# 3. Create a push stream and audio config
push_stream = speechsdk.audio.PushAudioInputStream(stream_format=stream_format)
audio_config = speechsdk.audio.AudioConfig(stream=push_stream)

# 4. Create the speech recognizer
recognizer = speechsdk.SpeechRecognizer(
    speech_config=speech_config, audio_config=audio_config
)

# 5. Read audio from a file and push it to the stream
import wave

with wave.open("recording.wav", "rb") as wav_file:
    n_channels = wav_file.getnchannels()
    samp_width = wav_file.getsampwidth()
    sample_rate = wav_file.getframerate()
    n_frames = wav_file.getnframes()

    print(n_channels, samp_width, sample_rate, n_frames)

    pcm_bytes = wav_file.readframes(n_frames)


def stop_cb(evt):
    global done
    done = True


recognizer.recognizing.connect(
    lambda evt: print(
        "Recognizing: {}".format(evt.result.text)
        if evt.result.text
        else "No speech"
    )
)
recognizer.recognized.connect(
    lambda evt: print(
        "Recognized: {}".format(evt.result.text)
        if evt.result.text
        else "No speech"
    )
)
recognizer.session_stopped.connect(stop_cb)
recognizer.canceled.connect(stop_cb)

recognizer.start_continuous_recognition()

# 7. Push audio in small chunks to simulate streaming
chunk_size = 1024 * 1  # bytes per push
for i in range(0, len(pcm_bytes), chunk_size):
    print(type(pcm_bytes[i : i + 5]))
    print("schunk", pcm_bytes[i : i + 5])
    push_stream.write(pcm_bytes[i : i + chunk_size])
    # time.sleep(0.05)  # simulate real-time streaming

# 8. Signal end of stream
push_stream.close()

recognizer.stop_continuous_recognition()
