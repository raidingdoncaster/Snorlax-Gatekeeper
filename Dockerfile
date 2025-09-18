# Start with a small version of Python
FROM python:3.11-slim

# Install Tesseract OCR (needed for pytesseract to work)
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libtesseract-dev \
    && rm -rf /var/lib/apt/lists/*

# Choose the folder inside the container where our code lives
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all your code into the container
COPY . .

# Make sure Google Sheets key is inside
COPY pogo-passport-key.json /app/pogo-passport-key.json

# Cloud Run always uses port 8080
ENV PORT=8080
EXPOSE 8080

# Flask needs a secret key
ENV SECRET_KEY="change-this-secret"

# Start the app using Gunicorn (production web server)
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app