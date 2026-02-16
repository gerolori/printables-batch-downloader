import logging
import os
import time
import zipfile

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

LOGGER = logging.getLogger("printables_downloader")


def try_download_all_button(driver, wait):
    """
    Attempt to find and click the 'Download all files' button.
    
    This button is typically available for smaller model collections and downloads
    all files as a single zip archive.
    
    Args:
        driver: Selenium WebDriver instance.
        wait: WebDriverWait instance.
        
    Returns:
        True if the button was found and clicked, False otherwise.
    """
    download_all_xpaths = [
        "//button[contains(text(), 'Download all')]",
        "//button[contains(text(), 'Download All')]",
        "//a[contains(text(), 'Download all')]",
        "//button[contains(@class, 'download-all')]",
        "//button[contains(@data-testid, 'download-all')]",
    ]
    
    for xpath in download_all_xpaths:
        try:
            button = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
            driver.execute_script("arguments[0].scrollIntoView();", button)
            time.sleep(0.5)
            driver.execute_script("arguments[0].click();", button)
            LOGGER.info("Clicked 'Download all' button.")
            return True
        except Exception:
            continue
    
    LOGGER.debug("'Download all' button not found, will use individual downloads.")
    return False


def find_zip_file(download_dir, timeout=60):
    """
    Wait for a zip file to appear in the download directory.
    
    Args:
        download_dir: Directory to check for zip files.
        timeout: Maximum time to wait in seconds.
        
    Returns:
        Path to the zip file if found, None otherwise.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        for name in os.listdir(download_dir):
            if name.lower().endswith(".zip") and not name.lower().endswith(".part"):
                return os.path.join(download_dir, name)
        time.sleep(1)
    return None


def extract_and_cleanup_zip(download_dir, zip_path):
    """
    Extract a zip file to the download directory and delete the archive.
    
    Existing files with the same names will be overwritten.
    
    Args:
        download_dir: Directory to extract files to.
        zip_path: Path to the zip file.
        
    Returns:
        Number of files extracted.
    """
    extracted_count = 0
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for member in zf.namelist():
                if member.endswith('/'):
                    continue
                filename = os.path.basename(member)
                if not filename:
                    continue
                target_path = os.path.join(download_dir, filename)
                with zf.open(member) as source, open(target_path, 'wb') as target:
                    target.write(source.read())
                extracted_count += 1
        LOGGER.info("Extracted %s file(s) from zip archive.", extracted_count)
        
        os.remove(zip_path)
        LOGGER.info("Deleted zip archive: %s", os.path.basename(zip_path))
    except Exception as exc:
        LOGGER.warning("Error extracting zip file: %s", exc)
    
    return extracted_count
