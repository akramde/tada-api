import json
import asyncio
import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import logging
import re
import time
from urllib.parse import urljoin, urlparse
import random

# إعداد التسجيل
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_URL = "https://kinovod240825.pro"

# ---------------- Russian Proxy System ---------------- #
def get_russian_proxies():
    """الحصول على بروكسيات روسية من مصادر متعددة"""
    proxies = []
    
    try:
        # المصدر 1: free-proxy-list.net
        url1 = "https://free-proxy-list.net/"
        resp1 = requests.get(url1, timeout=15)
        if resp1.status_code == 200:
            soup = BeautifulSoup(resp1.text, "html.parser")
            rows = soup.select("table tbody tr")
            for row in rows:
                cols = row.find_all("td")
                if len(cols) >= 7:
                    ip = cols[0].text.strip()
                    port = cols[1].text.strip()
                    code = cols[2].text.strip()
                    https = cols[6].text.strip()
                    if code == "RU" and https == "yes":
                        proxies.append(f"http://{ip}:{port}")
        
        logger.info(f"Found {len(proxies)} RU proxies from free-proxy-list")
    except Exception as e:
        logger.warning(f"Error getting proxies from free-proxy-list: {e}")
    
    try:
        # المصدر 2: proxy-list.download
        url2 = "https://www.proxy-list.download/api/v1/get?type=http&country=RU"
        resp2 = requests.get(url2, timeout=15)
        if resp2.status_code == 200:
            for line in resp2.text.split('\n'):
                line = line.strip()
                if line:
                    ip, port = line.split(':')
                    proxies.append(f"http://{ip}:{port}")
        
        logger.info(f"Total {len(proxies)} RU proxies after adding proxy-list.download")
    except Exception as e:
        logger.warning(f"Error getting proxies from proxy-list.download: {e}")
    
    try:
        # المصدر 3: proxyscrape.com
        url3 = "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=RU&ssl=all&anonymity=all"
        resp3 = requests.get(url3, timeout=15)
        if resp3.status_code == 200:
            for line in resp3.text.split('\n'):
                line = line.strip()
                if line and ':' in line:
                    ip, port = line.split(':')
                    proxies.append(f"http://{ip}:{port}")
        
        logger.info(f"Total {len(proxies)} RU proxies after adding proxyscrape")
    except Exception as e:
        logger.warning(f"Error getting proxies from proxyscrape: {e}")
    
    # إزالة التكرارات
    proxies = list(set(proxies))
    logger.info(f"Final unique RU proxies: {len(proxies)}")
    
    return proxies

async def test_proxy_async(proxy, test_url="https://kinovod240825.pro", timeout=10000):
    """اختبار البروكسي باستخدام Playwright"""
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(
                headless=True,
                proxy={"server": proxy},
                args=['--no-sandbox', '--disable-setuid-sandbox'],
                timeout=timeout
            )
            
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            page = await context.new_page()
            await page.goto(test_url, wait_until='domcontentloaded', timeout=timeout)
            
            # التحقق من أن الصفحة loaded بشكل صحيح
            title = await page.title()
            if title and "kinovod" in title.lower():
                logger.info(f"✅ Proxy {proxy} works - Title: {title}")
                await browser.close()
                return True
                
            await browser.close()
            return False
            
        except Exception as e:
            logger.debug(f"❌ Proxy {proxy} failed: {str(e)[:100]}")
            return False

async def get_working_proxies(proxies, max_tests=10):
    """الحصول على بروكسيات شغالة"""
    working_proxies = []
    test_tasks = []
    
    # اختبار عدد محدود من البروكسيات
    test_proxies = proxies[:max_tests]
    logger.info(f"Testing {len(test_proxies)} proxies...")
    
    for proxy in test_proxies:
        task = asyncio.create_task(test_proxy_async(proxy))
        test_tasks.append(task)
    
    results = await asyncio.gather(*test_tasks)
    
    for i, (proxy, works) in enumerate(zip(test_proxies, results)):
        if works:
            working_proxies.append(proxy)
            logger.info(f"✅ {i+1}. {proxy} - WORKING")
        else:
            logger.info(f"❌ {i+1}. {proxy} - FAILED")
    
    return working_proxies

# ---------------- Video Scraper Functions ---------------- #
async def solve_captcha_if_exists(page):
    """محاولة حل الـ CAPTCHA إذا ظهرت"""
    try:
        captcha_selectors = [
            '.captcha', '.g-recaptcha', '[class*="captcha"]',
            '[src*="captcha"]', 'iframe[src*="recaptcha"]', 'div[data-sitekey]'
        ]
        
        for selector in captcha_selectors:
            captcha_elements = await page.query_selector_all(selector)
            if captcha_elements:
                logger.warning("CAPTCHA detected! Trying to handle...")
                await page.wait_for_timeout(5000)
                return True
        return False
    except:
        return False

async def handle_advertisement(page):
    """التعامل مع النوافذ المنبثقة والإعلانات"""
    try:
        popup_selectors = [
            '.popup-close', '.close-button', '[aria-label*="close" i]',
            '[class*="close" i]', '[class*="dismiss" i]', '[class*="skip" i]'
        ]
        
        for selector in popup_selectors:
            try:
                close_buttons = await page.query_selector_all(selector)
                for button in close_buttons:
                    if await button.is_visible():
                        await button.click()
                        logger.info("Closed popup/advertisement")
                        await page.wait_for_timeout(1000)
            except:
                continue
        
        page.on("dialog", lambda dialog: dialog.dismiss())
        
    except Exception as e:
        logger.warning(f"Error handling advertisements: {e}")

async def click_play_button(page):
    """النقر على زر التشغيل"""
    play_selectors = [
        'button[class*="play"]', 'div[class*="play"]', 'a[class*="play"]',
        '.play-btn', '.player-play', '.start-button', '.video-play', '.btn-play',
        'button:has-text("Смотреть")', 'div:has-text("Смотреть")', 'a:has-text("Смотреть")',
        'button:has-text("Play")', 'div:has-text("Play")', 'a:has-text("Play")',
        'button:has-text("Watch")', 'div:has-text("Watch")', 'a:has-text("Watch")',
        'button:has-text("Start")', 'button:has-text("▶")', 'div:has-text("▶")'
    ]
    
    for selector in play_selectors:
        try:
            elements = await page.query_selector_all(selector)
            for element in elements:
                if await element.is_visible():
                    await element.click()
                    logger.info(f"Clicked play button: {selector}")
                    await page.wait_for_timeout(3000)
                    return True
        except:
            continue
    
    return False

async def extract_video_urls(page):
    """استخراج روابط الفيديو"""
    video_urls = []
    
    try:
        # من عناصر video
        video_elements = await page.query_selector_all('video')
        for video in video_elements:
            try:
                src = await video.get_attribute('src')
                if src and any(ext in src for ext in ['.mp4', '.m3u8', '.ts']):
                    video_urls.append(src)
                
                source_elements = await video.query_selector_all('source')
                for source in source_elements:
                    src = await source.get_attribute('src')
                    if src and any(ext in src for ext in ['.mp4', '.m3u8', '.ts']):
                        video_urls.append(src)
                        
            except:
                continue
        
        # من network requests
        network_urls = await page.evaluate("""() => {
            const performanceEntries = performance.getEntriesByType('resource');
            const videoUrls = [];
            const videoExtensions = ['.mp4', '.m3u8', '.ts', '.webm'];
            
            performanceEntries.forEach(entry => {
                if (videoExtensions.some(ext => entry.name.includes(ext))) {
                    videoUrls.push(entry.name);
                }
            });
            
            return videoUrls;
        }""")
        
        video_urls.extend(network_urls)
        
        # من scripts
        scripts = await page.query_selector_all('script')
        for script in scripts:
            try:
                content = await script.inner_text()
                if content:
                    patterns = [
                        r'(https?://[^\s<>"]+\.(mp4|m3u8|ts|webm)[^\s<>"]*)',
                        r'["\'](https?://[^"\']+\.(mp4|m3u8|ts|webm)[^"\']*)["\']',
                    ]
                    
                    for pattern in patterns:
                        matches = re.finditer(pattern, content, re.IGNORECASE)
                        for match in matches:
                            url = match.group(1) if len(match.groups()) > 0 else match.group(0)
                            if url and 'http' in url:
                                video_urls.append(url)
            except:
                continue
        
        return list(set(video_urls))
        
    except Exception as e:
        logger.error(f"Error extracting video URLs: {e}")
        return []

async def get_video_url(movie_url, proxy=None):
    """الحصول على رابط الفيديو باستخدام البروكسي"""
    async with async_playwright() as p:
        try:
            # إعداد المتصفح مع البروكسي
            launch_options = {
                'headless': True,
                'args': [
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu'
                ],
                'timeout': 60000
            }
            
            if proxy:
                launch_options['proxy'] = {'server': proxy}
                logger.info(f"Using proxy: {proxy}")
            
            browser = await p.chromium.launch(**launch_options)
            
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                java_script_enabled=True
            )
            
            page = await context.new_page()
            
            # الانتقال إلى صفحة الفيلم
            logger.info(f"Navigating to: {movie_url}")
            await page.goto(movie_url, wait_until='networkidle', timeout=60000)
            await page.wait_for_timeout(3000)
            
            # التعامل مع الإعلانات
            await handle_advertisement(page)
            await solve_captcha_if_exists(page)
            
            # النقر على زر التشغيل
            await click_play_button(page)
            
            # انتظار الفيديو
            await page.wait_for_timeout(8000)
            
            # استخراج روابط الفيديو
            video_urls = await extract_video_urls(page)
            
            await browser.close()
            
            # اختيار أفضل رابط
            best_url = None
            for url in video_urls:
                if url and any(ext in url for ext in ['.m3u8', '.mp4']):
                    best_url = url
                    break
            
            return best_url
            
        except Exception as e:
            logger.error(f"Error with proxy {proxy}: {e}")
            return None

# ---------------- Main Function ---------------- #
async def main():
    logger.info("Starting Kinovod scraper with Russian proxies...")
    
    # الحصول على البروكسيات الروسية
    logger.info("Fetching Russian proxies...")
    all_proxies = get_russian_proxies()
    
    if not all_proxies:
        logger.warning("No Russian proxies found! Continuing without proxy...")
        working_proxies = [None]
    else:
        logger.info(f"Testing {min(10, len(all_proxies))} proxies...")
        working_proxies = await get_working_proxies(all_proxies, max_tests=10)
        
        if not working_proxies:
            logger.warning("No working proxies found! Continuing without proxy...")
            working_proxies = [None]
        else:
            logger.info(f"Found {len(working_proxies)} working proxies")
    
    # قائمة الأفلام
    test_movies = [
        f"{BASE_URL}/film/240006-pampa",
        f"{BASE_URL}/film/239985-smotret-onlajn-besplatno-film-banderas-2024",
        f"{BASE_URL}/film/239984-smotret-onlajn-besplatno-film-vojna-i-mir-2024"
    ]
    
    results = []
    
    for movie_url in test_movies:
        logger.info(f"\n{'='*60}")
        logger.info(f"Scraping: {movie_url}")
        logger.info(f"{'='*60}")
        
        video_url = None
        used_proxy = None
        
        # تجربة كل بروكسي شغال
        for proxy in working_proxies:
            try:
                logger.info(f"Trying with proxy: {proxy if proxy else 'None'}")
                video_url = await get_video_url(movie_url, proxy)
                
                if video_url:
                    used_proxy = proxy
                    logger.info(f"✅ Success with proxy: {proxy}")
                    break
                else:
                    logger.warning(f"❌ Failed with proxy: {proxy}")
                    
            except Exception as e:
                logger.error(f"💥 Error with proxy {proxy}: {e}")
                continue
        
        results.append({
            "url": movie_url,
            "video": video_url,
            "proxy_used": used_proxy,
            "timestamp": time.time()
        })
        
        if video_url:
            logger.info(f"🎉 Found video URL: {video_url}")
        else:
            logger.warning("❌ No video URL found")
        
        await asyncio.sleep(2)
    
    # حفظ النتائج
    with open("video_links.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    logger.info("\n" + "="*70)
    logger.info("FINAL SCRAPING RESULTS:")
    logger.info("="*70)
    
    success_count = sum(1 for r in results if r.get("video"))
    for i, result in enumerate(results):
        status = "✅" if result.get("video") else "❌"
        proxy_info = result.get("proxy_used", "No proxy")
        logger.info(f"{status} {i+1}. {result['url']}")
        logger.info(f"   Proxy: {proxy_info}")
        if result.get("video"):
            logger.info(f"   Video: {result['video']}")
    
    logger.info(f"\n🎯 Success rate: {success_count}/{len(results)}")
    logger.info(f"📊 Working proxies: {len(working_proxies) if working_proxies[0] else 0}")

if __name__ == "__main__":
    asyncio.run(main())
