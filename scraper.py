import requests
from bs4 import BeautifulSoup
import json
import re
import time
from datetime import datetime, timedelta

# حساب تاريخ البارحة وتحويله لصيغة ddmmyy
yesterday = datetime.now() - timedelta(days=1)
date_str = yesterday.strftime("%d%m%y")

# بناء الرابط الديناميكي
BASE_URL = f"https://kinovod{date_str}.pro"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/115.0 Safari/537.36"
}

def scrape_page(path):
    """Scrape a single page and return list of movies"""
    url = BASE_URL + path
    print(f"🔍 Scraping: {url}")
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    movies = []

    items = soup.select("ul > li")
    for item in items:
        link_tag = item.select_one("a")
        img = item.select_one("img.img-responsive")
        if not link_tag or not img:
            continue

        # رابط الفيلم الكامل
        poster_href = link_tag.get("href")
        if poster_href.startswith("/"):
            poster_href = BASE_URL + poster_href

        # رابط الصورة الكامل
        poster_src = img.get("src")
        if poster_src.startswith("/"):
            poster_src = BASE_URL + poster_src

        # العنوان
        title = link_tag.get_text(strip=True)
        if not title:
            title = img.get("alt", "").strip()

        # التقييم والسنة
        info_text = item.get_text(" ", strip=True)
        rating_match = re.search(r"\b\d+(\.\d+)?\b", info_text)
        rating = rating_match.group() if rating_match else None

        year_match = re.search(r"\b(19|20)\d{2}\b", info_text)
        year = year_match.group() if year_match else None

        # label (إن وجد)
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

    return movies

def scrape_all():
    """Scrape all pages using automatic page numbering until no movies found"""
    results = []
    page_num = 1

    while True:
        path = f"/films?page={page_num}"
        movies = scrape_page(path)

        if not movies:
            print(f"⚠️ No more movies found. Stopping at page {page_num}")
            break

        results.extend(movies)
        page_num += 1
        time.sleep(1)  # لتجنب الحظر

    return results

if __name__ == "__main__":
    all_movies = scrape_all()
    with open("videos.json", "w", encoding="utf-8") as f:
        json.dump(all_movies, f, ensure_ascii=False, indent=2)
    print(f"✅ Done! Total movies: {len(all_movies)} from {BASE_URL}")
