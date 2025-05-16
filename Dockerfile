FROM python:3.12-slim

WORKDIR /app

COPY . /app

# Instalamos dependencias necesarias para pyodbc
RUN apt-get update && apt-get install -y \
    unixodbc \
    unixodbc-dev \
    libodbc1 \
    gcc \
    g++ \
    curl \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Instalamos las dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Permisos para ffmpeg
RUN chmod +x /app/ffmpeg/ffmpeg /app/ffmpeg/ffprobe

EXPOSE 80

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]