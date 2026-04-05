"""
Agente Q&A sui tutorial Odoo.
Usa ChromaDB per il retrieval e Claude API per la risposta.

Uso:
    python agent.py                      # Modalità chat interattiva
    python agent.py --question "..."     # Risposta singola (non interattivo)
    python agent.py --top-k 10           # Più contesto recuperato
"""

import argparse
import os
from pathlib import Path

import anthropic
import chromadb
from chromadb.config import Settings
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

load_dotenv()

DB_DIR = "data/chroma_db"
COLLECTION_NAME = "odoo_tutorials"
EMBED_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
CLAUDE_MODEL = "claude-opus-4-6"

SYSTEM_PROMPT = """Sei un esperto di Odoo con accesso alle trascrizioni dei tutorial ufficiali.
Rispondi sempre in italiano (o nella lingua in cui ti viene posta la domanda).
Basa le tue risposte ESCLUSIVAMENTE sul contesto fornito dalle trascrizioni.
Se l'informazione non è nel contesto, dillo chiaramente.
Cita il corso di provenienza quando è rilevante.
Sii preciso, pratico e diretto."""


def load_components(db_dir: str = DB_DIR):
    """Carica ChromaDB e il modello di embedding."""
    if not Path(db_dir).exists():
        raise FileNotFoundError(
            f"DB non trovato in '{db_dir}'.\n"
            "Esegui prima la pipeline completa:\n"
            "  python run_pipeline.py"
        )

    client = chromadb.PersistentClient(
        path=db_dir,
        settings=Settings(anonymized_telemetry=False),
    )
    collection = client.get_collection(COLLECTION_NAME)

    print(f"DB caricato: {collection.count()} chunk indicizzati")
    print(f"Caricamento modello embedding...")
    model = SentenceTransformer(EMBED_MODEL_NAME)
    print("✓ Pronto\n")

    return collection, model


def retrieve_context(
    question: str,
    collection,
    model: SentenceTransformer,
    top_k: int = 8,
) -> list[dict]:
    """Recupera i chunk più rilevanti per la domanda."""
    embedding = model.encode([question])[0].tolist()
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
            "course_title": meta.get("course_title", ""),
            "url": meta.get("url", ""),
            "language": meta.get("language", ""),
            "relevance_score": round(1 - dist, 3),
        })
    return chunks


def build_context_string(chunks: list[dict]) -> str:
    """Formatta i chunk recuperati come contesto per Claude."""
    parts = []
    seen_courses = set()
    for i, chunk in enumerate(chunks, 1):
        course = chunk["course_title"] or "Tutorial Odoo"
        header = f"[Fonte {i} — {course}]"
        if course not in seen_courses:
            seen_courses.add(course)
        parts.append(f"{header}\n{chunk['text']}")
    return "\n\n---\n\n".join(parts)


def ask(
    question: str,
    collection,
    model: SentenceTransformer,
    client: anthropic.Anthropic,
    top_k: int = 8,
    conversation_history: list = None,
) -> tuple[str, list[dict]]:
    """
    Pone una domanda all'agente e restituisce (risposta, chunks_usati).
    conversation_history viene modificata in place per il multi-turn.
    """
    if conversation_history is None:
        conversation_history = []

    chunks = retrieve_context(question, collection, model, top_k=top_k)
    context = build_context_string(chunks)

    user_message = f"""Contesto dalle trascrizioni dei tutorial Odoo:

{context}

---

Domanda: {question}"""

    conversation_history.append({"role": "user", "content": user_message})

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=conversation_history,
        thinking={"type": "adaptive"},
    )

    answer = next(
        (b.text for b in response.content if b.type == "text"), ""
    )
    conversation_history.append({"role": "assistant", "content": answer})

    return answer, chunks


def print_sources(chunks: list[dict], show_scores: bool = False):
    """Stampa le fonti usate per la risposta."""
    seen = set()
    sources = []
    for c in chunks:
        key = c["url"] or c["course_title"]
        if key not in seen:
            seen.add(key)
            sources.append(c)

    print("\n📚 Fonti:")
    for s in sources[:4]:
        score_str = f" (relevance: {s['relevance_score']})" if show_scores else ""
        course = s["course_title"] or "Tutorial Odoo"
        url = s["url"]
        print(f"  • {course}{score_str}")
        if url:
            print(f"    {url}")


def interactive_chat(collection, model, client: anthropic.Anthropic, top_k: int = 8):
    """Loop di chat interattiva con memoria della conversazione."""
    print("=" * 60)
    print("Agente Odoo Tutorial — Digita 'exit' per uscire")
    print("                        Digita 'clear' per nuova conversazione")
    print("=" * 60)

    history = []
    while True:
        try:
            question = input("\n🙋 Tu: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nArrivederci!")
            break

        if not question:
            continue
        if question.lower() in ("exit", "quit", "esci"):
            print("Arrivederci!")
            break
        if question.lower() == "clear":
            history = []
            print("✓ Conversazione azzerata")
            continue

        print("\n🤖 Agente: ", end="", flush=True)
        answer, chunks = ask(question, collection, model, client, top_k=top_k, conversation_history=history)
        print(answer)
        print_sources(chunks)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--question", "-q", help="Domanda singola (non interattivo)")
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--db-dir", default=DB_DIR)
    parser.add_argument("--show-scores", action="store_true")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY non trovata.\n"
            "Crea un file .env con: ANTHROPIC_API_KEY=your-key-here"
        )

    collection, embed_model = load_components(db_dir=args.db_dir)
    claude_client = anthropic.Anthropic(api_key=api_key)

    if args.question:
        answer, chunks = ask(args.question, collection, embed_model, claude_client, top_k=args.top_k)
        print(answer)
        print_sources(chunks, show_scores=args.show_scores)
    else:
        interactive_chat(collection, embed_model, claude_client, top_k=args.top_k)


if __name__ == "__main__":
    main()
