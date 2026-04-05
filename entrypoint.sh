#!/bin/bash

DATA_DIR="data"
mkdir -p "$DATA_DIR"

echo ""
echo "╔══════════════════════════════════╗"
echo "║     Odoo Tutorial Agent          ║"
echo "╚══════════════════════════════════╝"
echo ""

# ── Step 1: Scraping ────────────────────────────────────────
if [ -f "$DATA_DIR/videos.json" ]; then
    COUNT=$(python -c "import json; print(len(json.load(open('$DATA_DIR/videos.json'))))" 2>/dev/null || echo "?")
    echo "✓ [1/3] videos.json trovato ($COUNT video) — skip scraping"
else
    echo "→ [1/3] Scraping pagina tutorial Odoo..."
    python scraper.py --headless --out "$DATA_DIR/videos.json" || {
        echo "⚠ Scraping fallito (probabile blocco 403). Il server parte comunque."
        echo "  Per aggiungere video manualmente: modifica data/videos.json"
    }
fi

# ── Step 2: Trascrizioni ─────────────────────────────────────
TRANSCRIPT_COUNT=$(ls "$DATA_DIR/transcripts/"*.json 2>/dev/null | wc -l || echo 0)
if [ "$TRANSCRIPT_COUNT" -gt 0 ]; then
    echo "✓ [2/3] $TRANSCRIPT_COUNT trascrizioni trovate — skip download"
elif [ -f "$DATA_DIR/videos.json" ]; then
    echo "→ [2/3] Download trascrizioni YouTube..."
    python transcripts.py --videos "$DATA_DIR/videos.json" || {
        echo "⚠ Download trascrizioni parzialmente fallito. Continuo con quelle disponibili."
    }
else
    echo "⚠ [2/3] Nessun videos.json trovato — skip trascrizioni"
fi

# ── Step 3: Indicizzazione ───────────────────────────────────
if [ -d "$DATA_DIR/chroma_db" ] && [ "$(ls -A $DATA_DIR/chroma_db 2>/dev/null)" ]; then
    echo "✓ [3/3] Indice ChromaDB trovato — skip indicizzazione"
else
    TRANSCRIPT_COUNT=$(ls "$DATA_DIR/transcripts/"*.json 2>/dev/null | wc -l || echo 0)
    if [ "$TRANSCRIPT_COUNT" -gt 0 ]; then
        echo "→ [3/3] Costruzione indice vettoriale..."
        python indexer.py || echo "⚠ Indicizzazione fallita. Il server parte senza dati."
    else
        echo "⚠ [3/3] Nessuna trascrizione disponibile — skip indicizzazione"
    fi
fi

echo ""
echo "✅ Avvio server web su porta ${PORT:-8000}..."
echo ""

exec python app.py --no-browser --host 0.0.0.0 --port "${PORT:-8000}"
