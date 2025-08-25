import json
import asyncio
import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import logging
import re
import time
from urllib.parse import urljoin, urlparse

# إعداد التسجيل
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_URL = "https://kinovod240825.pro"

async def solve_captcha_if_exists(page):
    """محاولة حل الـ CAPTCHA إذا ظهرت"""
    try:
        # البحث عن عناصر الـ CAPTCHA الشائعة
        captcha_selectors = [
            '.captcha',
            '.g-recaptcha',
            '[class*="captcha"]',
            '[src*="captcha"]',
            'iframe[src*="recaptcha"]',
            'div[data-sitekey]'
        ]
        
        for selector in captcha_selectors:
            captcha_elements = await page.query_selector_all(selector)
            if captcha_elements:
                logger.warning("CAPTCHA detected! Trying to handle...")
                # يمكن إضافة منطق لحل الـ CAPTCHA هنا
                await page.wait_for_timeout(5000)
                return True
        return False
    except:
        return False

async def handle_advertisement(page):
    """التعامل مع النوافذ المنبثقة والإعلانات"""
    try:
        # إغلاق النوافذ المنبثقة
        popup_selectors = [
            '.popup-close',
            '.close-button',
            '[aria-label*="close" i]',
            '[class*="close" i]',
            '[class*="dismiss" i]',
            '[class*="skip" i]'
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
        
        # التعامل مع نوافذ alert
        page.on("dialog", lambda dialog: dialog.dismiss())
        
    except Exception as e:
        logger.warning(f"Error handling advertisements: {e}")

async def click_play_button(page):
    """النقر على زر التشغيل بطرق مختلفة"""
    play_attempted = False
    
    # قائمة بجميع أنواع أزرار التشغيل الممكنة
    play_selectors = [
        # أزرار التشغيل الشائعة
        'button[class*="play"]',
        'div[class*="play"]',
        'a[class*="play"]',
        'span[class*="play"]',
        '.play-btn',
        '.player-play',
        '.start-button',
        '.video-play',
        '.btn-play',
        
        # أزرار باللغة الروسية
        'button:has-text("Смотреть")',
        'div:has-text("Смотреть")',
        'a:has-text("Смотреть")',
        'button:has-text("Смотреть онлайн")',
        
        # أزرار بالإنجليزية
        'button:has-text("Play")',
        'div:has-text("Play")',
        'a:has-text("Play")',
        'button:has-text("Watch")',
        'div:has-text("Watch")',
        'a:has-text("Watch")',
        'button:has-text("Start")',
        
        # أزرار بالرموز
        'button:has-text("▶")',
        'div:has-text("▶")',
        
        # عناصر الفيديو نفسها
        'video',
        '.video-player',
        '.player-container'
    ]
    
    for selector in play_selectors:
        try:
            elements = await page.query_selector_all(selector)
            for element in elements:
                if await element.is_visible():
                    await element.click()
                    logger.info(f"Clicked play button: {selector}")
                    play_attempted = True
                    await page.wait_for_timeout(3000)
                    break
            if play_attempted:
                break
        except Exception as e:
            continue
    
    return play_attempted

async def wait_for_video_load(page, timeout=30000):
    """انتظار تحميل الفيديو"""
    try:
        # انتظار ظهور عناصر الفيديو
        await page.wait_for_selector('video', timeout=timeout)
        logger.info("Video element found")
        
        # انتظار حتى يبدأ الفيديو في التحميل
        await page.wait_for_function(
            """() => {
                const videos = document.querySelectorAll('video');
                return Array.from(videos).some(v => 
                    v.readyState > 0 || v.src || v.currentSrc
                );
            }""",
            timeout=timeout
        )
        logger.info("Video started loading")
        
        return True
    except:
        logger.warning("Video loading timeout")
        return False

async def extract_video_urls(page):
    """استخراج روابط الفيديو من الصفحة"""
    video_urls = []
    
    try:
        # الطريقة 1: من عناصر video مباشرة
        video_elements = await page.query_selector_all('video')
        for video in video_elements:
            try:
                # الحصول على src مباشرة
                src = await video.get_attribute('src')
                if src and any(ext in src for ext in ['.mp4', '.m3u8', '.ts']):
                    video_urls.append(src)
                
                # الحصول من source elements
                source_elements = await video.query_selector_all('source')
                for source in source_elements:
                    src = await source.get_attribute('src')
                    if src and any(ext in src for ext in ['.mp4', '.m3u8', '.ts']):
                        video_urls.append(src)
                
                # الحصول من currentSrc عبر JavaScript
                current_src = await page.evaluate('(element) => element.currentSrc', video)
                if current_src and any(ext in current_src for ext in ['.mp4', '.m3u8', '.ts']):
                    video_urls.append(current_src)
                    
            except:
                continue
        
        # الطريقة 2: البحث في الشبكة (network requests)
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
        
        # الطريقة 3: البحث في الـ scripts
        scripts = await page.query_selector_all('script')
        for script in scripts:
            try:
                content = await script.inner_text()
                if content:
                    # أنماط للبحث عن روابط الفيديو
                    patterns = [
                        r'(https?://[^\s<>"]+\.(mp4|m3u8|ts|webm)[^\s<>"]*)',
                        r'["\'](https?://[^"\']+\.(mp4|m3u8|ts|webm)[^"\']*)["\']',
                        r'(http[^\s<>"]*\.(mp4|m3u8|ts|webm)[^\s<>"]*)',
                        r'file["\']?:\s*["\']([^"\']+\.(mp4|m3u8|ts|webm)[^"\']*)',
                        r'src["\']?:\s*["\']([^"\']+\.(mp4|m3u8|ts|webm)[^"\']*)',
                        r'url["\']?:\s*["\']([^"\']+\.(mp4|m3u8|ts|webm)[^"\']*)'
                    ]
                    
                    for pattern in patterns:
                        matches = re.finditer(pattern, content, re.IGNORECASE)
                        for match in matches:
                            url = match.group(1) if len(match.groups()) > 0 else match.group(0)
                            if url and 'http' in url:
                                video_urls.append(url)
            except:
                continue
        
        # إزالة التكرارات
        video_urls = list(set(video_urls))
        
        # تصفية الروابط غير المرغوب فيها
        filtered_urls = []
        for url in video_urls:
            if not any(bad in url for bad in ['google', 'doubleclick', 'adservice', 'analytics']):
                filtered_urls.append(url)
        
        return filtered_urls
        
    except Exception as e:
        logger.error(f"Error extracting video URLs: {e}")
        return []

async def get_video_url(movie_url, proxy=None):
    """الحصول على رابط الفيديو الرئيسي"""
    async with async_playwright() as p:
        try:
            # إعداد المتصفح
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-software-rasterizer'
                ],
                timeout=60000
            )
            
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
            
            # التعامل مع الإعلانات والنوافذ المنبثقة
            await handle_advertisement(page)
            
            # محاولة حل الـ CAPTCHA إذا وجدت
            await solve_captcha_if_exists(page)
            
            # البحث والنقر على زر التشغيل
            play_clicked = await click_play_button(page)
            
            if not play_clicked:
                # إذا لم يتم العثور على زر تشغيل، جرب النقر على عناصر الفيديو
                try:
                    video_elements = await page.query_selector_all('video, .video-player, .player')
                    for video in video_elements:
                        if await video.is_visible():
                            await video.click()
                            logger.info("Clicked on video element")
                            await page.wait_for_timeout(2000)
                            break
                except:
                    pass
            
            # انتظار تحميل الفيديو
            await wait_for_video_load(page, timeout=15000)
            
            # إعطاء وقت للإعلان أن ينتهي
            await page.wait_for_timeout(5000)
            
            # استخراج روابط الفيديو
            video_urls = await extract_video_urls(page)
            
            await browser.close()
            
            # اختيار أفضل رابط فيديو
            best_url = None
            for url in video_urls:
                if url and any(ext in url for ext in ['.m3u8', '.mp4']):
                    best_url = url
                    break
            
            if best_url:
                logger.info(f"Found video URL: {best_url}")
            else:
                logger.warning("No video URL found")
                logger.info(f"All detected URLs: {video_urls}")
            
            return best_url
            
        except Exception as e:
            logger.error(f"Error in get_video_url: {e}")
            return None

async def main():
    logger.info("Starting advanced Kinovod scraper...")
    
    # قائمة الأفلام للاختبار
    test_movies = [
        f"{BASE_URL}/film/240006-pampa",
        f"{BASE_URL}/film/239985-smotret-onlajn-besplatno-film-banderas-2024",
        f"{BASE_URL}/film/239984-smotret-onlajn-besplatno-film-vojna-i-mir-2024"
    ]
    
    results = []
    for i, url in enumerate(test_movies):
        logger.info(f"\n{'='*50}")
        logger.info(f"Scraping {i+1}/{len(test_movies)}: {url}")
        logger.info(f"{'='*50}")
        
        try:
            start_time = time.time()
            video_url = await get_video_url(url)
            end_time = time.time()
            
            results.append({
                "url": url,
                "video": video_url,
                "time_taken": round(end_time - start_time, 2)
            })
            
            if video_url:
                logger.info(f"✅ SUCCESS: Found video URL in {end_time - start_time:.2f}s")
            else:
                logger.warning(f"❌ FAILED: No video URL found in {end_time - start_time:.2f}s")
                
        except Exception as e:
            logger.error(f"💥 ERROR scraping {url}: {e}")
            results.append({"url": url, "video": None, "error": str(e)})
        
        await asyncio.sleep(2)

    # حفظ النتائج
    with open("video_links.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    logger.info("\n" + "="*60)
    logger.info("FINAL RESULTS:")
    logger.info("="*60)
    
    success_count = sum(1 for r in results if r.get("video"))
    for i, result in enumerate(results):
        status = "✅" if result.get("video") else "❌"
        logger.info(f"{status} {i+1}. {result['url']}")
        if result.get("video"):
            logger.info(f"   📹 {result['video']}")
        if result.get("error"):
            logger.info(f"   ⚠️ Error: {result['error']}")
    
    logger.info(f"\n🎯 Success rate: {success_count}/{len(results)}")

if __name__ == "__main__":
    asyncio.run(main())
