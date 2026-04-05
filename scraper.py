"""
Scraper: estrae tutti gli URL dei video YouTube dalla pagina dei tutorial Odoo.
Usa Playwright per simulare un browser reale e aggirare il blocco 403.

Uso:
    python scraper.py                    # Salva in data/videos.json
    python scraper.py --headless         # Modalità headless (potrebbe essere bloccata)
    python scraper.py --out custom.json  # File di output personalizzato
"""

import argparse
import json
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


ODOO_TAG_URL = "https://www.odoo.com/it_IT/slides/tag/odoo-tutorials-9"
YOUTUBE_RE = re.compile(
    r"(?:youtube\.com/(?:embed/|watch\?v=)|youtu\.be/)([A-Za-z0-9_-]{11})"
)


def extract_youtube_ids(page_content: str) -> list[str]:
    return list(dict.fromkeys(YOUTUBE_RE.findall(page_content)))


def scrape_course_urls(page) -> list[dict]:
    """Estrae i link ai corsi dalla pagina tag."""
    courses = []
    page.wait_for_selector("a[href*='/slides/']", timeout=15000)
    links = page.query_selector_all("a[href*='/slides/']")
    seen = set()
    for link in links:
        href = link.get_attribute("href") or ""
        if "/slides/" in href and href not in seen:
            # Esclude link a singole slide (/slides/slide/) o al tag stesso
            if "/slides/slide/" not in href and "/slides/tag/" not in href:
                title = link.inner_text().strip() or href
                courses.append({"title": title, "url": href})
                seen.add(href)
    return courses


def scrape_slide_pages(page, course_url: str, base_url: str) -> list[str]:
    """Visita una pagina corso e raccoglie tutti i link a slide/video."""
    full_url = base_url + course_url if course_url.startswith("/") else course_url
    page.goto(full_url, wait_until="domcontentloaded")
    time.sleep(1)

    content = page.content()
    # Prima cerca ID YouTube direttamente nel sorgente della pagina
    ids_in_page = extract_youtube_ids(content)

    # Poi cerca link a slide individuali
    slide_links = page.query_selector_all("a[href*='/slides/slide/']")
    slide_urls = []
    for link in slide_links:
        href = link.get_attribute("href") or ""
        if href:
            slide_urls.append(href)

    return ids_in_page, list(dict.fromkeys(slide_urls))


def scrape_single_slide(page, slide_url: str, base_url: str) -> list[str]:
    """Visita una singola slide e cerca il video YouTube."""
    full_url = base_url + slide_url if slide_url.startswith("/") else slide_url
    try:
        page.goto(full_url, wait_until="domcontentloaded")
        time.sleep(0.8)
        content = page.content()
        return extract_youtube_ids(content)
    except Exception as e:
        print(f"  [!] Errore su {slide_url}: {e}")
        return []


def run_scraper(headless: bool = False, out_path: str = "data/videos.json"):
    Path("data").mkdir(exist_ok=True)
    base_url = "https://www.odoo.com"

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        print(f"[1/3] Apertura pagina tag: {ODOO_TAG_URL}")
        page.goto(ODOO_TAG_URL, wait_until="domcontentloaded")
        time.sleep(2)

        # Scroll per caricare tutti i contenuti lazy
        for _ in range(5):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(0.5)

        # Cerca ID YouTube direttamente nella pagina tag
        tag_page_ids = extract_youtube_ids(page.content())
        print(f"   → {len(tag_page_ids)} video trovati direttamente nella pagina tag")

        print("[2/3] Raccolta link ai corsi...")
        courses = scrape_course_urls(page)
        print(f"   → {len(courses)} corsi trovati")

        all_videos = []
        # Aggiungi video trovati direttamente nella pagina tag (senza corso associato)
        for vid_id in tag_page_ids:
            all_videos.append({
                "video_id": vid_id,
                "url": f"https://www.youtube.com/watch?v={vid_id}",
                "course_title": "Pagina tag principale",
                "course_url": ODOO_TAG_URL,
                "slide_url": None,
            })

        print("[3/3] Visita corsi e slide...")
        for i, course in enumerate(courses, 1):
            print(f"   [{i}/{len(courses)}] {course['title'][:60]}")
            try:
                ids_in_course, slide_urls = scrape_slide_pages(
                    page, course["url"], base_url
                )
                for vid_id in ids_in_course:
                    all_videos.append({
                        "video_id": vid_id,
                        "url": f"https://www.youtube.com/watch?v={vid_id}",
                        "course_title": course["title"],
                        "course_url": course["url"],
                        "slide_url": None,
                    })

                for j, slide_url in enumerate(slide_urls[:50]):  # max 50 slide per corso
                    print(f"      Slide {j+1}/{len(slide_urls[:50])}", end="\r")
                    ids_in_slide = scrape_single_slide(page, slide_url, base_url)
                    for vid_id in ids_in_slide:
                        all_videos.append({
                            "video_id": vid_id,
                            "url": f"https://www.youtube.com/watch?v={vid_id}",
                            "course_title": course["title"],
                            "course_url": course["url"],
                            "slide_url": slide_url,
                        })
            except Exception as e:
                print(f"   [!] Errore sul corso '{course['title']}': {e}")
            time.sleep(0.5)

        browser.close()

    # Deduplica per video_id mantenendo il primo trovato
    seen_ids = set()
    unique_videos = []
    for v in all_videos:
        if v["video_id"] not in seen_ids:
            unique_videos.append(v)
            seen_ids.add(v["video_id"])

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(unique_videos, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Trovati {len(unique_videos)} video unici → {out_path}")
    return unique_videos


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--out", default="data/videos.json")
    args = parser.parse_args()
    run_scraper(headless=args.headless, out_path=args.out)
