FROM python:3.11-slim

# Re-install ffmpeg because yt-dlp might need it for high-quality fallsbacks
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    --no-install-recommends \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose the port (Port 8088 to avoid conflict with TikTok 8087)
EXPOSE 8088

# Production-ready CMD with Gunicorn
CMD ["gunicorn", "app:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8088", "--timeout", "120"]
