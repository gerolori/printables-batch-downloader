"""
Printables Mass Downloader - Download models and collections from Printables.com
"""

from printables.cli import main
from printables.downloader import download_stl_files
from printables.collection import download_collection
from printables.utils import detect_url_type

__all__ = [
    "main",
    "download_stl_files",
    "download_collection",
    "detect_url_type",
]
