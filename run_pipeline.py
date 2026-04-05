"""
Runner unico per tutta la pipeline:
  1. Scraping (Playwright)   → data/videos.json
  2. Trascrizioni (YouTube)  → data/transcripts/*.json
  3. Indicizzazione (ChromaDB) → data/chroma_db/

Uso:
    python run_pipeline.py                   # Pipeline completa
    python run_pipeline.py --skip-scraping   # Salta scraping (usa videos.json esistente)
    python run_pipeline.py --skip-transcripts # Salta solo le trascrizioni
    python run_pipeline.py --headless        # Scraping headless (potrebbe dare 403)
    python run_pipeline.py --reset-index     # Ricostruisce il DB da zero
"""

import argparse
from pathlib import Path


def step_scraping(headless: bool, videos_path: str):
    print("\n" + "=" * 60)
    print("STEP 1: SCRAPING ODOO TUTORIALS")
    print("=" * 60)

    if Path(videos_path).exists():
        import json
        videos = json.loads(Path(videos_path).read_text())
        print(f"✓ {videos_path} già esistente con {len(videos)} video")
        answer = input("  Vuoi ri-eseguire lo scraping? [s/N] ").strip().lower()
        if answer not in ("s", "si", "y", "yes"):
            print("  Salto scraping.")
            return

    from scraper import run_scraper
    run_scraper(headless=headless, out_path=videos_path)


def step_transcripts(videos_path: str, languages: list):
    print("\n" + "=" * 60)
    print("STEP 2: DOWNLOAD TRASCRIZIONI YOUTUBE")
    print("=" * 60)
    from transcripts import run_transcripts
    run_transcripts(videos_path=videos_path, languages=languages)


def step_index(reset: bool):
    print("\n" + "=" * 60)
    print("STEP 3: INDICIZZAZIONE IN CHROMADB")
    print("=" * 60)
    from indexer import build_index
    build_index(reset=reset)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-scraping", action="store_true")
    parser.add_argument("--skip-transcripts", action="store_true")
    parser.add_argument("--skip-index", action="store_true")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--reset-index", action="store_true")
    parser.add_argument("--videos", default="data/videos.json")
    parser.add_argument("--lang", nargs="+", default=["it", "en", "en-US"])
    args = parser.parse_args()

    Path("data").mkdir(exist_ok=True)

    print("🚀 PIPELINE ODOO TUTORIAL AGENT")
    print("Questa pipeline scarica e indicizza i tutorial Odoo per l'agente Q&A.")

    if not args.skip_scraping:
        step_scraping(headless=args.headless, videos_path=args.videos)
    else:
        print("\n[STEP 1] Scraping saltato")

    if not args.skip_transcripts:
        step_transcripts(videos_path=args.videos, languages=args.lang)
    else:
        print("\n[STEP 2] Download trascrizioni saltato")

    if not args.skip_index:
        step_index(reset=args.reset_index)
    else:
        print("\n[STEP 3] Indicizzazione saltata")

    print("\n" + "=" * 60)
    print("✅ PIPELINE COMPLETATA")
    print("=" * 60)
    print("\nAvvia l'agente con:")
    print("  python agent.py")
    print("\nOppure fai una domanda diretta:")
    print('  python agent.py --question "Come si configura il magazzino in Odoo?"')


if __name__ == "__main__":
    main()
