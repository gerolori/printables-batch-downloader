# Printables Batch Downloader

Automates downloading files from a Printables model page using Selenium + Firefox. This is intended for personal use on models you are allowed to download.

## Disclosure / Use

- This script automates browser actions on Printables. Use it responsibly and comply with Printables terms, rate limits, and model licenses.
- You are responsible for ensuring you have permission to download and use each file.
- The script simulates clicks; it does not bypass paywalls or access restrictions.

## Requirements

- Python 3.9+
- Firefox installed
- Dependencies: `selenium`, `webdriver-manager`

Install dependencies:

```bash
pip install selenium webdriver-manager
```

## Usage

```bash
python script.py <PRINTABLES_MODEL_URL>
```

Optional flags:

```bash
python script.py <URL> \
  --download-dir "C:\\path\\to\\downloads" \
  --headless \
  --min-delay 0.5 \
  --max-delay 2.0 \
  --timeout 20 \
  --download-wait 120 \
  --retry-missing 1 \
  --verbose
```

Downloads go into a folder named after the model slug inside the base download directory.

## Pipeline (How it Works)

1. Build a download folder name from the URL slug.
2. Launch Firefox with a custom download directory and auto-save rules.
3. Open the model page and wait for the DOM to be ready.
4. Accept the cookie banner if it appears.
5. Expand any folder sections in the file tree.
6. Find all download buttons and click each one with a randomized delay.
7. Wait for active downloads to finish, then check for missing files by filename.
8. Optionally retry missing files based on filename matching.
9. Close the browser when complete.

## Notes

- If the page layout changes, the selectors may need updates.
- If downloads are blocked by a new content type, add it to the MIME list in the script.
- The missing-file check is best-effort and relies on page filename text.
- Retries may still fail if the page layout changes or filenames cannot be detected.
