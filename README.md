# Odoo Tutorial Agent

Agente Q&A basato su RAG per rispondere a domande sui tutorial ufficiali Odoo.

## Architettura

```
Scraping (Playwright)
  → YouTube Transcripts (youtube-transcript-api)
    → Embeddings + ChromaDB
      → Claude API (claude-opus-4-6) con RAG
```

## Setup

```bash
# 1. Installa dipendenze
pip install -r requirements.txt

# 2. Installa browser Playwright
playwright install chromium

# 3. Configura API key
cp .env.example .env
# Apri .env e inserisci ANTHROPIC_API_KEY=sk-ant-...
```

## Pipeline completa (prima volta)

```bash
python run_pipeline.py
```

Questo esegue 3 step in sequenza:

| Step | Cosa fa | Output |
|------|---------|--------|
| 1. Scraping | Playwright visita la pagina Odoo e raccoglie gli URL dei video YouTube | `data/videos.json` |
| 2. Trascrizioni | Scarica le trascrizioni da YouTube (IT → EN come fallback) | `data/transcripts/*.json` |
| 3. Indicizzazione | Crea embedding con `paraphrase-multilingual-MiniLM-L12-v2` e indicizza in ChromaDB | `data/chroma_db/` |

> **Nota sullo scraping**: il browser si apre in modalità visibile (non headless) per evitare il blocco 403 di Odoo. Lascia che carichi normalmente.

## Avvia il server web

```bash
python app.py
# → http://localhost:8000
```

Apre automaticamente il browser. Interfaccia stile Claude con:
- Streaming delle risposte in tempo reale
- Fonti cliccabili sotto ogni risposta
- Memoria della conversazione multi-turn
- Cronologia conversazioni nella sidebar
- Domande suggerite per iniziare

```bash
python app.py --port 8080      # Porta personalizzata
python app.py --no-browser     # Non aprire il browser automaticamente
```

## Uso dell'agente da CLI (alternativa)

```bash
# Chat interattiva nel terminale
python agent.py

# Domanda singola
python agent.py --question "Come si configura il magazzino?"
```

## Step individuali

```bash
# Solo scraping
python scraper.py

# Solo trascrizioni (richiede data/videos.json)
python transcripts.py

# Solo indicizzazione (richiede data/transcripts/)
python indexer.py

# Reindicizza da zero
python indexer.py --reset
```

## Opzioni avanzate

```bash
# Forza ri-scraping in headless (meno affidabile)
python run_pipeline.py --headless

# Salta lo scraping se videos.json esiste già
python run_pipeline.py --skip-scraping

# Ricostruisce il DB ChromaDB da zero
python run_pipeline.py --reset-index

# Trascrizioni solo in inglese
python transcripts.py --lang en en-US
```

## Struttura file

```
data/
  videos.json              # Lista video con metadati corso
  transcripts/
    <video_id>.json        # Trascrizione + metadati per ogni video
  transcripts_summary.json # Sommario download
  chroma_db/               # Indice vettoriale persistente
```

## Modelli usati

| Componente | Modello | Note |
|------------|---------|------|
| Embedding | `paraphrase-multilingual-MiniLM-L12-v2` | Locale, ~300MB, supporta IT+EN |
| LLM | `claude-opus-4-6` | Via API Anthropic |
| Scraping | Playwright Chromium | Browser headful per evitare 403 |
