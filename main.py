# main.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
import azure.cognitiveservices.speech as speechsdk
import requests
import os
import subprocess
import stat
import logging

app = FastAPI(title="Knoxia Transcription API", version="2.1")

@app.get("/transcribe")
def transcribe(url: str):
    logging.info("🧠 Knoxia v2.1 – Inicio de función de transcripción")

    try:
        ext = os.path.splitext(url)[-1].lower()
        if ext not in [".mp3", ".wav"]:
            raise HTTPException(status_code=415, detail="Formato no soportado. Solo .mp3 o .wav")

        logging.info(f"🔗 Descargando archivo desde URL: {url}")
        response = requests.get(url)
        audio_data = response.content

        temp_input = "/tmp/input" + ext
        with open(temp_input, "wb") as f:
            f.write(audio_data)

        if ext == ".mp3":
            logging.info("🎛️ Detectado archivo MP3. Iniciando conversión con ffmpeg...")
            temp_wav = "/tmp/converted.wav"
            ffmpeg_path = os.path.join(os.getcwd(), "ffmpeg", "ffmpeg")

            try:
                st = os.stat(ffmpeg_path)
                os.chmod(ffmpeg_path, st.st_mode | stat.S_IEXEC)
                logging.info("✅ Permisos de ejecución para ffmpeg aplicados")
            except Exception as e:
                logging.error(f"🚫 No se pudo aplicar permisos a ffmpeg: {e}")
                raise HTTPException(status_code=500, detail="Error aplicando permisos a ffmpeg")

            try:
                subprocess.run(
                    [ffmpeg_path, "-i", temp_input, "-ar", "16000", "-ac", "1", "-f", "wav", temp_wav],
                    check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                logging.info("🔄 Conversión exitosa. Archivo convertido listo para transcripción")
                audio_path = temp_wav
            except subprocess.CalledProcessError as e:
                logging.error(f"❌ Error durante conversión con ffmpeg: {e.stderr.decode()}")
                raise HTTPException(status_code=500, detail="Error convirtiendo archivo MP3")
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
            return PlainTextResponse(result.text)

        elif result.reason == speechsdk.ResultReason.NoMatch:
            logging.warning("⚠️ No se reconoció voz en el audio.")
            return PlainTextResponse("No se reconoció ninguna voz en el audio.", status_code=204)

        elif result.reason == speechsdk.ResultReason.Canceled:
            details = getattr(result, "cancellation_details", None)
            logging.error(f"❌ Transcripción cancelada: {getattr(details, 'reason', 'Desconocido')}")
            logging.error(f"🔍 Detalles: {getattr(details, 'error_details', 'Sin detalles')}")
            raise HTTPException(status_code=500, detail="Transcripción cancelada por Azure Speech.")

        else:
            logging.warning(f"🤔 Resultado inesperado: {result.reason}")
            raise HTTPException(status_code=500, detail=f"Resultado no reconocido: {result.reason}")

    except Exception as e:
        logging.exception("🔥 Excepción general durante la transcripción")
        raise HTTPException(status_code=500, detail=f"Error procesando audio: {str(e)}")
