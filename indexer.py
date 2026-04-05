"""
Indicizza le trascrizioni in ChromaDB usando sentence-transformers.
Divide ogni trascrizione in chunk da ~500 token con sovrapposizione.

Uso:
    python indexer.py                    # Indicizza data/transcripts/
    python indexer.py --reset            # Svuota il DB e reindicizza
    python indexer.py --chunk-size 500
"""

import argparse
import json
from pathlib import Path

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

DB_DIR = "data/chroma_db"
COLLECTION_NAME = "odoo_tutorials"
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """
    Divide il testo in chunk di circa chunk_size parole con overlap.
    Usa i paragrafi come unità naturali dove possibile.
    """
    words = text.split()
    if len(words) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        if end == len(words):
            break
        start += chunk_size - overlap

    return chunks


def build_index(
    transcripts_dir: str = "data/transcripts",
    db_dir: str = DB_DIR,
    chunk_size: int = 500,
    overlap: int = 50,
    reset: bool = False,
    batch_size: int = 64,
):
    transcript_files = list(Path(transcripts_dir).glob("*.json"))
    if not transcript_files:
        print(f"[!] Nessuna trascrizione trovata in {transcripts_dir}")
        print("    Esegui prima: python transcripts.py")
        return

    print(f"Modello di embedding: {MODEL_NAME}")
    print("Caricamento modello (prima volta: ~300MB download)...")
    model = SentenceTransformer(MODEL_NAME)
    print("✓ Modello caricato")

    client = chromadb.PersistentClient(
        path=db_dir,
        settings=Settings(anonymized_telemetry=False),
    )

    if reset:
        try:
            client.delete_collection(COLLECTION_NAME)
            print(f"✓ Collezione '{COLLECTION_NAME}' eliminata")
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    existing_ids = set(collection.get(include=[])["ids"])
    print(f"Documenti già nel DB: {len(existing_ids)}")

    all_chunks = []
    all_ids = []
    all_metadatas = []

    print(f"\nPreparazione chunk da {len(transcript_files)} trascrizioni...")
    for tf in transcript_files:
        data = json.loads(tf.read_text(encoding="utf-8"))
        video_id = data["video_id"]
        text = data.get("text", "").strip()

        if not text:
            continue

        chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
        for idx, chunk in enumerate(chunks):
            chunk_id = f"{video_id}_{idx}"
            if chunk_id in existing_ids:
                continue
            all_chunks.append(chunk)
            all_ids.append(chunk_id)
            all_metadatas.append({
                "video_id": video_id,
                "url": data.get("url", ""),
                "course_title": data.get("course_title", ""),
                "language": data.get("language", ""),
                "chunk_index": idx,
                "total_chunks": len(chunks),
            })

    if not all_chunks:
        print("✓ Tutti i documenti sono già indicizzati")
        print(f"  Totale chunk nel DB: {collection.count()}")
        return collection, model

    print(f"Nuovi chunk da indicizzare: {len(all_chunks)}")
    print("Calcolo embedding e inserimento nel DB...")

    for i in range(0, len(all_chunks), batch_size):
        batch_texts = all_chunks[i : i + batch_size]
        batch_ids = all_ids[i : i + batch_size]
        batch_meta = all_metadatas[i : i + batch_size]

        embeddings = model.encode(batch_texts, show_progress_bar=False).tolist()
        collection.add(
            ids=batch_ids,
            documents=batch_texts,
            embeddings=embeddings,
            metadatas=batch_meta,
        )
        done = min(i + batch_size, len(all_chunks))
        print(f"  {done}/{len(all_chunks)} chunk indicizzati", end="\r")

    print(f"\n✓ Indicizzazione completata")
    print(f"  Totale chunk nel DB: {collection.count()}")
    print(f"  DB salvato in: {db_dir}")

    return collection, model


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--transcripts-dir", default="data/transcripts")
    parser.add_argument("--db-dir", default=DB_DIR)
    parser.add_argument("--chunk-size", type=int, default=500)
    parser.add_argument("--overlap", type=int, default=50)
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    build_index(
        transcripts_dir=args.transcripts_dir,
        db_dir=args.db_dir,
        chunk_size=args.chunk_size,
        overlap=args.overlap,
        reset=args.reset,
    )
