# Use lightweight Python base
FROM python:3.13-slim

# Install system deps (Tesseract + fonts)
COPY apt.txt .
RUN apt-get update && xargs -a apt.txt apt-get install -y --no-install-recommends && rm -rf /var/lib/apt/lists/*

# Set working dir
WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app files
COPY . .

# Cloud Run requires listening on $PORT
ENV PORT=8080
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 app:app