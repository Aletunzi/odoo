FROM python:3.11-slim

WORKDIR /app

# Dipendenze di sistema per Playwright/Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates wget curl \
    && rm -rf /var/lib/apt/lists/*

# Installa dipendenze Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Installa Chromium con tutte le sue dipendenze di sistema
RUN playwright install chromium --with-deps

# Copia il codice sorgente
COPY . .

RUN chmod +x entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
