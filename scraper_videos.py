import json
import asyncio
import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import logging
import re
import time

# إعداد التسجيل
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_URL = "https://kinovod240825.pro"

# ---------------- Proxy ---------------- #
def get_russian_proxies():
    """الحصول على قائمة بروكسيات روسية"""
    try:
        url = "https://www.proxy-list.download/api/v1/get?type=http&country=RU"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        
        proxies = []
        for line in resp.text.split('\n'):
            line = line.strip()
            if line:
                proxies.append(f"http://{line}")
        
        logger.info(f"Found {len(proxies)} Russian proxies")
        return proxies
        
    except Exception as e:
        logger.error(f"Error fetching proxies: {e}")
        return []

def test_proxy(proxy, test_url="https://kinovod240825.pro"):
    """اختبار إذا كان البروكسي يعمل"""
    try:
        resp = requests.get(test_url, proxies={"http": proxy, "https": proxy}, 
                          timeout=10, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
        if resp.status_code == 200:
            return True
    except Exception as e:
        logger.debug(f"Proxy {proxy} failed: {e}")
    return False

# ---------------- Video Scraper ---------------- #
async def extract_video_from_page(page):
    """استخراج رابط الفيديو من الصفحة"""
    try:
        # الطريقة 1: البحث عن عناصر video مباشرة
        video_elements = await page.query_selector_all("video")
        for video in video_elements:
            src = await video.get_attribute("src")
            if src and (".mp4" in src or ".m3u8" in src):
                return src
            
            source_elements = await video.query_selector_all("source")
            for source in source_elements:
                src = await source.get_attribute("src")
                if src and (".mp4" in src or ".m3u8" in src):
                    return src
        
        # الطريقة 2: البحث في iframes
        iframes = await page.query_selector_all("iframe")
        for iframe in iframes:
            try:
                iframe_src = await iframe.get_attribute("src")
                if iframe_src and ("video" in iframe_src or "player" in iframe_src):
                    # الانتقال إلى الiframe
                    frame = await iframe.content_frame()
                    if frame:
                        video_in_frame = await extract_video_from_page(frame)
                        if video_in_frame:
                            return video_in_frame
            except:
                continue
        
        # الطريقة 3: البحث في النصوص البرمجية JavaScript
        scripts = await page.query_selector_all("script")
        for script in scripts:
            try:
                script_content = await script.inner_text()
                if script_content:
                    # البحث عن روابط الفيديو باستخدام regex
                    patterns = [
                        r'(https?://[^\s<>"]+\.(mp4|m3u8)[^\s<>"]*)',
                        r'src["\']?:\s*["\']([^"\']+\.(mp4|m3u8)[^"\']*)["\']',
                        r'file["\']?:\s*["\']([^"\']+\.(mp4|m3u8)[^"\']*)["\']',
                        r'video["\']?:\s*["\']([^"\']+\.(mp4|m3u8)[^"\']*)["\']'
                    ]
                    
                    for pattern in patterns:
                        matches = re.findall(pattern, script_content, re.IGNORECASE)
                        for match in matches:
                            if isinstance(match, tuple):
                                url = match[0]
                            else:
                                url = match
                            
                            if url and ("http" in url) and (".mp4" in url or ".m3u8" in url):
                                return url
            except:
                continue
        
        return None
        
    except Exception as e:
        logger.error(f"Error extracting video: {e}")
        return None

async def get_video_url(movie_url, proxy=None):
    """الحصول على رابط الفيديو من URL الفيلم"""
    async with async_playwright() as p:
        try:
            # إعداد المتصفح
            browser_args = [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-software-rasterizer',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor'
            ]
            
            browser = await p.chromium.launch(
                headless=True,
                args=browser_args,
                timeout=60000
            )
            
            # إعداد الصفحة
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            page = await context.new_page()
            
            # الانتقال إلى URL الفيلم
            logger.info(f"Navigating to: {movie_url}")
            await page.goto(movie_url, wait_until='networkidle', timeout=60000)
            
            # انتظار تحميل الصفحة
            await page.wait_for_timeout(5000)
            
            # البحث عن زر التشغيل والنقر عليه
            play_selectors = [
                'button[class*="play"]',
                'div[class*="play"]',
                'a[class*="play"]',
                '.play-btn',
                '.player-play',
                '.start-button',
                'button:has-text("Play")',
                'div:has-text("Play")',
                'a:has-text("Play")'
            ]
            
            for selector in play_selectors:
                try:
                    play_button = await page.query_selector(selector)
                    if play_button:
                        await play_button.click()
                        logger.info("Clicked play button")
                        await page.wait_for_timeout(3000)
                        break
                except:
                    continue
            
            # البحث عن روابط الفيديو
            logger.info("Searching for video sources...")
            video_url = await extract_video_from_page(page)
            
            if not video_url:
                # محاولة إيجاد iframes رئيسية
                iframes = await page.query_selector_all("iframe")
                for iframe in iframes:
                    try:
                        iframe_src = await iframe.get_attribute("src")
                        if iframe_src:
                            logger.info(f"Checking iframe: {iframe_src}")
                            # فتح الiframe في صفحة جديدة
                            iframe_page = await context.new_page()
                            await iframe_page.goto(iframe_src, wait_until='networkidle', timeout=30000)
                            await iframe_page.wait_for_timeout(3000)
                            
                            video_url = await extract_video_from_page(iframe_page)
                            await iframe_page.close()
                            
                            if video_url:
                                break
                    except Exception as e:
                        logger.warning(f"Error checking iframe: {e}")
                        continue
            
            await browser.close()
            
            if video_url:
                logger.info(f"Found video URL: {video_url}")
            else:
                logger.warning("Could not find video URL")
                
            return video_url
            
        except Exception as e:
            logger.error(f"Error in get_video_url: {e}")
            return None

# ---------------- Main ---------------- #
async def main():
    logger.info("Starting Kinovod scraper...")
    
    # اختيار عدم استخدام البروكسي مؤقتاً للاختبار
    working_proxy = None
    
    # قائمة الأفلام للاختبار
    test_movies = [
        f"{BASE_URL}/film/240006-pampa",
        f"{BASE_URL}/film/239985-smotret-onlajn-besplatno-film-banderas-2024",
        f"{BASE_URL}/film/239984-smotret-onlajn-besplatno-film-vojna-i-mir-2024"
    ]
    
    results = []
    for i, url in enumerate(test_movies):
        logger.info(f"Scraping {i+1}/{len(test_movies)}: {url}")
        try:
            video_url = await get_video_url(url, proxy=working_proxy)
            results.append({"url": url, "video": video_url})
            
            if video_url:
                logger.info(f"✅ Success: Found video URL")
            else:
                logger.warning("❌ Failed: No video URL found")
                
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            results.append({"url": url, "video": None})
        
        await asyncio.sleep(2)  # فترة انتظار بين الطلبات

    # حفظ النتائج
    with open("video_links.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    logger.info("Results saved to video_links.json")
    
    # عرض ملخص النتائج
    success_count = sum(1 for r in results if r["video"])
    logger.info(f"Scraping completed: {success_count}/{len(results)} successful")

if __name__ == "__main__":
    asyncio.run(main())
