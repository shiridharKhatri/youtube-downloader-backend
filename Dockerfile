FROM python:3.11-slim

# Install system dependencies
# ffmpeg for media processing
# curl for health checks
# Chrome and dependencies for Selenium fallback
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    wget \
    gnupg \
    unzip \
    --no-install-recommends \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Google Chrome for Selenium (if needed)
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "脫deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable --no-install-recommends \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose the port (Port 8088 to avoid conflict with TikTok 8087)
EXPOSE 8088

# Production-ready CMD with Gunicorn
# Timeout increased to 150 to allow for Selenium/yt-dlp fallbacks
CMD ["gunicorn", "app:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8088", "--timeout", "150"]
