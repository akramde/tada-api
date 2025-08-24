from requests_html import HTMLSession
from bs4 import BeautifulSoup
import json
import re
import asyncio
import time
import sys
import os

BASE_URL = "https://kinovod240825.pro"
START_PATH = "/films"

# إعداد session مع headers لتجنب الحظر
session = HTMLSession()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
})

async def ensure_chromium():
    try:
        from pyppeteer import launch
        # إعدادات خاصة لـ GitHub Actions
        browser = await launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--no-first-run',
                '--no-zygote',
                '--single-process',
                '--disable-gpu'
            ]
        )
        await browser.close()
        print("✅ Chromium configured successfully")
    except Exception as e:
        print(f"❌ Error setting up Chromium: {e}")
        sys.exit(1)

# تشغيل setup chromium مرة واحدة
try:
    asyncio.get_event_loop().run_until_complete(ensure_chromium())
except Exception as e:
    print(f"❌ Failed to setup Chromium: {e}")
    sys.exit(1)

def scrape_page(path):
    try:
        url = BASE_URL + path
        print(f"🔍 Scraping: {url}")
        
        # زيادة timeout للصفحات الثقيلة
        r = session.get(url, timeout=30)
        
        # render مع زيادة timeout
        r.html.render(sleep=5, timeout=30)
        
        soup = BeautifulSoup(r.html.html, "html.parser")
        movies = []

        items = soup.select("ul > li")
        print(f"📊 Found {len(items)} items on page")
        
        for item in items:
            try:
                link_tag = item.select_one("a")
                img = item.select_one("img.img-responsive")
                if not link_tag or not img:
                    continue

                poster_href = link_tag.get("href", "")
                if poster_href.startswith("/"):
                    poster_href = BASE_URL + poster_href

                poster_src = img.get("src", "")
                if poster_src and poster_src.startswith("/"):
                    poster_src = BASE_URL + poster_src

                title = link_tag.get_text(strip=True)
                if not title:
                    title = img.get("alt", "").strip()

                info_text = item.get_text(" ", strip=True)
                rating_match = re.search(r"\b\d+(\.\d+)?\b", info_text)
                rating = rating_match.group() if rating_match else "N/A"

                year_match = re.search(r"\b(19|20)\d{2}\b", info_text)
                year = year_match.group() if year_match else "N/A"

                label_tag = item.select_one(".label")
                label = label_tag.get_text(strip=True) if label_tag else "N/A"

                movies.append({
                    "poster_href": poster_href,
                    "poster_src": poster_src,
                    "label": label,
                    "title": title,
                    "rating": rating,
                    "year": year
                })
                
            except Exception as e:
                print(f"⚠️ Error processing item: {e}")
                continue

        next_link = soup.find("a", string=lambda s: s and "Следующая" in s)
        next_path = next_link.get("href") if next_link else None

        print(f"✅ Page scraped: {len(movies)} movies found")
        return movies, next_path
        
    except Exception as e:
        print(f"❌ Error scraping page {path}: {e}")
        return [], None

def scrape_all():
    path = START_PATH
    results = []
    page_count = 0
    max_pages = 10  # حد أقصى للصفحات لتجنب infinity loop
    
    while path and page_count < max_pages:
        try:
            movies, next_path = scrape_page(path)
            results.extend(movies)
            path = next_path
            page_count += 1
            print(f"📄 Page {page_count} completed. Total movies: {len(results)}")
            
            if path:
                time.sleep(2)  # زيادة وقت الانتظار بين الصفحات
                
        except Exception as e:
            print(f"❌ Error in scrape_all: {e}")
            break
    
    return results

if __name__ == "__main__":
    print("🚀 Starting movie scraping...")
    
    try:
        all_movies = scrape_all()
        
        # حفظ البيانات
        with open("movies.json", "w", encoding="utf-8") as f:
            json.dump(all_movies, f, ensure_ascii=False, indent=2)
        
        print(f"✅ Done! Total movies scraped: {len(all_movies)}")
        print(f"💾 Saved to movies.json")
        
        # التحقق من أن الملف تم إنشاؤه
        if os.path.exists("movies.json"):
            file_size = os.path.getsize("movies.json")
            print(f"📁 File size: {file_size} bytes")
        else:
            print("❌ movies.json file was not created!")
            sys.exit(1)
            
    except Exception as e:
        print(f"💥 Critical error: {e}")
        sys.exit(1)
