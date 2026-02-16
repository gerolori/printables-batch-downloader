import argparse
import logging
import os
import sys

from printables.utils import detect_url_type
from printables.downloader import download_stl_files
from printables.collection import download_collection

LOGGER = logging.getLogger("printables_downloader")


def _parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Mass-download STL files from Printables model pages or collections."
    )
    parser.add_argument(
        "url",
        help="Printables model URL or collection URL",
    )
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
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force download even if local files appear up-to-date",
    )
    parser.add_argument(
        "--no-zip",
        action="store_true",
        help="Disable automatic zip extraction (always use individual downloads)",
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
    
    url_type = detect_url_type(args.url)
    
    if url_type == "collection":
        LOGGER.info("Detected collection URL, will download all models in collection.")
        download_collection(
            args.download_dir,
            args.url,
            headless=args.headless,
            min_delay=args.min_delay,
            max_delay=args.max_delay,
            timeout=args.timeout,
            download_wait=args.download_wait,
            retry_missing=args.retry_missing,
            force=args.force,
            no_zip=args.no_zip,
        )
    elif url_type == "model":
        LOGGER.info("Detected model URL, downloading single model.")
        download_stl_files(
            args.download_dir,
            args.url,
            headless=args.headless,
            min_delay=args.min_delay,
            max_delay=args.max_delay,
            timeout=args.timeout,
            download_wait=args.download_wait,
            retry_missing=args.retry_missing,
            force=args.force,
            no_zip=args.no_zip,
        )
    else:
        LOGGER.error(
            "Unrecognized URL format: %s. Expected a model URL (/model/...) or collection URL (/@.../collections/...).",
            args.url,
        )
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
