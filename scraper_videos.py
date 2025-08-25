import json
import asyncio
import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import logging
import sys

# إعداد التسجيل
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_URL = "https://kinovod240825.pro"

# ---------------- Proxy ---------------- #
def get_russian_proxies():
    url = "https://free-proxy-list.net/"
    try:
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
    except Exception as e:
        logger.error(f"Error fetching proxies: {e}")
        return []

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
        # استخدام وضع headless بدون واجهة
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
        )
        page = await browser.new_page()

        try:
            await page.goto(movie_url, timeout=60000)
            logger.info(f"Successfully opened page: {movie_url}")
        except Exception as e:
            logger.error(f"Failed to open page {movie_url}: {e}")
            await browser.close()
            return None

        # محاولة إيجاد iframe
        try:
            iframe_elem = await page.wait_for_selector("iframe", timeout=20000)
            iframe_url = await iframe_elem.get_attribute("src")
            if not iframe_url:
                logger.error("iframe src is empty or blocked")
                await browser.close()
                return None
            logger.info(f"Found iframe with URL: {iframe_url}")
        except Exception as e:
            logger.error(f"No iframe found or blocked: {e}")
            await browser.close()
            return None

        # افتح iframe page
        try:
            iframe_page = await browser.new_page()
            await iframe_page.goto(iframe_url, timeout=60000)
            logger.info(f"Successfully opened iframe: {iframe_url}")
        except Exception as e:
            logger.error(f"Failed to open iframe page: {e}")
            await browser.close()
            return None

        # ---------------- تشغيل الفيديو ---------------- #
        try:
            # حاول الضغط على زر Play أو تجاوز الإعلان
            play_button = await iframe_page.query_selector("button, .play, .start")
            if play_button:
                await play_button.click()
                await asyncio.sleep(5)  # انتظر الفيديو يبدأ
                logger.info("Clicked play button")
        except Exception as e:
            logger.warning(f"Could not click play button: {e}")

        # ---------------- استخراج رابط الفيديو ---------------- #
        video_url = None
        try:
            source_elem = await iframe_page.query_selector("video source")
            if source_elem:
                video_url = await source_elem.get_attribute("src")
                logger.info(f"Found video URL in source element: {video_url}")
        except Exception as e:
            logger.warning(f"Error getting video source: {e}")

        if not video_url:
            # أحيانًا يكون في سكربت JS
            try:
                scripts = await iframe_page.query_selector_all("script")
                for s in scripts:
                    content = await s.inner_text()
                    if ".m3u8" in content or ".mp4" in content:
                        # استخراج الرابط من المحتوى
                        lines = content.split('\n')
                        for line in lines:
                            if ".m3u8" in line or ".mp4" in line:
                                # البحث عن الرابط في السطر
                                if 'http' in line:
                                    parts = line.split('"')
                                    for part in parts:
                                        if ("http" in part) and (".m3u8" in part or ".mp4" in part):
                                            video_url = part
                                            break
                                if video_url:
                                    break
                        if video_url:
                            logger.info(f"Found video URL in script: {video_url}")
                            break
            except Exception as e:
                logger.warning(f"Error searching scripts: {e}")

        await browser.close()
        return video_url

# ---------------- Main ---------------- #
async def main():
    logger.info("Starting Kinovod scraper...")
    
    # 1️⃣ احصل على بروكسي روسي شغال
    proxies = get_russian_proxies()
    logger.info(f"Found {len(proxies)} Russian proxies")
    
    working_proxy = None
    for i, proxy in enumerate(proxies[:10]):  # اختبر فقط أول 10 بروكسيات
        logger.info(f"Testing proxy {i+1}/10: {proxy}")
        if test_proxy(proxy):
            working_proxy = proxy
            logger.info(f"Using working proxy: {working_proxy}")
            break
    
    if not working_proxy:
        logger.warning("No working RU proxy found, will try without proxy")

    # 2️⃣ روابط الأفلام / المسلسلات
    movies = [
        f"{BASE_URL}/film/240006-pampa",  # مثال فيلم واحد
        # يمكن إضافة المزيد
    ]

    results = []
    for i, url in enumerate(movies):
        logger.info(f"Scraping {i+1}/{len(movies)}: {url}")
        try:
            video = await get_video_url(url, proxy=working_proxy)
            results.append({"url": url, "video": video})
            if video:
                logger.info(f"Successfully extracted video URL for {url}")
            else:
                logger.warning(f"Could not extract video URL for {url}")
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            results.append({"url": url, "video": None})

    # 3️⃣ حفظ النتائج
    with open("video_links.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    logger.info("Saved results to video_links.json")
    
    # عرض النتائج في السجل
    logger.info("Scraping completed. Results:")
    for result in results:
        status = "✅" if result["video"] else "❌"
        logger.info(f"{status} {result['url']}")
        if result["video"]:
            logger.info(f"   Video URL: {result['video']}")

if __name__ == "__main__":
    # تشغيل الكود غير المتزامن
    asyncio.run(main())
