"""Multi-threaded download backend shared by every DevCraft 'download' step.

Uses pypdl (installed by bootstrap alongside PyYAML) for parallel multi-segment
downloads, degrading to a single-connection pypdl download and finally to a
single-stream curl. Downloads are staged as '.downloading' and only renamed to
the final destination after Content-Length (curl tier) and all requested
MD5/SHA-256/SHA-512 checksums pass.
"""

import glob
import hashlib
import os
import subprocess
import sys
import time
import urllib.request

try:
    from pypdl import Pypdl
    PYPDl_AVAILABLE = True
except ImportError:
    PYPDl_AVAILABLE = False

DEFAULT_SEGMENTS = 8       # parallel connections for pypdl
PYPDl_RETRIES = 3          # retries inside one pypdl download
MAX_ATTEMPTS = 10          # whole-file attempts
ATTEMPT_RETRY_DELAY = 2    # seconds between whole-file attempts


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


def _http_head(url):
    """Return (content_length, accepts_byte_ranges) for the URL."""
    req = urllib.request.Request(url, method='HEAD')
    with urllib.request.urlopen(req, timeout=15) as resp:
        cl = resp.getheader('Content-Length') or resp.getheader('content-length')
        size = int(cl) if cl else None
        accept_ranges = resp.getheader('Accept-Ranges') or resp.getheader('accept-ranges') or ''
        return size, 'bytes' in accept_ranges.lower()


def _download_pypdl(url, downloading_file, segments):
    """Download via pypdl; segments=None requests a single connection."""
    # aiohttp advertises gzip by default and pypdl sizes its Range segments
    # from the compressed Content-Length, so force identity to keep the
    # segment math aligned with the bytes actually received
    result = Pypdl().start(
        url,
        file_path=downloading_file,
        multisegment=segments is not None,
        segments=segments or 1,
        retries=PYPDl_RETRIES,
        overwrite=True,
        display=sys.stdout.isatty(),  # built-in progress bar is ANSI-heavy; keep it off piped logs
        block=True,
        headers={"Accept-Encoding": "identity"})
    if not result or not os.path.isfile(downloading_file) or os.path.getsize(downloading_file) == 0:
        raise Exception("pypdl reported a failed download")


def _download_single_stream(url, downloading_file, need_auth=False):
    curl_cmd = [
        "curl",
        "--progress-bar",  # Show download progress
        "-L",              # Follow redirects
    ]

    if need_auth:
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        print(f"\nDownloading from {domain}")
        username = input("Username: ")
        curl_cmd.extend(["--user", f"{username}"])  # Curl will prompt for password

    curl_cmd.extend([
        "-o", downloading_file,  # Output file
        "-S",                    # Show error
        "--retry", "3",          # Retry up to 3 times
        "--retry-delay", "5",    # Wait 5 seconds between retries
        url
    ])
    # stderr is intentionally not captured so --progress-bar stays visible;
    # curl prints its own error message on failure.
    result = subprocess.run(curl_cmd, text=True)
    if result.returncode != 0:
        raise Exception(f"curl exited with code {result.returncode}")


def _verify_size(downloading_file, expected_size):
    file_size = os.path.getsize(downloading_file)
    if expected_size is None:
        if file_size == 0:
            raise Exception("Downloaded file is empty")
        return
    if file_size != expected_size:
        raise Exception(f"Downloaded file size {file_size} does not match expected size {expected_size}")


def _verify_hash(downloading_file, expected_hash, algorithm):
    """Verify one checksum; deletes the file and raises on mismatch."""
    expected_hash = expected_hash.strip().lower()
    print(f"Verifying {algorithm} checksum for {downloading_file}...")
    hasher = hashlib.new(algorithm)
    with open(downloading_file, 'rb') as fh:
        for chunk in iter(lambda: fh.read(8192), b''):
            hasher.update(chunk)
    actual_hash = hasher.hexdigest().lower()
    if actual_hash != expected_hash:
        # remove the corrupt download
        try:
            os.remove(downloading_file)
        except Exception:
            pass
        raise Exception(f"{algorithm} mismatch: expected {expected_hash}, got {actual_hash}")
    else:
        print(f"{algorithm} verification passed")


def _cleanup_staging(downloading_file):
    # remove the staged file plus any pypdl/curl segment temp files placed next to it
    for path in glob.glob(downloading_file + "*"):
        _remove(path)


def _download_via_curl(url, downloading_file, need_auth=False):
    expected_size = None
    try:
        expected_size, _ = _http_head(url)
    except Exception as e:
        print(f"Warning: could not determine remote Content-Length: {e}")
    _download_single_stream(url, downloading_file, need_auth)
    _verify_size(downloading_file, expected_size)


def _download_with_fallback(url, downloading_file, segments):
    """Multi-segment pypdl -> single-connection pypdl -> single-stream curl."""
    try:
        _download_pypdl(url, downloading_file, segments)
        return
    except Exception as e:
        print(f"Multi-segment download failed ({e}); retrying with a single connection")
        _cleanup_staging(downloading_file)
    try:
        _download_pypdl(url, downloading_file, None)
        return
    except Exception as e:
        print(f"pypdl download failed ({e}); falling back to curl")
        _cleanup_staging(downloading_file)
    _download_via_curl(url, downloading_file)


def download_file(url, dest,
                  expected_md5_hash=None, expected_sha256_hash=None, expected_sha512_hash=None,
                  need_auth=False, segments=DEFAULT_SEGMENTS,
                  max_attempts=MAX_ATTEMPTS):
    """Download url to dest, multi-threaded via pypdl when possible.

    The download is staged as dest + '.downloading' and only renamed to dest
    after Content-Length (curl tier) and all requested checksums pass.
    Raises when every attempt fails.
    """
    downloading_file = dest + ".downloading"
    last_err = None
    warned = False
    for attempt in range(1, max_attempts + 1):
        if attempt > 1:
            print(f"Running download attempt {attempt}/{max_attempts}...")
        print(f"Downloading... {url}")
        print(f"    to {dest}")

        try:
            if need_auth:
                # curl prompts for the password once; pypdl has no interactive auth
                _download_via_curl(url, downloading_file, need_auth=True)
            elif PYPDl_AVAILABLE:
                _download_with_fallback(url, downloading_file, segments)
            else:
                if not warned:
                    print("pypdl is not installed, falling back to single-stream curl; re-run bootstrap to install it")
                    warned = True
                _download_via_curl(url, downloading_file)
            if not expected_sha256_hash:
                print("No SHA-256 checksum provided, skipping verification.")
            if expected_md5_hash:
                _verify_hash(downloading_file, expected_md5_hash, 'MD5')
            if expected_sha256_hash:
                _verify_hash(downloading_file, expected_sha256_hash, 'SHA-256')
            if expected_sha512_hash:
                _verify_hash(downloading_file, expected_sha512_hash, 'SHA-512')
            os.replace(downloading_file, dest)
            print("\nDownload completed and verified.")
            return
        except Exception as e:
            last_err = e
            print(f"Download attempt {attempt} failed: {e}")
            # Remove partial files so the next attempt starts fresh instead of
            # resuming onto potentially corrupt data
            _cleanup_staging(downloading_file)
            if attempt < max_attempts:
                print("Retrying download...")
                time.sleep(ATTEMPT_RETRY_DELAY)

    raise Exception(f"Download command failed after {max_attempts} attempts: {last_err}")
