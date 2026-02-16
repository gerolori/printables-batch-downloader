import logging
import os
import random
import re
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

LOGGER = logging.getLogger("printables_downloader")
KNOWN_EXTENSIONS = ("stl", "3mf", "obj", "zip")
FOLDER_EXPAND_MAX_RETRIES = 5


def detect_url_type(url):
    """
    Detect if the URL is a model page or a collection page.
    
    Returns:
        "model" - for model pages (e.g., /model/1583116-prusa-spool-bot)
        "collection" - for collection pages (e.g., /@user/collections/123)
        "unknown" - for unrecognized URLs
    """
    if re.search(r"/model/\d+", url):
        return "model"
    if re.search(r"/@[^/]+/collections/\d+", url):
        return "collection"
    return "unknown"


def slug_from_url(url):
    """
    Extract the model slug from a Printables URL.
    
    Args:
        url: Printables model URL.
        
    Returns:
        The slug portion of the URL.
    """
    parts = [p for p in url.split("/") if p]
    if not parts:
        return "printables-download"
    last = parts[-1]
    if re.match(r"^\d+-", last):
        tokens = last.split("-")[1:]
        return "-".join(tokens) or "printables-download"
    return last


def try_accept_cookies(driver, wait):
    """
    Try to accept cookies if a banner is present.
    
    Args:
        driver: Selenium WebDriver instance.
        wait: WebDriverWait instance.
    """
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


def expand_folders(driver, min_folder_delay=0.3, max_folder_delay=1.5):
    """
    Expand all folders in the file tree with randomized delays and verification.
    
    Args:
        driver: Selenium WebDriver instance.
        min_folder_delay: Minimum delay between folder expansions.
        max_folder_delay: Maximum delay between folder expansions.
    """
    folder_buttons = driver.find_elements(
        By.XPATH, "//i[contains(@class, 'fa-folder-open') or contains(@class, 'fa-folder')]"
    )
    
    expanded_count = 0
    for button in folder_buttons:
        try:
            classes = button.get_attribute("class") or ""
            is_already_open = "fa-folder-open" in classes
            
            if is_already_open:
                LOGGER.debug("Folder already expanded, skipping.")
                continue
            
            driver.execute_script("arguments[0].scrollIntoView();", button)
            time.sleep(0.3)
            driver.execute_script("arguments[0].click();", button)
            
            for retry in range(FOLDER_EXPAND_MAX_RETRIES):
                time.sleep(0.2)
                try:
                    current_classes = button.get_attribute("class") or ""
                    if "fa-folder-open" in current_classes:
                        LOGGER.debug("Folder expanded successfully (verified by icon change).")
                        expanded_count += 1
                        break
                except Exception:
                    break
            else:
                LOGGER.warning("Folder may not have expanded correctly (icon didn't change).")
            
            delay = random.uniform(min_folder_delay, max_folder_delay)
            LOGGER.debug("Waiting %.2f seconds before next folder...", delay)
            time.sleep(delay)
            
        except Exception as exc:
            LOGGER.warning("Error opening folder: %s", exc)
    
    LOGGER.info("Expanded %s folder(s).", expanded_count)


def extract_name_from_button(button):
    """
    Extract filename from a download button element.
    
    Args:
        button: Selenium WebElement for the download button.
        
    Returns:
        The filename if found, None otherwise.
    """
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


def extract_expected_filenames(driver):
    """
    Extract all expected filenames from download buttons on the page.
    
    Args:
        driver: Selenium WebDriver instance.
        
    Returns:
        List of filenames expected to be downloaded.
    """
    buttons = driver.find_elements(By.XPATH, "//button[contains(@class, 'btn-download')]")
    expected = []
    for button in buttons:
        name = extract_name_from_button(button)
        if name:
            expected.append(name)
    return expected


def normalize_name(name):
    """
    Normalize a filename for comparison purposes.
    
    Args:
        name: Filename to normalize.
        
    Returns:
        Normalized filename string.
    """
    return re.sub(r"[^a-z0-9.]+", "", name.lower())


def name_matches(expected_norm, actual_norm):
    """
    Check if normalized filenames match (with prefix tolerance).
    
    Args:
        expected_norm: Normalized expected filename.
        actual_norm: Normalized actual filename.
        
    Returns:
        True if names match, False otherwise.
    """
    return (
        expected_norm == actual_norm
        or expected_norm.startswith(actual_norm)
        or actual_norm.startswith(expected_norm)
    )


def wait_for_downloads(download_dir, timeout):
    """
    Wait for all downloads to complete.
    
    Args:
        download_dir: Directory to check for in-progress downloads.
        timeout: Maximum time to wait in seconds.
        
    Returns:
        True if all downloads finished, False if timeout.
    """
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


def get_missing_names(download_dir, expected_names):
    """
    Find filenames that are expected but not downloaded.
    
    Args:
        download_dir: Directory containing downloaded files.
        expected_names: List of expected filenames.
        
    Returns:
        List of missing filenames.
    """
    if not expected_names:
        LOGGER.info("Skipping missing-file check (no filenames found on page).")
        return []

    downloaded = [
        name
        for name in os.listdir(download_dir)
        if os.path.isfile(os.path.join(download_dir, name))
        and not name.lower().endswith(".part")
    ]
    normalized_downloaded = [normalize_name(name) for name in downloaded]

    missing = []
    for expected in expected_names:
        expected_norm = normalize_name(expected)
        found = any(name_matches(expected_norm, actual) for actual in normalized_downloaded)
        if not found:
            missing.append(expected)

    return missing


def collect_button_indices_by_name(driver):
    """
    Create a mapping of normalized filenames to button indices.
    
    Args:
        driver: Selenium WebDriver instance.
        
    Returns:
        Dictionary mapping normalized names to lists of indices.
    """
    buttons = driver.find_elements(By.XPATH, "//button[contains(@class, 'btn-download')]")
    index_map = {}
    for index, button in enumerate(buttons):
        name = extract_name_from_button(button)
        if not name:
            continue
        normalized = normalize_name(name)
        index_map.setdefault(normalized, []).append(index)
    return index_map
