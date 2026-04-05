"""
Server web per l'agente Odoo Tutorial.
Espone una UI stile Claude e un endpoint SSE per lo streaming delle risposte.

Uso:
    python app.py                    # http://localhost:8000
    python app.py --port 8080
    python app.py --no-browser       # Non apre il browser automaticamente
"""

import argparse
import asyncio
import json
import os
import webbrowser
from contextlib import asynccontextmanager
from pathlib import Path

import anthropic
import chromadb
from chromadb.config import Settings
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

load_dotenv()

DB_DIR = "data/chroma_db"
COLLECTION_NAME = "odoo_tutorials"
EMBED_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
CLAUDE_MODEL = "claude-opus-4-6"

SYSTEM_PROMPT = """Sei un esperto di Odoo con accesso alle trascrizioni dei tutorial ufficiali Odoo.

Regole:
- Rispondi nella stessa lingua della domanda (italiano o inglese)
- Basa le risposte SOLO sul contesto fornito dalle trascrizioni
- Se l'informazione non è nel contesto, dillo chiaramente
- Usa la formattazione Markdown: **grassetto**, elenchi puntati, blocchi di codice
- Cita il corso di provenienza quando è rilevante
- Sii preciso, pratico e diretto"""

# Stato globale dell'applicazione
_state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Carica i modelli all'avvio, li libera allo spegnimento."""
    print("Caricamento ChromaDB...")
    db_path = Path(DB_DIR)
    if not db_path.exists():
        print(f"[!] DB non trovato in '{DB_DIR}'")
        print("    Esegui prima: python run_pipeline.py")
        _state["ready"] = False
    else:
        client_db = chromadb.PersistentClient(
            path=DB_DIR,
            settings=Settings(anonymized_telemetry=False),
        )
        collection = client_db.get_collection(COLLECTION_NAME)
        print(f"✓ ChromaDB caricato: {collection.count()} chunk")

        print("Caricamento modello embedding...")
        embed_model = SentenceTransformer(EMBED_MODEL_NAME)
        print("✓ Modello embedding caricato")

        _state["collection"] = collection
        _state["embed_model"] = embed_model
        _state["ready"] = True

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[!] ANTHROPIC_API_KEY non trovata nel file .env")
        _state["ready"] = False
    else:
        _state["claude"] = anthropic.AsyncAnthropic(api_key=api_key)
        print("✓ Client Claude inizializzato")

    print("\n🚀 Server pronto su http://localhost:8000\n")
    yield
    _state.clear()


app = FastAPI(lifespan=lifespan)


# ---------------------------------------------------------------------------
# Helpers RAG
# ---------------------------------------------------------------------------

def retrieve_context(question: str, top_k: int = 8) -> list[dict]:
    collection = _state["collection"]
    embed_model = _state["embed_model"]
    embedding = embed_model.encode([question])[0].tolist()
    results = collection.query(
        query_embeddings=[embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )
    chunks = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        chunks.append({
            "text": doc,
            "course_title": meta.get("course_title", "Tutorial Odoo"),
            "url": meta.get("url", ""),
            "language": meta.get("language", ""),
            "score": round(1 - dist, 3),
        })
    return chunks


def build_context_string(chunks: list[dict]) -> str:
    parts = []
    for i, chunk in enumerate(chunks, 1):
        course = chunk["course_title"] or "Tutorial Odoo"
        parts.append(f"[Fonte {i} — {course}]\n{chunk['text']}")
    return "\n\n---\n\n".join(parts)


def deduplicate_sources(chunks: list[dict]) -> list[dict]:
    seen, sources = set(), []
    for c in chunks:
        key = c["url"] or c["course_title"]
        if key not in seen:
            seen.add(key)
            sources.append({"title": c["course_title"], "url": c["url"]})
    return sources[:5]


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

class HistoryMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[HistoryMessage] = []
    top_k: int = 8


@app.get("/")
async def index():
    html = Path("static/index.html").read_text(encoding="utf-8")
    return HTMLResponse(content=html)


@app.get("/api/status")
async def status():
    return {"ready": _state.get("ready", False)}


@app.post("/api/chat")
async def chat(request: ChatRequest):
    if not _state.get("ready"):
        async def error_stream():
            yield f"data: {json.dumps({'type': 'error', 'data': 'Il server non è pronto. Esegui prima python run_pipeline.py'})}\n\n"
        return StreamingResponse(error_stream(), media_type="text/event-stream")

    async def generate():
        # 1. Recupera contesto (I/O bound → thread pool)
        loop = asyncio.get_event_loop()
        chunks = await loop.run_in_executor(
            None, retrieve_context, request.message, request.top_k
        )

        # 2. Invia subito le fonti al client
        sources = deduplicate_sources(chunks)
        yield f"data: {json.dumps({'type': 'sources', 'data': sources})}\n\n"

        # 3. Costruisce messaggi con contesto RAG sull'ultimo turno
        context = build_context_string(chunks)
        messages = [
            *[{"role": m.role, "content": m.content} for m in request.history],
            {
                "role": "user",
                "content": (
                    f"Contesto dalle trascrizioni dei tutorial Odoo:\n\n{context}"
                    f"\n\n---\n\nDomanda: {request.message}"
                ),
            },
        ]

        # 4. Stream risposta Claude
        try:
            async with _state["claude"].messages.stream(
                model=CLAUDE_MODEL,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                messages=messages,
                thinking={"type": "adaptive"},
            ) as stream:
                async for text in stream.text_stream:
                    yield f"data: {json.dumps({'type': 'text', 'data': text})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'data': str(e)})}\n\n"

        yield 'data: {"type": "done"}\n\n'

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser()
    # PORT da argomento o da variabile d'ambiente (Railway, Render, ecc.)
    default_port = int(os.environ.get("PORT", 8000))
    parser.add_argument("--port", type=int, default=default_port)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    if not args.no_browser:
        import threading
        def open_browser():
            import time; time.sleep(1.5)
            webbrowser.open(f"http://localhost:{args.port}")
        threading.Thread(target=open_browser, daemon=True).start()

    uvicorn.run(app, host=args.host, port=args.port)
