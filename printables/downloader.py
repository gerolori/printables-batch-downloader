import logging
import os
import random
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from printables.driver import build_driver
from printables.utils import (
    slug_from_url,
    try_accept_cookies,
    expand_folders,
    extract_expected_filenames,
    wait_for_downloads,
    get_missing_names,
    collect_button_indices_by_name,
)
from printables.zip_handler import (
    try_download_all_button,
    find_zip_file,
    extract_and_cleanup_zip,
)
from printables.metadata import should_skip_download

LOGGER = logging.getLogger("printables_downloader")


def download_stl_files(
    download_path,
    url,
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
    Download files from a Printables model page.
    
    Args:
        download_path: Base directory for downloads.
        url: Printables model URL.
        headless: Run Firefox in headless mode.
        min_delay: Minimum delay between downloads.
        max_delay: Maximum delay between downloads.
        timeout: Page load and wait timeout in seconds.
        download_wait: Wait time for downloads to finish.
        retry_missing: Number of retry passes for missing files.
        force: Force download even if local files appear up-to-date.
        no_zip: Disable automatic zip extraction.
        
    Returns:
        True if download was performed, False if skipped.
    """
    folder_name = slug_from_url(url)
    full_download_path = os.path.join(download_path, folder_name)
    os.makedirs(full_download_path, exist_ok=True)

    driver = build_driver(full_download_path, headless)
    driver.set_page_load_timeout(timeout)
    wait = WebDriverWait(driver, timeout)

    try:
        driver.get(url)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        try_accept_cookies(driver, wait)
        
        if should_skip_download(driver, full_download_path, force):
            return False
        
        used_download_all = False
        if not no_zip:
            used_download_all = try_download_all_button(driver, wait)
            
            if used_download_all:
                LOGGER.info("Waiting for zip download (up to %s seconds)...", download_wait)
                wait_for_downloads(full_download_path, download_wait)
                
                zip_path = find_zip_file(full_download_path, timeout=30)
                if zip_path:
                    extract_and_cleanup_zip(full_download_path, zip_path)
                else:
                    LOGGER.warning("Zip file not found after 'Download all', falling back to individual downloads.")
                    used_download_all = False
        
        if not used_download_all:
            expand_folders(driver)
            time.sleep(2)

            expected_names = extract_expected_filenames(driver)
            download_buttons = driver.find_elements(By.XPATH, "//button[contains(@class, 'btn-download')]")
            LOGGER.info("Found %s files to download.", len(download_buttons))

            for index in range(len(download_buttons)):
                try:
                    buttons = driver.find_elements(By.XPATH, "//button[contains(@class, 'btn-download')]")
                    button = buttons[index]
                    driver.execute_script("arguments[0].scrollIntoView();", button)
                    time.sleep(0.5)
                    driver.execute_script("arguments[0].click();", button)

                    delay = random.uniform(min_delay, max_delay)
                    LOGGER.info(
                        "Downloading file %s/%s, waiting %.2f seconds...",
                        index + 1,
                        len(download_buttons),
                        delay,
                    )
                    time.sleep(delay)
                except Exception as exc:
                    LOGGER.warning("Error downloading file %s: %s", index + 1, exc)

            if download_wait:
                LOGGER.info("Waiting for downloads to finish (up to %s seconds)...", download_wait)
                wait_for_downloads(full_download_path, download_wait)
            missing = get_missing_names(full_download_path, expected_names)

            if missing:
                LOGGER.warning("Missing %s file(s) based on page filenames.", len(missing))
            else:
                LOGGER.info("All expected files appear to be downloaded.")

            if retry_missing and missing:
                for attempt in range(1, retry_missing + 1):
                    LOGGER.info(
                        "Retrying %s missing files (attempt %s/%s)...",
                        len(missing),
                        attempt,
                        retry_missing,
                    )
                    index_map = collect_button_indices_by_name(driver)

                    for expected in list(missing):
                        expected_norm = expected
                        indices = index_map.get(expected_norm)
                        if not indices:
                            continue
                        index = indices.pop(0)
                        try:
                            buttons = driver.find_elements(
                                By.XPATH, "//button[contains(@class, 'btn-download')]"
                            )
                            if index >= len(buttons):
                                continue
                            button = buttons[index]
                            driver.execute_script("arguments[0].scrollIntoView();", button)
                            time.sleep(0.5)
                            driver.execute_script("arguments[0].click();", button)

                            delay = random.uniform(min_delay, max_delay)
                            LOGGER.info("Retrying download, waiting %.2f seconds...", delay)
                            time.sleep(delay)
                        except Exception as exc:
                            LOGGER.warning("Error retrying download for %s: %s", expected, exc)

                    if download_wait:
                        LOGGER.info(
                            "Waiting for downloads to finish after retry (up to %s seconds)...",
                            download_wait,
                        )
                        wait_for_downloads(full_download_path, download_wait)

                    missing = get_missing_names(full_download_path, expected_names)
                    if not missing:
                        LOGGER.info("All expected files appear to be downloaded after retries.")
                        break

                if missing:
                    LOGGER.warning("Still missing %s file(s) after retries.", len(missing))
        
        return True

    finally:
        driver.quit()
