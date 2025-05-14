# Imagen base de Python
FROM python:3.12-slim

# Establece el directorio de trabajo
WORKDIR /app

# Copia los archivos
COPY . /app

# Instala las dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Permisos para ffmpeg
RUN chmod +x /app/ffmpeg/ffmpeg /app/ffmpeg/ffprobe

# Expone el puerto si aplica (opcional)
EXPOSE 80

# Comando de inicio
CMD ["python", "function_app.py"]