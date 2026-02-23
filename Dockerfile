FROM python:3.11-slim

# Install system dependencies
# ffmpeg for media processing
# curl for health checks
# wget and gnupg for Chrome installation
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    wget \
    gnupg \
    unzip \
    --no-install-recommends \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Google Chrome for Selenium (Stateless Fallback)
# Using direct .deb installation to avoid deprecated apt-key
RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get update \
    && apt-get install -y ./google-chrome-stable_current_amd64.deb --no-install-recommends \
    && rm google-chrome-stable_current_amd64.deb \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose the port (Port 8088 to avoid conflict with TikTok 8087)
EXPOSE 8088

# Production-ready CMD with Gunicorn
# Timeout 150s to allow for deep extraction fallbacks
CMD ["gunicorn", "app:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8088", "--timeout", "150"]
