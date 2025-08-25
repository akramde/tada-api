import sys
import json
import asyncio
import requests
from bs4 import BeautifulSoup
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTextEdit, QPushButton, QLabel, 
                             QProgressBar, QLineEdit, QFileDialog, QMessageBox,
                             QGroupBox, QSplitter, QListWidget)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from playwright.async_api import async_playwright

BASE_URL = "https://kinovod240825.pro"

class ScraperThread(QThread):
    update_log = pyqtSignal(str)
    update_progress = pyqtSignal(int)
    finished = pyqtSignal(list)
    
    def __init__(self, movie_urls, use_proxy=True):
        super().__init__()
        self.movie_urls = movie_urls
        self.use_proxy = use_proxy
        self.results = []
        self.working_proxy = None
        
    def run(self):
        self.update_log.emit("Starting scraping process...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.async_run())
        finally:
            loop.close()
    
    async def async_run(self):
        # Get proxies if needed
        if self.use_proxy:
            self.update_log.emit("Fetching Russian proxies...")
            proxies = self.get_russian_proxies()
            self.update_log.emit(f"Found {len(proxies)} Russian proxies")
            
            # Test proxies
            self.update_log.emit("Testing proxies...")
            for i, proxy in enumerate(proxies[:20]):
                self.update_progress.emit((i + 1) * 5)
                self.update_log.emit(f"Testing proxy {proxy}...")
                if self.test_proxy(proxy):
                    self.working_proxy = proxy
                    self.update_log.emit(f"✅ Using working proxy: {self.working_proxy}")
                    break
                
            if not self.working_proxy:
                self.update_log.emit("❌ No working RU proxy found, will try without proxy")
        
        # Scrape each movie
        self.results = []
        total = len(self.movie_urls)
        for i, url in enumerate(self.movie_urls):
            self.update_log.emit(f"🎬 Scraping {url} ...")
            self.update_progress.emit(100 * i // total)
            
            try:
                video = await self.get_video_url(url, self.working_proxy)
                self.results.append({"url": url, "video": video})
                self.update_log.emit(f"✅ Successfully extracted video URL: {video[:100] if video else 'None'}")
            except Exception as e:
                self.update_log.emit(f"❌ Error scraping {url}: {str(e)}")
                self.results.append({"url": url, "video": None})
        
        self.update_progress.emit(100)
        self.finished.emit(self.results)
    
    def get_russian_proxies(self):
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
            self.update_log.emit(f"Error fetching proxies: {str(e)}")
            return []
    
    def test_proxy(self, proxy, test_url="https://kinovod240825.pro/films"):
        try:
            resp = requests.get(test_url, proxies={"http": proxy, "https": proxy}, timeout=10)
            if resp.status_code == 200:
                return True
        except:
            pass
        return False
    
    async def get_video_url(self, movie_url, proxy=None):
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                proxy={"server": proxy} if proxy else None
            )
            page = await browser.new_page()

            try:
                await page.goto(movie_url, timeout=60000)
            except Exception as e:
                self.update_log.emit(f"❌ Failed to open page {movie_url}: {e}")
                await browser.close()
                return None

            # Try to find iframe
            try:
                iframe_elem = await page.wait_for_selector("iframe", timeout=20000)
                iframe_url = await iframe_elem.get_attribute("src")
                if not iframe_url:
                    self.update_log.emit("❌ iframe src is empty or blocked")
                    await browser.close()
                    return None
            except Exception as e:
                self.update_log.emit(f"❌ No iframe found or blocked: {e}")
                await browser.close()
                return None

            # Open iframe page
            try:
                iframe_page = await browser.new_page()
                await iframe_page.goto(iframe_url, timeout=60000)
            except Exception as e:
                self.update_log.emit(f"❌ Failed to open iframe page: {e}")
                await browser.close()
                return None

            # Try to click play button
            try:
                play_button = await iframe_page.query_selector("button, .play, .start")
                if play_button:
                    await play_button.click()
                    await asyncio.sleep(5)
            except:
                pass

            # Extract video URL
            video_url = None
            try:
                source_elem = await iframe_page.query_selector("video source")
                if source_elem:
                    video_url = await source_elem.get_attribute("src")
            except:
                pass

            if not video_url:
                # Try to find in JS scripts
                scripts = await iframe_page.query_selector_all("script")
                for s in scripts:
                    content = await s.inner_text()
                    if ".m3u8" in content or ".mp4" in content:
                        # Extract URL from script content
                        lines = content.split('\n')
                        for line in lines:
                            if ".m3u8" in line or ".mp4" in line:
                                parts = line.split('"')
                                for part in parts:
                                    if ".m3u8" in part or ".mp4" in part:
                                        video_url = part
                                        break
                                if video_url:
                                    break
                        if video_url:
                            break

            await browser.close()
            return video_url


class KinovodScraperApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kinovod Video Scraper")
        self.setGeometry(100, 100, 900, 700)
        
        # Central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Title
        title = QLabel("Kinovod Video URL Scraper")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # URL input section
        url_group = QGroupBox("Movie URLs (one per line)")
        url_layout = QVBoxLayout()
        self.url_input = QTextEdit()
        self.url_input.setPlaceholderText("Enter movie URLs here, one per line\nExample: https://kinovod240825.pro/film/240006-pampa")
        url_layout.addWidget(self.url_input)
        url_group.setLayout(url_layout)
        layout.addWidget(url_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        self.start_btn = QPushButton("Start Scraping")
        self.start_btn.clicked.connect(self.start_scraping)
        self.export_btn = QPushButton("Export Results")
        self.export_btn.clicked.connect(self.export_results)
        self.export_btn.setEnabled(False)
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self.clear_all)
        
        button_layout.addWidget(self.start_btn)
        button_layout.addWidget(self.export_btn)
        button_layout.addWidget(self.clear_btn)
        layout.addLayout(button_layout)
        
        # Proxy option
        proxy_layout = QHBoxLayout()
        proxy_layout.addWidget(QLabel("Use Russian proxies:"))
        self.proxy_checkbox = QLineEdit()
        self.proxy_checkbox.setPlaceholderText("Enabled by default")
        self.proxy_checkbox.setText("Yes")
        self.proxy_checkbox.setReadOnly(True)
        proxy_layout.addWidget(self.proxy_checkbox)
        proxy_layout.addStretch()
        layout.addLayout(proxy_layout)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)
        
        # Log output
        log_group = QGroupBox("Log Output")
        log_layout = QVBoxLayout()
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        log_layout.addWidget(self.log_output)
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        # Results section
        results_group = QGroupBox("Results")
        results_layout = QVBoxLayout()
        self.results_list = QListWidget()
        results_layout.addWidget(self.results_list)
        results_group.setLayout(results_layout)
        layout.addWidget(results_group)
        
        # Initialize variables
        self.scraper_thread = None
        self.results = []
        
        self.log("Welcome to Kinovod Video Scraper")
        self.log("Enter movie URLs and click 'Start Scraping' to begin")
    
    def log(self, message):
        self.log_output.append(message)
    
    def start_scraping(self):
        urls = self.url_input.toPlainText().strip().split('\n')
        if not urls or not urls[0]:
            QMessageBox.warning(self, "Input Error", "Please enter at least one movie URL")
            return
        
        # Filter out empty lines
        urls = [url.strip() for url in urls if url.strip()]
        
        self.start_btn.setEnabled(False)
        self.export_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.results_list.clear()
        self.log("Starting scraping process...")
        
        use_proxy = self.proxy_checkbox.text().lower() == "yes"
        self.scraper_thread = ScraperThread(urls, use_proxy)
        self.scraper_thread.update_log.connect(self.log)
        self.scraper_thread.update_progress.connect(self.progress_bar.setValue)
        self.scraper_thread.finished.connect(self.on_scraping_finished)
        self.scraper_thread.start()
    
    def on_scraping_finished(self, results):
        self.results = results
        self.start_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
        
        success_count = sum(1 for r in results if r['video'])
        self.log(f"Scraping completed! Successfully extracted {success_count} out of {len(results)} video URLs")
        
        # Display results in list
        for result in results:
            status = "✅" if result['video'] else "❌"
            self.results_list.addItem(f"{status} {result['url']}")
    
    def export_results(self):
        if not self.results:
            QMessageBox.warning(self, "Export Error", "No results to export")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Results", "video_links.json", "JSON Files (*.json)"
        )
        
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(self.results, f, ensure_ascii=False, indent=2)
                self.log(f"Results saved to {file_path}")
                QMessageBox.information(self, "Export Successful", f"Results saved to {file_path}")
            except Exception as e:
                self.log(f"Error saving file: {str(e)}")
                QMessageBox.critical(self, "Export Error", f"Error saving file: {str(e)}")
    
    def clear_all(self):
        self.url_input.clear()
        self.log_output.clear()
        self.results_list.clear()
        self.progress_bar.setValue(0)
        self.log("Cleared all inputs and results")
        self.results = []


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = KinovodScraperApp()
    window.show()
    sys.exit(app.exec_())
