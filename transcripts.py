"""
Scarica le trascrizioni YouTube per tutti i video trovati dallo scraper.
Supporta italiano e inglese (prova italiano prima, poi inglese).

Uso:
    python transcripts.py                          # Legge data/videos.json
    python transcripts.py --videos data/videos.json
    python transcripts.py --lang it en             # Priorità lingua
"""

import argparse
import json
import time
from pathlib import Path

from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from youtube_transcript_api.formatters import TextFormatter


TRANSCRIPT_DIR = Path("data/transcripts")


def download_transcript(video_id: str, languages: list[str]) -> dict | None:
    """
    Scarica la trascrizione di un video YouTube.
    Ritorna dict con 'text', 'language', 'segments' oppure None.
    """
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

        # Prova le lingue in ordine di preferenza
        transcript = None
        used_lang = None

        for lang in languages:
            try:
                transcript = transcript_list.find_transcript([lang])
                used_lang = lang
                break
            except NoTranscriptFound:
                continue

        # Fallback: qualsiasi trascrizione disponibile
        if transcript is None:
            try:
                transcript = transcript_list.find_generated_transcript(languages)
                used_lang = transcript.language_code
            except Exception:
                # Prende la prima disponibile
                for t in transcript_list:
                    transcript = t
                    used_lang = t.language_code
                    break

        if transcript is None:
            return None

        segments = transcript.fetch()
        formatter = TextFormatter()
        full_text = formatter.format_transcript(segments)

        return {
            "language": used_lang,
            "text": full_text,
            "segments": [
                {
                    "text": s["text"],
                    "start": s["start"],
                    "duration": s.get("duration", 0),
                }
                for s in segments
            ],
        }

    except TranscriptsDisabled:
        return None
    except Exception as e:
        print(f"  [!] Errore trascrizione {video_id}: {e}")
        return None


def run_transcripts(
    videos_path: str = "data/videos.json",
    languages: list[str] = None,
    delay: float = 0.5,
):
    if languages is None:
        languages = ["it", "en", "en-US", "en-GB"]

    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)

    with open(videos_path, encoding="utf-8") as f:
        videos = json.load(f)

    print(f"Video da processare: {len(videos)}")
    results = []
    ok, skip, fail = 0, 0, 0

    for i, video in enumerate(videos, 1):
        vid_id = video["video_id"]
        out_file = TRANSCRIPT_DIR / f"{vid_id}.json"

        if out_file.exists():
            print(f"[{i:3d}/{len(videos)}] ✓ {vid_id} (già scaricato)")
            skip += 1
            results.append({**video, "transcript_file": str(out_file), "status": "cached"})
            continue

        print(f"[{i:3d}/{len(videos)}] Scarico {vid_id} ({video['course_title'][:40]})")
        data = download_transcript(vid_id, languages)

        if data:
            payload = {
                "video_id": vid_id,
                "url": video["url"],
                "course_title": video["course_title"],
                "course_url": video["course_url"],
                "slide_url": video.get("slide_url"),
                "language": data["language"],
                "text": data["text"],
                "segments": data["segments"],
            }
            out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"         → {data['language']} | {len(data['text'])} chars")
            results.append({**video, "transcript_file": str(out_file), "status": "ok"})
            ok += 1
        else:
            print(f"         → nessuna trascrizione disponibile")
            results.append({**video, "transcript_file": None, "status": "no_transcript"})
            fail += 1

        time.sleep(delay)

    # Salva sommario
    summary_path = Path("data/transcripts_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Completato: {ok} scaricati, {skip} cached, {fail} senza trascrizione")
    print(f"  Sommario → {summary_path}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--videos", default="data/videos.json")
    parser.add_argument("--lang", nargs="+", default=["it", "en", "en-US"])
    parser.add_argument("--delay", type=float, default=0.5)
    args = parser.parse_args()
    run_transcripts(videos_path=args.videos, languages=args.lang, delay=args.delay)
