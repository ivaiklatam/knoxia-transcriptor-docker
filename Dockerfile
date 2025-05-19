FROM python:3.12-slim

WORKDIR /app

# Copia de archivos del proyecto
COPY . /app

# Instalación de dependencias del sistema (incluye ODBC y compiladores)
RUN apt-get update && apt-get install -y \
    curl \
    apt-transport-https \
    gnupg \
    unixodbc \
    unixodbc-dev \
    gcc \
    g++ \
    libssl-dev \
    libcurl4-openssl-dev \
    libxml2 \
    libkrb5-dev \
    && curl -sSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /etc/apt/trusted.gpg.d/microsoft.gpg \
    && curl -sSL https://packages.microsoft.com/config/debian/12/prod.list -o /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql18 \
    && rm -rf /var/lib/apt/lists/*

# Instalación de paquetes Python
RUN pip install --no-cache-dir -r requirements.txt

# Permisos de ejecución para ffmpeg
RUN chmod +x /app/ffmpeg/ffmpeg /app/ffmpeg/ffprobe

EXPOSE 80

# Comando de inicio de la API
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]