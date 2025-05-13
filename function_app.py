import azure.functions as func
import logging
import azure.cognitiveservices.speech as speechsdk
import requests
import os
import subprocess
import stat

app = func.FunctionApp()

@app.function_name(name="transcribe")
@app.route(route="transcribe", auth_level=func.AuthLevel.ANONYMOUS)
def transcribe(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('🧠 Knoxia v2.1 – Inicio de función de transcripción')

    try:
        audio_url = req.params.get('url')
        if not audio_url:
            return func.HttpResponse("Falta parámetro 'url'", status_code=400)

        ext = os.path.splitext(audio_url)[-1].lower()
        if ext not in [".mp3", ".wav"]:
            return func.HttpResponse("Formato no soportado. Solo .mp3 o .wav", status_code=415)

        logging.info(f"🔗 Descargando archivo desde URL: {audio_url}")
        response = requests.get(audio_url)
        audio_data = response.content

        temp_input = "/tmp/input" + ext
        with open(temp_input, "wb") as f:
            f.write(audio_data)

        if ext == ".mp3":
            logging.info("🎛️ Detectado archivo MP3. Iniciando conversión con ffmpeg...")
            temp_wav = "/tmp/converted.wav"
            ffmpeg_path = os.path.join(os.getcwd(), "ffmpeg", "ffmpeg")

            # Asignar permisos de ejecución si faltan
            try:
                st = os.stat(ffmpeg_path)
                os.chmod(ffmpeg_path, st.st_mode | stat.S_IEXEC)
                logging.info("✅ Permisos de ejecución para ffmpeg aplicados")
            except Exception as e:
                logging.error(f"🚫 No se pudo aplicar permisos a ffmpeg: {e}")
                return func.HttpResponse("Error aplicando permisos a ffmpeg", status_code=500)

            try:
                subprocess.run(
                    [ffmpeg_path, "-i", temp_input, "-ar", "16000", "-ac", "1", "-f", "wav", temp_wav],
                    check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                logging.info("🔄 Conversión exitosa. Archivo convertido listo para transcripción")
                audio_path = temp_wav
            except subprocess.CalledProcessError as e:
                logging.error(f"❌ Error durante conversión con ffmpeg: {e.stderr.decode()}")
                return func.HttpResponse("Error convirtiendo archivo MP3", status_code=500)
        else:
            logging.info("📥 Archivo WAV detectado, se usará directamente")
            audio_path = temp_input

        logging.info("🔐 Configurando servicio de transcripción con Azure Speech")
        speech_config = speechsdk.SpeechConfig(
            subscription=os.environ["SPEECH_KEY"],
            region=os.environ["SPEECH_REGION"]
        )
        audio_input = speechsdk.audio.AudioConfig(filename=audio_path)
        recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_input)

        logging.info("🎙️ Ejecutando reconocimiento de voz...")
        result = recognizer.recognize_once()

        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            logging.info(f"📣 Resultado: {result.text}")
            return func.HttpResponse(result.text)

        elif result.reason == speechsdk.ResultReason.NoMatch:
            logging.warning("⚠️ No se reconoció voz en el audio.")
            return func.HttpResponse("No se reconoció ninguna voz en el audio.", status_code=204)

        elif result.reason == speechsdk.ResultReason.Canceled:
            details = getattr(result, "cancellation_details", None)
            logging.error(f"❌ Transcripción cancelada: {getattr(details, 'reason', 'Desconocido')}")
            logging.error(f"🔍 Detalles: {getattr(details, 'error_details', 'Sin detalles')}")
            return func.HttpResponse("Transcripción cancelada por Azure Speech.", status_code=500)

        else:
            logging.warning(f"🤔 Resultado inesperado: {result.reason}")
            return func.HttpResponse(f"Resultado no reconocido: {result.reason}", status_code=500)

    except Exception as e:
        logging.exception("🔥 Excepción general durante la transcripción")
        return func.HttpResponse(f"Error procesando audio: {str(e)}", status_code=500)