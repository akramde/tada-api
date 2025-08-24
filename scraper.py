import requests
from bs4 import BeautifulSoup
import json
import re
import time

BASE_URL = "https://kinovod240825.pro"
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
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    movies = []

    # غالبًا كل فيلم داخل <li>
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

        # التقييم والسنة باستخدام Regex
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

    # الرابط للصفحة التالية
    next_link = soup.find("a", string=lambda s: s and "Следующая" in s)
    next_path = next_link.get("href") if next_link else None

    return movies, next_path

def scrape_all():
    path = START_PATH
    results = []
    while path:
        try:
            m, path = scrape_page(path)
            results.extend(m)
            time.sleep(1)  # لتجنب الحظر
        except Exception as e:
            print(f"⚠️ Error scraping {path}: {e}")
            break
    return results

if __name__ == "__main__":
    all_movies = scrape_all()
    with open("movies.json", "w", encoding="utf-8") as f:
        json.dump(all_movies, f, ensure_ascii=False, indent=2)
    print(f"✅ Done! Total movies: {len(all_movies)}")
