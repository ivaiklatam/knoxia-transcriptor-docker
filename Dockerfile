# Imagen base oficial de Python compatible con Azure Functions
FROM mcr.microsoft.com/azure-functions/python:4-python3.12

# Establece el directorio de trabajo dentro del contenedor
WORKDIR /app

# Copia todos los archivos al contenedor
COPY . /app

# Instala dependencias Python
RUN pip install --no-cache-dir -r requirements.txt

# Da permisos de ejecución a los binarios de ffmpeg
RUN chmod +x /app/ffmpeg/ffmpeg /app/ffmpeg/ffprobe

# Expone el puerto usado por Azure Functions (no se necesita cambiar nada aquí)
EXPOSE 80

# Comando para iniciar el runtime de Azure Functions
CMD ["python", "-m", "azure_functions_worker"]
