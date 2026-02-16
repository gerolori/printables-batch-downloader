import logging
import os
import re
from datetime import datetime

from selenium.webdriver.common.by import By

LOGGER = logging.getLogger("printables_downloader")


def get_model_last_updated(driver):
    """
    Extract the 'last updated' timestamp from the model page.
    
    Looks for text like "updated February 5, 2026" in the model stats section.
    
    Args:
        driver: Selenium WebDriver instance.
        
    Returns:
        datetime object if found, None otherwise.
    """
    date_xpaths = [
        "//div[contains(@class, 'published-date')]//span",
        "//div[contains(@class, 'stats-item')]//span[contains(text(), 'updated')]",
        "//*[contains(text(), 'updated')]",
    ]
    
    for xpath in date_xpaths:
        try:
            elements = driver.find_elements(By.XPATH, xpath)
            for element in elements:
                text = element.text.strip()
                match = re.search(
                    r"updated\s+(\w+\s+\d{1,2},?\s+\d{4})",
                    text,
                    re.IGNORECASE
                )
                if match:
                    date_str = match.group(1).replace(",", "")
                    try:
                        return datetime.strptime(date_str, "%B %d %Y")
                    except ValueError:
                        continue
        except Exception:
            continue
    
    LOGGER.debug("Could not extract last updated date from page.")
    return None


def get_local_latest_modification(download_dir):
    """
    Get the modification time of the newest file in the download directory.
    
    Args:
        download_dir: Path to the download directory.
        
    Returns:
        datetime object of the newest file's modification time, or None if empty/missing.
    """
    if not os.path.exists(download_dir):
        return None
    
    latest_time = None
    for name in os.listdir(download_dir):
        filepath = os.path.join(download_dir, name)
        if os.path.isfile(filepath) and not name.lower().endswith(".part"):
            mtime = os.path.getmtime(filepath)
            if latest_time is None or mtime > latest_time:
                latest_time = mtime
    
    if latest_time is None:
        return None
    
    return datetime.fromtimestamp(latest_time)


def should_skip_download(driver, download_dir, force=False):
    """
    Determine if the download should be skipped based on timestamps.
    
    Compares the page's last update time with the newest local file's modification time.
    
    Args:
        driver: Selenium WebDriver instance.
        download_dir: Path to the model's download directory.
        force: If True, never skip (always download).
        
    Returns:
        True if download should be skipped, False otherwise.
    """
    import re
    
    if force:
        return False
    
    page_updated = get_model_last_updated(driver)
    if page_updated is None:
        LOGGER.debug("Could not determine page update time, will proceed with download.")
        return False
    
    local_latest = get_local_latest_modification(download_dir)
    if local_latest is None:
        LOGGER.debug("No local files found, will proceed with download.")
        return False
    
    if local_latest >= page_updated:
        LOGGER.info(
            "Skipping download: local files (%s) are up-to-date with page (%s).",
            local_latest.strftime("%Y-%m-%d"),
            page_updated.strftime("%Y-%m-%d"),
        )
        return True
    
    LOGGER.info(
        "Page was updated (%s) after local files (%s), will download.",
        page_updated.strftime("%Y-%m-%d"),
        local_latest.strftime("%Y-%m-%d"),
    )
    return False
