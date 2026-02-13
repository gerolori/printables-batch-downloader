# Printables Batch Downloader

Automates downloading files from a Printables model page using Selenium + Firefox. This is intended for personal use on models you are allowed to download.

## Disclosure / Use

The reason this script exists is for the limitations of big collections of items that make them impossible to download all in one click (as of now). This is not intended to be an exploit and will likely encounter rate limits pretty fast.

**Note on Rate Limits**: Printables has a batch download button for models with approximately 900+ files, but for models with 2000+ files, this button is not available. This script is necessary for downloading very large model collections that exceed the batch download threshold.

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

## Future Enhancements

### Batch Collection Downloader
A planned feature for data hoarding enthusiasts: the ability to download entire collections at once. This would be useful for maintaining essential models as backups in case of internet outages or remote site unavailability. You could periodically download all files from your "backup" collections to keep them updated with any new or modified files.

### Automatic Zip Extraction
When the "download all" button is available on Printables (typically for smaller model collections), the script could utilize this feature by:
- Clicking the "download all" button to download a single zip file
- Automatically extracting the zip to the correct folder structure
- Overriding files with the same names and adding new files when decompressing
- This would provide a faster alternative to individual file downloads when available
