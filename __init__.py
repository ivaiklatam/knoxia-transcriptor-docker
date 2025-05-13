import azure.functions as func
import logging
import azure.cognitiveservices.speech as speechsdk
import requests
import os
from pydub import AudioSegment

app = func.FunctionApp()

@app.function_name(name="transcribe")
@app.route(route="transcribe", auth_level=func.AuthLevel.ANONYMOUS)
def transcribe(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Knoxia transcripción: procesando solicitud init.')

    try:
        audio_url = req.params.get('url')
        if not audio_url:
            return func.HttpResponse("Falta parámetro 'url'", status_code=400)

        # Descargar archivo de audio
        audio_data = requests.get(audio_url).content
        temp_mp3_path = "/tmp/temp_audio.mp3"
        temp_wav_path = "/tmp/temp_audio.wav"

        # Guardar el mp3 original
        with open(temp_mp3_path, "wb") as f:
            f.write(audio_data)

        # Convertir MP3/WAV al formato PCM WAV mono 16kHz 16-bit compatible con Azure
        audio = AudioSegment.from_file(temp_mp3_path)
        audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
        audio.export(temp_wav_path, format="wav")

        # Configurar Azure Speech
        speech_config = speechsdk.SpeechConfig(
            subscription=os.environ["SPEECH_KEY"],
            region=os.environ["SPEECH_REGION"]
        )
        audio_input = speechsdk.audio.AudioConfig(filename=temp_wav_path)
        recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_input)
        result = recognizer.recognize_once()

        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            return func.HttpResponse(result.text)
        else:
            return func.HttpResponse(f"No se reconoció voz. Razón: {result.reason}", status_code=500)

    except Exception as e:
        logging.error(f"Error: {e}")
        return func.HttpResponse(f"Error procesando audio: {e}", status_code=500)
