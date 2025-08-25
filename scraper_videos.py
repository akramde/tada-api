import json
import asyncio
from playwright.async_api import async_playwright

BASE_URL = "https://kinovod240825.pro"

async def get_video_url(movie_url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(movie_url, timeout=60000)

        try:
            iframe_elem = await page.wait_for_selector("iframe", timeout=20000)
        except:
            await browser.close()
            return None

        iframe_url = await iframe_elem.get_attribute("src")

        iframe_page = await browser.new_page()
        await iframe_page.goto(iframe_url, timeout=60000)

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


async def main():
    # لاحقًا نقدر نقرأ من movies.json أو kids.json
    movies = [
        f"{BASE_URL}/film/240006-pampa",  # مثال فيلم واحد
    ]

    results = []
    for url in movies:
        print(f"🎬 Scraping {url} ...")
        video = await get_video_url(url)
        results.append({"url": url, "video": video})

    with open("video_links.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print("✅ Saved video_links.json")


if __name__ == "__main__":
    asyncio.run(main())
