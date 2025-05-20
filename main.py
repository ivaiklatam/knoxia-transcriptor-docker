from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse, JSONResponse
import azure.cognitiveservices.speech as speechsdk
import requests
import os
import subprocess
import stat
import logging
from urllib.parse import urlparse, unquote
from azure.search.documents import SearchClient
import pyodbc
from azure.core.credentials import AzureKeyCredential
import time
import base64

app = FastAPI(title="Knoxia Transcription API", version="2.2")

@app.get("/transcribe")
def transcribe(url: str):
    logging.info("🧠 Knoxia v2.2 – Inicio de función de transcripción")

    try:
        parsed = urlparse(url)
        path = parsed.path
        ext = os.path.splitext(path)[-1].lower()

        if ext not in [".mp3", ".wav", ".webm"]:
            raise HTTPException(status_code=415, detail="Formato no soportado. Solo .mp3, .wav o .webm")

        logging.info(f"🔗 Descargando archivo desde URL: {url}")
        response = requests.get(url)
        response.raise_for_status()
        audio_data = response.content

        temp_input = "/tmp/input" + ext
        with open(temp_input, "wb") as f:
            f.write(audio_data)

        if ext in [".mp3", ".webm"]:
            logging.info(f"🎛️ Detectado archivo {ext.upper()}. Iniciando conversión con ffmpeg...")
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
                raise HTTPException(status_code=500, detail=f"Error convirtiendo archivo {ext.upper()}")
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


@app.post("/run-indexer")
async def run_indexer_eventgrid(request: Request):
    import json

    body = await request.json()
    logging.info("📥 Solicitud recibida en /run-indexer")

    if body and isinstance(body, list):
        event = body[0]
        if event.get("eventType") == "Microsoft.EventGrid.SubscriptionValidationEvent":
            validation_code = event.get("data", {}).get("validationCode")
            logging.info(f"🧾 Validación de Event Grid detectada: {validation_code}")
            return JSONResponse(content={"validationResponse": validation_code})

    try:
        indexer_name = "knoxia-blob-indexer"
        search_service_endpoint = os.environ["AZURE_SEARCH_ENDPOINT"]
        search_admin_key = os.environ["AZURE_SEARCH_KEY"]

        url = f"{search_service_endpoint}/indexers/{indexer_name}/run?api-version=2023-07-01-Preview"
        headers = {
            "Content-Type": "application/json",
            "api-key": search_admin_key
        }

        logging.info(f"🚀 Ejecutando indexador en: {url}")
        response = requests.post(url, headers=headers)
        response.raise_for_status()

        logging.info("✅ Indexador ejecutado exitosamente. Esperando 120 segundos...")
        time.sleep(120)

        logging.info("🔁 Ejecutando sincronización incremental...")
        sync_response = sync_search_to_sql()

        return sync_response

    except requests.HTTPError as http_err:
        logging.error(f"❌ Error HTTP al ejecutar indexador: {http_err.response.text}")
        return JSONResponse({"error": "Error al ejecutar el indexador", "details": http_err.response.text}, status_code=500)

    except Exception as e:
        logging.exception("🔥 Error inesperado en /run-indexer")
        return JSONResponse({"error": "Error inesperado ejecutando indexador", "details": str(e)}, status_code=500)


@app.post("/sync-search-to-sql")
def sync_search_to_sql():
    import re
    try:
        endpoint = os.environ["AZURE_SEARCH_ENDPOINT"]
        key = os.environ["AZURE_SEARCH_KEY"]
        index = os.environ["AZURE_SEARCH_INDEX"]
        search_client = SearchClient(
            endpoint=endpoint,
            index_name=index,
            credential=AzureKeyCredential(key)
        )

        conn = pyodbc.connect(os.environ["AZURE_SQL_CONNECTION_STRING"])
        cursor = conn.cursor()

        cursor.execute("SELECT TOP 1 ultima_fecha_sync FROM Sync_Status WHERE nombre_proceso = 'azure-search-to-sql' ORDER BY fecha_ejecucion DESC")
        row = cursor.fetchone()
        last_sync = row[0].isoformat() if row else None

        query = "*"
        if last_sync:
            query = f"created_at gt {last_sync}"

        results = search_client.search(search_text=query, top=50)

        insertados = 0
        actualizados = 0

        for doc in results:
            doc_id = doc.get("id")
            content = doc.get("content", "")[:255]
            created_at = doc.get("created_at")
            language = doc.get("language") or ""
            title = doc.get("title") or ""
            summary = doc.get("summary") or ""
            key_phrases = doc.get("keyPhrases", [])
            tags = doc.get("tags", [])

            palabras_clave = ";".join(key_phrases)[:2000]
            etiquetas = ";".join(tags)[:255]

            try:
                raw_url = doc_id.encode("ascii")
                decoded = base64.urlsafe_b64decode(raw_url + b'=' * (-len(raw_url) % 4)).decode()
                nombre_archivo = re.findall(r"/([^/]+)$", decoded)
                nombre = unquote(nombre_archivo[0]) if nombre_archivo else "Autoimportado"
            except Exception:
                nombre = "Autoimportado"

            cursor.execute("SELECT COUNT(*) FROM Documentos WHERE url_blob = ?", doc_id)
            exists = cursor.fetchone()[0] > 0

            if not exists:
                cursor.execute("""
                    INSERT INTO Documentos 
                    (nombre, descripcion, url_blob, fecha_cargue, idioma, resumen, titulo, palabras_clave, etiquetas)
                    VALUES (?, ?, ?, GETDATE(), ?, ?, ?, ?, ?)
                """, nombre[:255], content, doc_id, language[:10], summary[:1000], title[:500], palabras_clave, etiquetas)
                insertados += 1
            else:
                cursor.execute("""
                    UPDATE Documentos 
                    SET descripcion = ?, idioma = ?, resumen = ?, titulo = ?, palabras_clave = ?, etiquetas = ?, fecha_modificacion = GETDATE()
                    WHERE url_blob = ?
                """, content, language[:10], summary[:1000], title[:500], palabras_clave, etiquetas, doc_id)
                actualizados += 1

        cursor.execute("""
            INSERT INTO Sync_Status (nombre_proceso, ultima_fecha_sync, estado, detalles)
            VALUES (?, GETDATE(), ?, ?)
        """, "azure-search-to-sql", "OK", f"{insertados} nuevos, {actualizados} actualizados")

        conn.commit()
        conn.close()

        return JSONResponse({
            "message": "Sincronización completada",
            "documentos_nuevos": insertados,
            "documentos_actualizados": actualizados
        })

    except Exception as e:
        logging.exception("🔥 Error sincronizando índice con SQL")
        raise HTTPException(status_code=500, detail=f"Error sincronizando: {str(e)}")