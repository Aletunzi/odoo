# Odoo Tutorial Agent

Agente Q&A con interfaccia web sui tutorial ufficiali Odoo.

## Avvio rapido (Docker)

```bash
# 1. Clona il repo
git clone <repo-url>
cd odoo

# 2. Configura la API key
cp .env.example .env
# Apri .env e inserisci: ANTHROPIC_API_KEY=sk-ant-...

# 3. Avvia tutto
docker-compose up
```

Al primo avvio, Docker:
1. Installa automaticamente tutte le dipendenze
2. Scarica i video dai tutorial Odoo (scraping)
3. Scarica le trascrizioni da YouTube
4. Costruisce l'indice vettoriale
5. Avvia il server → **http://localhost:8000**

Dal secondo avvio in poi salta tutti i passi già completati e va diretto al server.

> **I dati vengono mantenuti tra un avvio e l'altro** tramite volume Docker: non devi rigenerare nulla dopo un riavvio o un aggiornamento del codice.

---

## Deploy dopo ogni commit

```bash
git pull
docker-compose up --build -d    # Ricostruisce l'immagine e rilancia in background
```

---

## Deploy su Railway / Render

Il `Dockerfile` è già configurato. Basta:

1. Collegare il repository a Railway o Render
2. Impostare la variabile d'ambiente `ANTHROPIC_API_KEY` nel pannello della piattaforma
3. Deploy automatico ad ogni push

---

## Architettura

```
entrypoint.sh
  ├── scraper.py       → Playwright estrae video YouTube da Odoo
  ├── transcripts.py   → youtube-transcript-api scarica trascrizioni (IT → EN)
  ├── indexer.py       → sentence-transformers + ChromaDB indicizza i testi
  └── app.py           → FastAPI serve la UI e l'endpoint SSE /api/chat
```

Il server usa **Claude Opus 4.6** con RAG: recupera i chunk più rilevanti da ChromaDB e li passa come contesto a Claude per ogni domanda.

---

## Struttura file

```
data/                    (volume Docker, non in git)
  videos.json            # Lista video con metadati
  transcripts/           # Trascrizioni JSON per ogni video
  chroma_db/             # Indice vettoriale persistente
static/
  index.html             # UI web (HTML + CSS + JS)
app.py                   # Server FastAPI + SSE streaming
scraper.py               # Scraping Odoo con Playwright
transcripts.py           # Download trascrizioni YouTube
indexer.py               # Embedding + ChromaDB
run_pipeline.py          # Runner pipeline (uso locale)
agent.py                 # CLI alternativa al web
entrypoint.sh            # Script di avvio Docker
Dockerfile
docker-compose.yml
```
