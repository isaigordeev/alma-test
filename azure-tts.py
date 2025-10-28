import azure.cognitiveservices.speech as speechsdk

endpoint = "https://swedencentral.api.cognitive.microsoft.com/"
speech_config = speechsdk.SpeechConfig(
    subscription=speech_key, endpoint=endpoint
)

speech_config.set_speech_synthesis_output_format(
    speechsdk.SpeechSynthesisOutputFormat.Raw48Khz16BitMonoPcm
)

# Création du synthétiseur vocal
speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config)

# Exemple de SSML en français
ssml = """
<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="fr-FR">
  <voice name="fr-FR-VivienneMultilingualNeural">
      Bonjour ! Ceci est un exemple de synthèse vocale Azure avec SSML en français.
  </voice>
</speak>
"""
# fr-FR-Vivienne:DragonHDLatestNeural
# fr-FR-VivienneMultilingualNeural
ssml = """<speak version="1.0"
       xmlns="http://www.w3.org/2001/10/synthesis"
       xmlns:mstts="https://www.w3.org/2001/mstts"
       xml:lang="fr-FR">

  <voice name="fr-FR-VivienneMultilingualNeural">

    <mstts:express-as style="embarrassed">
      C'est du texte prononcé!
    </mstts:express-as>
  </voice>
</speak>


"""

ssml = """<speak xmlns="http://www.w3.org/2001/10/synthesis" xmlns:mstts="http://www.w3.org/2001/mstts" xmlns:emo="http://www.w3.org/2009/10/emotionml" version="1.0" xml:lang="fr-FR">    <voice name="en-US-AvaMultilingualNeural">
        <mstts:express-as style="cheerful" styledegree="2">
        ça serait super cool!
        </mstts:express-as>
        <mstts:express-as style="my-custom-style" styledegree="0.01">
        Et de suite? 
        </mstts:express-as>
    </voice></speak>"""

# Exécution de la synthèse
result = speech_synthesizer.speak_ssml_async(ssml).get()

if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
    print("✅ Synthèse vocale réussie.")
else:
    print(f"❌ Échec de la synthèse : {result.reason}")
