import os

from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from webdriver_manager.firefox import GeckoDriverManager


def build_driver(download_dir, headless):
    """
    Build and configure a Firefox WebDriver instance.
    
    Args:
        download_dir: Directory to save downloads to.
        headless: Run Firefox in headless mode.
        
    Returns:
        Configured Firefox WebDriver instance.
    """
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
