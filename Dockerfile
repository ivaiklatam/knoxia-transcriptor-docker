# Imagen base de Python
FROM python:3.12-slim

# Crea y define el directorio de trabajo
WORKDIR /app

# Copia los archivos necesarios
COPY . /app

# Instala las dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Da permisos de ejecución a ffmpeg
RUN chmod +x /app/ffmpeg/ffmpeg /app/ffmpeg/ffprobe

# Expone el puerto si tu app lo requiere (solo si usas Flask/FastAPI, por ejemplo)
EXPOSE 80

# Ejecuta el script principal de tu aplicación
CMD ["python", "function_app.py"]