import json
import asyncio
import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

BASE_URL = "https://kinovod240825.pro"

# ---------------- Proxy ---------------- #
def get_russian_proxies():
    url = "https://free-proxy-list.net/"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    proxies = []
    rows = soup.select("table tbody tr")
    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 7:
            continue
        ip = cols[0].text.strip()
        port = cols[1].text.strip()
        code = cols[2].text.strip()
        if code == "RU":
            proxies.append(f"http://{ip}:{port}")
    return proxies

def test_proxy(proxy, test_url="https://kinovod240825.pro/films"):
    try:
        resp = requests.get(test_url, proxies={"http": proxy, "https": proxy}, timeout=10)
        if resp.status_code == 200:
            return True
    except:
        pass
    return False

# ---------------- Video Scraper ---------------- #
async def get_video_url(movie_url, proxy=None):
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            proxy={"server": proxy} if proxy else None
        )
        page = await browser.new_page()

        try:
            await page.goto(movie_url, timeout=60000)
        except Exception as e:
            print(f"❌ Failed to open page {movie_url}: {e}")
            await browser.close()
            return None

        try:
            iframe_elem = await page.wait_for_selector("iframe", timeout=20000)
            iframe_url = await iframe_elem.get_attribute("src")
            if not iframe_url:
                print("❌ iframe src is empty or blocked")
                await browser.close()
                return None
        except Exception as e:
            print(f"❌ No iframe found or blocked: {e}")
            await browser.close()
            return None

        # افتح iframe page
        try:
            iframe_page = await browser.new_page()
            await iframe_page.goto(iframe_url, timeout=60000)
        except Exception as e:
            print(f"❌ Failed to open iframe page: {e}")
            await browser.close()
            return None

        video_url = None
        try:
            source_elem = await iframe_page.query_selector("video source")
            if source_elem:
                video_url = await source_elem.get_attribute("src")
        except:
            pass

        if not video_url:
            scripts = await iframe_page.query_selector_all("script")
            for s in scripts:
                content = await s.inner_text()
                if ".m3u8" in content or ".mp4" in content:
                    video_url = content
                    break

        await browser.close()
        return video_url

# ---------------- Main ---------------- #
async def main():
    # 1️⃣ احصل على بروكسي روسي شغال
    proxies = get_russian_proxies()
    print(f"🔍 Found {len(proxies)} Russian proxies")
    working_proxy = None
    for proxy in proxies[:20]:
        print(f"⚡ Testing proxy {proxy} ...")
        if test_proxy(proxy):
            working_proxy = proxy
            print(f"✅ Using working proxy: {working_proxy}")
            break
    if not working_proxy:
        print("❌ No working RU proxy found, will try without proxy")

    # 2️⃣ روابط الأفلام / المسلسلات
    movies = [
        f"{BASE_URL}/film/240006-pampa",  # مثال فيلم واحد
        # أضف المزيد من الروابط أو اقرأها من movies.json
    ]

    results = []
    for url in movies:
        print(f"🎬 Scraping {url} ...")
        try:
            video = await get_video_url(url, proxy=working_proxy)
            results.append({"url": url, "video": video})
        except Exception as e:
            print(f"❌ Error scraping {url}: {e}")
            results.append({"url": url, "video": None})

    # 3️⃣ حفظ النتائج
    with open("video_links.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("✅ Saved video_links.json")

if __name__ == "__main__":
    asyncio.run(main())
