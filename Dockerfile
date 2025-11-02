# Use a slim Python base
FROM python:3.11-slim

# System libs for OCR, PDF utils, images, audio
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-eng \
    poppler-utils \
    libmagic1 \
    libglib2.0-0 libsm6 libxext6 libxrender1 \
    ffmpeg \
    curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Optional: add more tesseract language packs if you need them
# RUN apt-get update && apt-get install -y tesseract-ocr-pol tesseract-ocr-deu && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app /app/app

ENV PYTHONUNBUFFERED=1 \
    PORT=8080

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "info"]
