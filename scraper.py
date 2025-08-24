import requests
from bs4 import BeautifulSoup
import json
import time

BASE_URL = "https://kinovod240825.pro"
START_PATH = "/films"

HEADERS = {"User-Agent": "Mozilla/5.0"}

def scrape_page(path):
    url = BASE_URL + path
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    movies = []

    items = soup.select("li")  # كل فيلم غالباً داخل <li>
    for item in items:
        link_tag = item.select_one("a")
        img = item.select_one("img.img-responsive")

        if not link_tag or not img:
            continue

        poster_href = BASE_URL + link_tag.get("href")
        poster_src = img.get("src")

        title = link_tag.get_text(strip=True)

        # التقييم والسنة (من النص بعد العنوان غالباً)
        info_text = item.get_text(" ", strip=True)
        rating, year = None, None
        parts = info_text.split()
        if parts:
            rating = parts[0] if parts[0].replace(".", "").isdigit() else None
            year = [p.strip(",") for p in parts if p.isdigit()]
            year = year[0] if year else None

        # label (إن وُجد)
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

    # استحصال رابط الصفحة التالية (Следующая)
    next_link = soup.find("a", string="Следующая")
    next_path = next_link.get("href") if next_link else None

    return movies, next_path

def scrape_all():
    path = START_PATH
    results = []
    while path:
        print(f"🔍 Scraping: {BASE_URL + path}")
        m, path = scrape_page(path)
        results.extend(m)
        time.sleep(1)
    return results

if __name__ == "__main__":
    all_movies = scrape_all()
    with open("movies.json", "w", encoding="utf-8") as f:
        json.dump(all_movies, f, ensure_ascii=False, indent=2)
    print(f"✅ Done! total: {len(all_movies)} movies.")
