import argparse
import logging
import os
import random
import re
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.firefox import GeckoDriverManager

LOGGER = logging.getLogger("printables_downloader")
KNOWN_EXTENSIONS = ("stl", "3mf", "obj", "zip")


def _slug_from_url(url):
    parts = [p for p in url.split("/") if p]
    if not parts:
        return "printables-download"
    last = parts[-1]
    if re.match(r"^\d+-", last):
        tokens = last.split("-")[1:]
        return "-".join(tokens) or "printables-download"
    return last


def _build_driver(download_dir, headless):
    firefox_options = webdriver.FirefoxOptions()
    if headless:
        firefox_options.add_argument("-headless")
    firefox_options.set_preference("browser.download.folderList", 2)
    firefox_options.set_preference("browser.download.dir", os.path.abspath(download_dir))
    firefox_options.set_preference(
        "browser.helperApps.neverAsk.saveToDisk",
        "application/octet-stream,application/x-stl,model/stl,application/zip,application/x-zip-compressed",
    )

    service = Service(GeckoDriverManager().install())
    return webdriver.Firefox(service=service, options=firefox_options)


def _try_accept_cookies(driver, wait):
    cookie_xpaths = [
        "//button[contains(text(), 'I am OK with that')]",
        "//button[contains(text(), 'I agree')]",
        "//button[contains(text(), 'Accept')]",
    ]
    for xpath in cookie_xpaths:
        try:
            button = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
            button.click()
            time.sleep(1)
            return
        except Exception:
            continue
    LOGGER.info("Cookie banner not found or already accepted.")


def _expand_folders(driver, min_folder_delay=0.3, max_folder_delay=1.5):
    """
    Expand all folders in the file tree with randomized delays and verification.
    
    Args:
        driver: Selenium WebDriver instance
        min_folder_delay: Minimum delay between folder expansions (default: 0.3)
        max_folder_delay: Maximum delay between folder expansions (default: 1.5)
    """
    # Find all folder icons (both open and closed)
    folder_buttons = driver.find_elements(
        By.XPATH, "//i[contains(@class, 'fa-folder-open') or contains(@class, 'fa-folder')]"
    )
    
    expanded_count = 0
    for button in folder_buttons:
        try:
            # Check if folder is already open by checking for 'fa-folder-open' class
            classes = button.get_attribute("class") or ""
            is_already_open = "fa-folder-open" in classes
            
            if is_already_open:
                LOGGER.debug("Folder already expanded, skipping.")
                continue
            
            # Scroll into view and click
            driver.execute_script("arguments[0].scrollIntoView();", button)
            time.sleep(0.3)
            driver.execute_script("arguments[0].click();", button)
            
            # Wait for folder to expand and verify icon change
            max_retries = 5
            for retry in range(max_retries):
                time.sleep(0.2)
                # Re-fetch the element to get updated classes
                try:
                    current_classes = button.get_attribute("class") or ""
                    if "fa-folder-open" in current_classes:
                        LOGGER.debug("Folder expanded successfully (verified by icon change).")
                        expanded_count += 1
                        break
                except Exception:
                    # Element might be stale, break and continue to next folder
                    break
            else:
                LOGGER.warning("Folder may not have expanded correctly (icon didn't change).")
            
            # Random delay before next folder to avoid bot detection
            delay = random.uniform(min_folder_delay, max_folder_delay)
            LOGGER.debug("Waiting %.2f seconds before next folder...", delay)
            time.sleep(delay)
            
        except Exception as exc:
            LOGGER.warning("Error opening folder: %s", exc)
    
    LOGGER.info("Expanded %s folder(s).", expanded_count)


def _extract_name_from_button(button):
    try:
        container = button.find_element(By.XPATH, "ancestor::li[1]")
        text = container.text.strip()
    except Exception:
        return None

    if not text:
        return None

    match = re.search(
        r"([A-Za-z0-9 _\-\.]+\.(?:stl|3mf|obj|zip))",
        text,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[0] if lines else None


def _extract_expected_filenames(driver):
    buttons = driver.find_elements(By.XPATH, "//button[contains(@class, 'btn-download')]")
    expected = []
    for button in buttons:
        name = _extract_name_from_button(button)
        if name:
            expected.append(name)
    return expected


def _normalize_name(name):
    return re.sub(r"[^a-z0-9.]+", "", name.lower())


def _name_matches(expected_norm, actual_norm):
    return (
        expected_norm == actual_norm
        or expected_norm.startswith(actual_norm)
        or actual_norm.startswith(expected_norm)
    )


def _wait_for_downloads(download_dir, timeout):
    deadline = time.time() + timeout
    while time.time() < deadline:
        partials = [
            name
            for name in os.listdir(download_dir)
            if name.lower().endswith(".part")
        ]
        if not partials:
            return True
        time.sleep(1)
    return False


def _get_missing_names(download_dir, expected_names):
    if not expected_names:
        LOGGER.info("Skipping missing-file check (no filenames found on page).")
        return []

    downloaded = [
        name
        for name in os.listdir(download_dir)
        if os.path.isfile(os.path.join(download_dir, name))
        and not name.lower().endswith(".part")
    ]
    normalized_downloaded = [_normalize_name(name) for name in downloaded]

    missing = []
    for expected in expected_names:
        expected_norm = _normalize_name(expected)
        found = any(_name_matches(expected_norm, actual) for actual in normalized_downloaded)
        if not found:
            missing.append(expected)

    return missing


def _collect_button_indices_by_name(driver):
    buttons = driver.find_elements(By.XPATH, "//button[contains(@class, 'btn-download')]")
    index_map = {}
    for index, button in enumerate(buttons):
        name = _extract_name_from_button(button)
        if not name:
            continue
        normalized = _normalize_name(name)
        index_map.setdefault(normalized, []).append(index)
    return index_map


def download_stl_files(
    download_path,
    url,
    headless=False,
    min_delay=0.5,
    max_delay=2.0,
    timeout=20,
    download_wait=120,
    retry_missing=0,
):
    folder_name = _slug_from_url(url)
    full_download_path = os.path.join(download_path, folder_name)
    os.makedirs(full_download_path, exist_ok=True)

    driver = _build_driver(full_download_path, headless)
    driver.set_page_load_timeout(timeout)
    wait = WebDriverWait(driver, timeout)

    try:
        driver.get(url)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        _try_accept_cookies(driver, wait)
        _expand_folders(driver)
        time.sleep(2)

        expected_names = _extract_expected_filenames(driver)
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
            _wait_for_downloads(full_download_path, download_wait)
        missing = _get_missing_names(full_download_path, expected_names)

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
                index_map = _collect_button_indices_by_name(driver)

                for expected in list(missing):
                    expected_norm = _normalize_name(expected)
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
                    _wait_for_downloads(full_download_path, download_wait)

                missing = _get_missing_names(full_download_path, expected_names)
                if not missing:
                    LOGGER.info("All expected files appear to be downloaded after retries.")
                    break

            if missing:
                LOGGER.warning("Still missing %s file(s) after retries.", len(missing))

    finally:
        driver.quit()

def _parse_args(argv):
    parser = argparse.ArgumentParser(description="Mass-download STL files from a Printables model page.")
    parser.add_argument("url", help="Printables model URL")
    parser.add_argument(
        "--download-dir",
        default=os.path.join(os.path.expanduser("~"), "Downloads", "printables-mass-downloader"),
        help="Base directory for downloads",
    )
    parser.add_argument("--headless", action="store_true", help="Run Firefox in headless mode")
    parser.add_argument("--min-delay", type=float, default=0.5, help="Minimum delay between downloads")
    parser.add_argument("--max-delay", type=float, default=2.0, help="Maximum delay between downloads")
    parser.add_argument("--timeout", type=int, default=20, help="Page load and wait timeout in seconds")
    parser.add_argument(
        "--download-wait",
        type=int,
        default=3600,
        help="Wait time for downloads to finish before checking for missing files",
    )
    parser.add_argument(
        "--retry-missing",
        type=int,
        default=0,
        help="Number of retry passes for missing files",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    return parser.parse_args(argv)


def main(argv):
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    os.makedirs(args.download_dir, exist_ok=True)
    download_stl_files(
        args.download_dir,
        args.url,
        headless=args.headless,
        min_delay=args.min_delay,
        max_delay=args.max_delay,
        timeout=args.timeout,
        download_wait=args.download_wait,
        retry_missing=args.retry_missing,
    )


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))