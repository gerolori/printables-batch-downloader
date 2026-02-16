import logging
import random
import re
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from printables.driver import build_driver
from printables.utils import try_accept_cookies, slug_from_url
from printables.downloader import download_stl_files

LOGGER = logging.getLogger("printables_downloader")

COLLECTION_SCROLL_PAUSE = 2
MAX_COLLECTION_SCROLLS = 50


def extract_model_urls_from_collection(driver, wait):
    """
    Extract all model URLs from a collection page by scrolling through infinite scroll.
    
    Args:
        driver: Selenium WebDriver instance.
        wait: WebDriverWait instance.
        
    Returns:
        List of model URLs found in the collection.
    """
    model_urls = set()
    last_height = driver.execute_script("return document.body.scrollHeight")
    scroll_count = 0
    
    while scroll_count < MAX_COLLECTION_SCROLLS:
        model_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/model/')]")
        for link in model_links:
            href = link.get_attribute("href")
            if href and re.search(r"/model/\d+", href):
                model_url = re.match(r"(https?://[^?#]+)", href)
                if model_url:
                    model_urls.add(model_url.group(1))
        
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(COLLECTION_SCROLL_PAUSE)
        
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            time.sleep(COLLECTION_SCROLL_PAUSE)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
        last_height = new_height
        scroll_count += 1
    
    LOGGER.info("Found %s model(s) in collection after %s scroll(s).", len(model_urls), scroll_count)
    return list(model_urls)


def download_collection(
    download_path,
    collection_url,
    headless=False,
    min_delay=0.5,
    max_delay=2.0,
    timeout=20,
    download_wait=120,
    retry_missing=0,
    force=False,
    no_zip=False,
):
    """
    Download all models from a Printables collection.
    
    Args:
        download_path: Base directory for downloads.
        collection_url: Printables collection URL.
        headless: Run Firefox in headless mode.
        min_delay: Minimum delay between downloads.
        max_delay: Maximum delay between downloads.
        timeout: Page load and wait timeout in seconds.
        download_wait: Wait time for downloads to finish.
        retry_missing: Number of retry passes for missing files.
        force: Force download even if local files appear up-to-date.
        no_zip: Disable automatic zip extraction.
    """
    driver = build_driver(download_path, headless)
    driver.set_page_load_timeout(timeout)
    wait = WebDriverWait(driver, timeout)
    
    try:
        LOGGER.info("Loading collection page: %s", collection_url)
        driver.get(collection_url)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        try_accept_cookies(driver, wait)
        time.sleep(2)
        
        model_urls = extract_model_urls_from_collection(driver, wait)
    finally:
        driver.quit()
    
    if not model_urls:
        LOGGER.warning("No models found in collection.")
        return
    
    LOGGER.info("Starting download of %s model(s) from collection.", len(model_urls))
    
    downloaded = 0
    skipped = 0
    for i, model_url in enumerate(model_urls, 1):
        LOGGER.info("Processing model %s/%s: %s", i, len(model_urls), model_url)
        try:
            result = download_stl_files(
                download_path,
                model_url,
                headless=headless,
                min_delay=min_delay,
                max_delay=max_delay,
                timeout=timeout,
                download_wait=download_wait,
                retry_missing=retry_missing,
                force=force,
                no_zip=no_zip,
            )
            if result:
                downloaded += 1
            else:
                skipped += 1
        except Exception as exc:
            LOGGER.error("Error downloading model %s: %s", model_url, exc)
        
        if i < len(model_urls):
            delay = random.uniform(min_delay * 2, max_delay * 2)
            LOGGER.info("Waiting %.2f seconds before next model...", delay)
            time.sleep(delay)
    
    LOGGER.info(
        "Collection download complete: %s downloaded, %s skipped (up-to-date).",
        downloaded,
        skipped,
    )
