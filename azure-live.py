import azure.cognitiveservices.speech as speechsdk
import time


def stream_recognition_from_microphone():
    """Stream audio recognition with real-time results."""
    # Configure speech service
    speech_config = speechsdk.SpeechConfig(
        endpoint="https://swedencentral.api.cognitive.microsoft.com/",
    )
    speech_config.speech_recognition_language = "fr-FR"
    # Enable continuous recognition
    speech_config.enable_dictation()
    # Audio configuration
    audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)
    speech_recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config, audio_config=audio_config
    )

    # Event handlers for streaming
    def recognizing_callback(evt):
        """Called during recognition (partial results)."""
        print(f"Recognizing: {evt.result.text}")

    def recognized_callback(evt):
        """Called when a phrase is recognized (final result)."""
        if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            print(f":white_check_mark: Recognized: {evt.result.text}")
        elif evt.result.reason == speechsdk.ResultReason.NoMatch:
            print(":x: No speech could be recognized")

    def canceled_callback(evt):
        """Called when recognition is canceled."""
        print(
            f":octagonal_sign: Canceled: {evt.result.cancellation_details.reason}"
        )
        if (
            evt.result.cancellation_details.reason
            == speechsdk.CancellationReason.Error
        ):
            print(
                f":x: Error: {evt.result.cancellation_details.error_details}"
            )

    def session_started_callback(evt):
        """Called when session starts."""
        print(":microphone: Speech recognition session started...")

    def session_stopped_callback(evt):
        """Called when session stops."""
        print(":mute: Speech recognition session stopped.")

    # Connect event handlers
    speech_recognizer.recognizing.connect(recognizing_callback)
    speech_recognizer.recognized.connect(recognized_callback)
    speech_recognizer.canceled.connect(canceled_callback)
    speech_recognizer.session_started.connect(session_started_callback)
    speech_recognizer.session_stopped.connect(session_stopped_callback)
    # Start continuous recognition
    print("Starting continuous speech recognition...")
    print("Say something (press Ctrl+C to stop)...")
    speech_recognizer.start_continuous_recognition()
    try:
        # Keep the program running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n:octagonal_sign: Stopping recognition...")
        speech_recognizer.stop_continuous_recognition()


def stream_recognition_with_phrase_detection():
    """Stream recognition with phrase-based detection."""
    speech_config = speechsdk.SpeechConfig(
        endpoint="https://swedencentral.api.cognitive.microsoft.com/",
    )
    speech_config.speech_recognition_language = "fr-FR"
    # Configure for better streaming
    speech_config.set_property(
        speechsdk.PropertyId.SpeechServiceConnection_InitialSilenceTimeoutMs,
        "5000",
    )
    speech_config.set_property(
        speechsdk.PropertyId.SpeechServiceConnection_EndSilenceTimeoutMs,
        "2000",
    )
    audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)
    speech_recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config, audio_config=audio_config
    )
    complete_text = ""

    def recognizing_callback(evt):
        """Real-time partial results."""
        print(
            f"\r:arrows_counterclockwise: En cours: {evt.result.text}",
            end="",
            flush=True,
        )

    def recognized_callback(evt):
        """Final recognized phrase."""
        nonlocal complete_text
        if (
            evt.result.reason == speechsdk.ResultReason.RecognizedSpeech
            and evt.result.text
        ):
            complete_text += evt.result.text + " "
            print(f"\n:white_check_mark: Phrase complète: {evt.result.text}")
            print(f":memo: Texte total: {complete_text.strip()}")
            print("---")

    def canceled_callback(evt):
        print(
            f"\n:octagonal_sign: Annulé: {evt.result.cancellation_details.reason}"
        )

    # Connect callbacks
    speech_recognizer.recognizing.connect(recognizing_callback)
    speech_recognizer.recognized.connect(recognized_callback)
    speech_recognizer.canceled.connect(canceled_callback)
    print(":microphone: Reconnaissance vocale continue démarrée...")
    print("Parlez (Ctrl+C pour arrêter)...")
    speech_recognizer.start_continuous_recognition()
    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print(f"\n:octagonal_sign: Arrêt de la reconnaissance...")
        print(f":page_facing_up: Texte final complet: {complete_text.strip()}")
        speech_recognizer.stop_continuous_recognition()


def push_stream_recognition():
    """Stream recognition using push audio stream (for custom audio sources)."""
    speech_config = speechsdk.SpeechConfig(
        endpoint="https://swedencentral.api.cognitive.microsoft.com/",
    )
    speech_config.speech_recognition_language = "fr-FR"
    # Create push stream
    stream_format = speechsdk.audio.AudioStreamFormat(
        samples_per_second=16000, channels=1
    )
    push_stream = speechsdk.audio.PushAudioInputStream(stream_format)
    audio_config = speechsdk.audio.AudioConfig(stream=push_stream)
    speech_recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config, audio_config=audio_config
    )

    def recognizing_callback(evt):
        print(f":arrows_counterclockwise: Streaming: {evt.result.text}")

    def recognized_callback(evt):
        if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            print(f":white_check_mark: Final: {evt.result.text}")

    speech_recognizer.recognizing.connect(recognizing_callback)
    speech_recognizer.recognized.connect(recognized_callback)
    print(":microphone: Push stream recognition ready...")
    speech_recognizer.start_continuous_recognition()
    # Here you would push audio data to the stream
    # push_stream.write(audio_bytes)
    try:
        # In real implementation, you'd read from audio source and push data
        time.sleep(30)  # Example duration
    except KeyboardInterrupt:
        pass
    finally:
        push_stream.close()
        speech_recognizer.stop_continuous_recognition()


if __name__ == "__main__":
    print("Choisissez le mode de reconnaissance:")
    print("1. Reconnaissance continue simple")
    print("2. Reconnaissance avec détection de phrases")
    print("3. Reconnaissance avec push stream")
    choice = input("Votre choix (1-3): ")
    if choice == "1":
        stream_recognition_from_microphone()
    elif choice == "2":
        stream_recognition_with_phrase_detection()
    elif choice == "3":
        push_stream_recognition()
    else:
        print("Choix invalide, lancement du mode par défaut...")
        stream_recognition_with_phrase_detection()
