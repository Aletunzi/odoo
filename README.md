# Odoo Tutorial Agent

Agente Q&A con interfaccia web sui tutorial ufficiali Odoo.  
**Deploy automatico ad ogni push** — nessun comando da eseguire.

---

## Setup iniziale (una volta sola, solo clic)

### Opzione A — Railway (consigliata, gratuita)

1. Vai su [railway.app](https://railway.app) → **Login with GitHub**
2. **New Project** → **Deploy from GitHub repo** → seleziona questo repository
3. Una volta creato il progetto, clicca sul servizio → **Variables** → aggiungi:
   ```
   ANTHROPIC_API_KEY = sk-ant-...
   ```
4. Vai su **Volumes** → **New Volume** → imposta Mount Path: `/app/data`
5. Il primo deploy parte automaticamente

**Da quel momento: ogni push al repository = nuovo deploy automatico.**

---

### Opzione B — Render

1. Vai su [render.com](https://render.com) → **New** → **Web Service**
2. Connetti il repository GitHub
3. Render legge automaticamente il file `render.yaml` — non serve configurare nulla
4. Nella sezione **Environment Variables** aggiungi:
   ```
   ANTHROPIC_API_KEY = sk-ant-...
   ```
5. Clicca **Create Web Service**

**Da quel momento: ogni push al repository = nuovo deploy automatico.**

---

## Cosa succede ad ogni deploy

```
Push su GitHub
  └── Railway/Render costruisce l'immagine Docker
        └── entrypoint.sh verifica cosa manca e avvia solo i passi necessari:
              ├── [solo primo avvio] Scraping video da Odoo
              ├── [solo primo avvio] Download trascrizioni YouTube
              ├── [solo primo avvio] Costruzione indice ChromaDB
              └── Avvio server web → https://tuo-progetto.railway.app
```

I dati (trascrizioni + indice) vengono salvati nel volume e **non vengono rigenerati** ai deploy successivi.

---

## Architettura

```
scraper.py       → Playwright estrae video YouTube dalla pagina Odoo
transcripts.py   → youtube-transcript-api scarica le trascrizioni (IT → EN)
indexer.py       → sentence-transformers crea embedding, ChromaDB indicizza
app.py           → FastAPI serve la UI e lo streaming SSE verso Claude API
static/index.html → Interfaccia chat
```
