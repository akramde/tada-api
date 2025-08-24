from requests_html import HTMLSession
from bs4 import BeautifulSoup
import json
import re
import asyncio
import time

BASE_URL = "https://kinovod240825.pro"
START_PATH = "/films"

session = HTMLSession()

# تثبيت Chromium إذا لم يكن موجودًا
async def ensure_chromium():
    from pyppeteer import launch
    browser = await launch(headless=True, args=['--no-sandbox'])
    await browser.close()

asyncio.get_event_loop().run_until_complete(ensure_chromium())

def scrape_page(path):
    url = BASE_URL + path
    print(f"🔍 Scraping: {url}")
    r = session.get(url)
    r.html.render(sleep=3)  # تنفيذ جافاسكريبت وانتظار التحميل

    soup = BeautifulSoup(r.html.html, "html.parser")
    movies = []

    items = soup.select("ul > li")
    for item in items:
        link_tag = item.select_one("a")
        img = item.select_one("img.img-responsive")
        if not link_tag or not img:
            continue

        poster_href = link_tag.get("href")
        if poster_href.startswith("/"):
            poster_href = BASE_URL + poster_href

        poster_src = img.get("src")
        if poster_src.startswith("/"):
            poster_src = BASE_URL + poster_src

        title = link_tag.get_text(strip=True)
        if not title:
            title = img.get("alt", "").strip()

        info_text = item.get_text(" ", strip=True)
        rating_match = re.search(r"\b\d+(\.\d+)?\b", info_text)
        rating = rating_match.group() if rating_match else None

        year_match = re.search(r"\b(19|20)\d{2}\b", info_text)
        year = year_match.group() if year_match else None

        label_tag = item.select_one(".label")
        label = label_tag.get_text(strip=True) if label_tag else None

        movies.append({
            "poster href": poster_href,
            "img-responsive src": poster_src,
            "label": label,
            "title": title,
            "rating": rating,
            "year": year
        })

    next_link = soup.find("a", string=lambda s: s and "Следующая" in s)
    next_path = next_link.get("href") if next_link else None

    return movies, next_path

def scrape_all():
    path = START_PATH
    results = []
    while path:
        m, path = scrape_page(path)
        results.extend(m)
        time.sleep(1)
    return results

if __name__ == "__main__":
    all_movies = scrape_all()
    with open("movies.json", "w", encoding="utf-8") as f:
        json.dump(all_movies, f, ensure_ascii=False, indent=2)
    print(f"✅ Done! Total movies: {len(all_movies)}")
