<<<<<<< HEAD
# Imagen base de Python
FROM python:3.12-slim
=======
# Imagen base oficial de Python compatible con Azure Functions
FROM mcr.microsoft.com/azure-functions/python:4-python3.12
>>>>>>> 9d72187ffd914ee44ff39e42b547cc2101127d27

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

<<<<<<< HEAD
# Ejecuta el script principal de tu aplicación
CMD ["python", "function_app.py"]
=======
# Comando para iniciar el runtime de Azure Functions
CMD ["python", "-m", "azure_functions_worker"]
>>>>>>> 9d72187ffd914ee44ff39e42b547cc2101127d27
