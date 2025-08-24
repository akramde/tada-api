import requests
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime, timedelta
import re

# 1️⃣ حساب تاريخ البارحة
yesterday = datetime.now() - timedelta(days=1)
dd = yesterday.strftime("%d")
mm = yesterday.strftime("%m")
yy = yesterday.strftime("%y")  # آخر رقمين من السنة

# 2️⃣ رابط الموقع ديناميكي حسب تاريخ البارحة
BASE_URL = f"https://kinovod{dd}{mm}{yy}.com"
START_PATH = "/films"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/115.0 Safari/537.36"
}

def scrape_page(path):
    url = BASE_URL + path
    print(f"🔍 Scraping: {url}")
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code != 200:
        print(f"⚠️ Failed to fetch page {url} (status code {resp.status_code})")
        return [], None

    soup = BeautifulSoup(resp.text, "html.parser")
    movies = []

    # تعديل CSS selector حسب HTML الحالي للموقع
    items = soup.select("li")  # غالبًا كل فيلم داخل <li>
    if not items:
        return [], soup

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
        rating = None
        year = None

        # استخراج التقييم
        rating_match = re.search(r"\b\d+(\.\d+)?\b", info_text)
        if rating_match:
            rating = rating_match.group()

        # استخراج السنة
        year_match = re.search(r"\b(19|20)\d{2}\b", info_text)
        if year_match:
            year = year_match.group()

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

    return movies, soup

def scrape_all():
    results = []
    page_num = 1

    while True:
        path = f"{START_PATH}?page={page_num}"
        movies, _ = scrape_page(path)

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
    print(f"✅ Done! Total movies: {len(all_movies)}")
