import os
import sys
import stat
import shutil
from pathlib import Path
import subprocess
import platform
import json
import hashlib
try:
    import yaml
except Exception:
    yaml = None
import configparser
import urllib.request
import datetime
import time
import zipfile
import tarfile
import copy
import heapq

class WorkspaceInstaller:
    def __init__(self):
        # Get the directory where this script is located
        self.m_dev_env_root_path = Path(__file__).parent.parent.absolute()
        self.m_configs_root_path = os.path.join(self.m_dev_env_root_path, "configs")
        self.m_workspace_root_path = os.path.join(self.m_dev_env_root_path, "workspace")
        self.m_download_root_path = os.path.join(self.m_dev_env_root_path, ".downloads")
        self.m_system_name = platform.system()
        self.m_summary_data = []
        self.m_run_started_at = datetime.datetime.now(datetime.UTC)
        self.m_current_config = None
        self.m_current_node = None
        self.m_current_install_step = None

    def build_failure_summary(self, error):
        """Build a compact failure summary for console output."""
        lines = ["Failure summary:"]
        lines.append(f"  Config: {self.m_current_config or 'N/A'}")
        lines.append(f"  Node: {self.m_current_node or 'N/A'}")
        lines.append(f"  Install step: {self.m_current_install_step or 'N/A'}")
        lines.append(f"  Error: {error}")
        return "\n".join(lines)

    def _record_config_summary(self, config_name, status, message=""):
        """Record per-config install result for final summary output."""
        sdk_name = config_name.split('/', 1)[0] if isinstance(config_name, str) and config_name else "N/A"
        self.m_summary_data.append({
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            "sdk": sdk_name,
            "config": config_name,
            "status": status,
            "message": message,
        })

    def build_run_summary(self, run_error=None):
        """Build a timestamped summary for the full install run."""
        run_finished_at = datetime.datetime.now(datetime.UTC)
        total_seconds = int((run_finished_at - self.m_run_started_at).total_seconds())
        total_count = len(self.m_summary_data)
        success_items = [item for item in self.m_summary_data if item.get("status") == "SUCCESS"]
        failed_items = [item for item in self.m_summary_data if item.get("status") == "FAILED"]

        lines = []
        lines.append("DevCraft Install Summary")
        lines.append(f"Started (UTC): {self.m_run_started_at.isoformat()}")
        lines.append(f"Finished (UTC): {run_finished_at.isoformat()}")
        lines.append(f"Duration (seconds): {total_seconds}")
        lines.append(f"Overall result: {'FAILED' if run_error else 'SUCCESS'}")
        lines.append(f"Configs processed: {total_count}")
        lines.append(f"Successful SDK installs: {len(success_items)}")
        lines.append(f"Failed SDK installs: {len(failed_items)}")

        lines.append("")
        lines.append("Successful installs:")
        if success_items:
            for item in success_items:
                lines.append(f"  - {item['sdk']} | {item['config']} | {item['timestamp']}")
        else:
            lines.append("  - None")

        lines.append("")
        lines.append("Failed installs:")
        if failed_items:
            for item in failed_items:
                fail_message = item.get("message") or "Unknown error"
                lines.append(f"  - {item['sdk']} | {item['config']} | {item['timestamp']} | {fail_message}")
        else:
            lines.append("  - None")

        if run_error:
            lines.append("")
            lines.append(self.build_failure_summary(run_error))

        return "\n".join(lines)

    def write_run_summary(self, summary_text):
        """Write the run summary to summary.txt in repository root."""
        summary_path = os.path.join(self.m_dev_env_root_path, "summary.txt")
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(summary_text)
            f.write("\n")
        return summary_path

    def run_command(self, command: str) -> str:
        """Run a Conan command and return its output."""
        try:
            result = subprocess.run(
                command,
                shell=True,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            print(f"Error running Conan command: {e.stderr}")
            raise
    
    def make_executable(self, path):
        mode = os.stat(path).st_mode
        mode |= (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        os.chmod(path, mode)

    def _formalize_path(self, path):
        """Formalize a path by replacing workspace/configs/download variables."""
        if not isinstance(path, str) or path == "":
            return path
        path = path.replace("${workspace}", self.m_workspace_root_path)
        path = path.replace("${configs}", self.m_configs_root_path)
        path = path.replace("${settings}", self.m_configs_root_path)
        path = path.replace("${download}", self.m_download_root_path)
        path = os.path.normpath(path)
        
        return path

    def _process_download(self, download_config, context):
        """Handle download node."""
        # download_config is the child node data: { src: {url, auth_required} or src_url, dest }
        
        # Handle src as either nested object or flat src_url
        if "src" in download_config and isinstance(download_config["src"], dict):
            src_url = download_config["src"]["url"]
            need_auth = download_config["src"].get("auth_required", False)
            expected_sha256_hash = download_config["src"].get("SHA-256", None)
            expected_sha512_hash = download_config["src"].get("SHA-512", None)
        
        downloading_file = self._formalize_path(download_config["dest"]) + ".downloading"
        downloaded_file = self._formalize_path(download_config["dest"])

        # Check if file already exists
        if os.path.exists(downloaded_file):
            file_size = os.path.getsize(downloaded_file)
            if file_size > 0:
                print(f"File already exists, skipping download: {downloaded_file}")
                return
            else:
                print(f"File exists but is empty, will re-download: {downloaded_file}")
                os.remove(downloaded_file)

        # Create directory for downloaded file
        os.makedirs(os.path.dirname(downloaded_file), exist_ok=True)

        # Download using curl with authentication
        print(f"Downloading... {src_url}")

        # Prepare curl command
        curl_cmd = [
            "curl",
            "--progress-bar",  # Show download progress
            "-L",  # Follow redirects
        ]

        # Add authentication if needed
        if need_auth:                    
            from urllib.parse import urlparse
            domain = urlparse(src_url).netloc
            print(f"\nDownloading from {domain}")
            
            username = input("Username: ")
            curl_cmd.extend(["--user", f"{username}"])  # Curl will prompt for password

        # Add output file specification
        curl_cmd.extend([
            "-o", downloading_file,  # Output file
            "-S",  # Show error
            "--retry", "3",  # Retry up to 3 times
            "--retry-delay", "5",  # Wait 5 seconds between retries
            src_url
        ])

        # Check size of the file when no SHA-256 provided.
        # Attempt to determine expected size via HTTP HEAD Content-Length header.
        expected_size = None
        try:
            req = urllib.request.Request(src_url, method='HEAD')
            with urllib.request.urlopen(req, timeout=10) as resp:
                cl = resp.getheader('Content-Length') or resp.getheader('content-length')
                if cl:
                    expected_size = int(cl)
        except Exception as e:
            print(f"Warning: could not determine remote Content-Length: {e}")

        # Execute curl and check result. Retry up to 3 times on failure.
        max_attempts = 10
        attempt = 1
        last_err = None
        while attempt < max_attempts:
            result = subprocess.run(curl_cmd, text=True, check=True)
            if result.returncode == 0:
                # success
                print("Download command succeeded")

                # get file_size from downloading file
                file_size = os.path.getsize(downloading_file)
                # If expected_size is unknown (server gave no Content-Length) accept any
                # non-empty file; otherwise require an exact size match.
                if expected_size is None and file_size > 0:
                    last_err = None
                    break
                elif file_size == expected_size:
                    last_err = None
                    break
                else:
                    last_err = f"Downloaded file size {file_size} does not match expected size {expected_size}"
            else:
                last_err = result.stderr.strip() or result.stdout.strip()
            
            print(f"Download attempt {attempt} failed: {last_err}")

            if attempt < max_attempts:
                print("Retrying download...")
                # Remove the partial file before retrying so curl starts fresh
                # instead of attempting a byte-range resume that some servers reject.
                if os.path.exists(downloading_file):
                    try:
                        os.remove(downloading_file)
                    except Exception:
                        pass
                time.sleep(2)
            attempt += 1
            print(f"Running download attempt {attempt}/{max_attempts}...")

        if last_err:
            raise Exception(f"Download command failed after {max_attempts} attempts: {last_err}")

        
        # Verify the downloaded file
        if not os.path.exists(downloading_file):
            raise Exception("Downloaded file does not exist")
        
        file_size = os.path.getsize(downloading_file)
        if file_size == 0:
            raise Exception("Downloaded file is empty")

        if not expected_sha256_hash:
            print("No SHA-256 checksum provided, skipping verification.")

        # If a SHA-256 checksum is provided in the config, verify it now.
        if expected_sha256_hash:
            expected_sha256_hash = expected_sha256_hash.strip().lower()
            print(f"Verifying SHA-256 checksum for {downloading_file}...")
            sha256 = hashlib.sha256()
            with open(downloading_file, 'rb') as fh:
                for chunk in iter(lambda: fh.read(8192), b''):
                    sha256.update(chunk)
            actual_hash = sha256.hexdigest().lower()
            if actual_hash != expected_sha256_hash:
                # remove the corrupt download
                try:
                    os.remove(downloading_file)
                except Exception:
                    pass
                raise Exception(f"SHA-256 mismatch: expected {expected_sha256_hash}, got {actual_hash}")
            else:
                print("SHA-256 verification passed")

        if expected_sha512_hash:
            expected_sha512_hash = expected_sha512_hash.strip().lower()
            print(f"Verifying SHA-512 checksum for {downloading_file}...")
            sha512 = hashlib.sha512()
            with open(downloading_file, 'rb') as fh:
                for chunk in iter(lambda: fh.read(8192), b''):
                    sha512.update(chunk)
            actual_hash = sha512.hexdigest().lower()
            if actual_hash != expected_sha512_hash:
                # remove the corrupt download
                try:
                    os.remove(downloading_file)
                except Exception:
                    pass
                raise Exception(f"SHA-512 mismatch: expected {expected_sha512_hash}, got {actual_hash}")
            else:
                print("SHA-512 verification passed")

        
        # Rename the downloading file to final name
        os.rename(downloading_file, downloaded_file)

        print("\nDownload completed and verified.")

    def _process_unzip_source(self, unzip_config, context):
        """Handle unzip node."""
        # unzip_config is the child node data: { src, src_sub_folder, dest }
        
        src_zip_file = self._formalize_path(unzip_config["src"])
        dest_folder = self._formalize_path(unzip_config["dest"])
        unzip_source = unzip_config.get("src_sub_folder", "")
        output_symbol_list = self._formalize_path(unzip_config.get("output_symbol_list", ""))

        if not src_zip_file:
            raise Exception("No source file specified for unzip")
        
        # Check if target folder already exists
        if os.path.exists(dest_folder) and os.path.isdir(dest_folder):
            # Check if folder has content
            if os.listdir(dest_folder):
                print(f"Target folder already exists and has content, skipping extraction: {dest_folder}")
                return
            else:
                print(f"Target folder exists but is empty, will extract: {dest_folder}")
        
        # Check file extension to determine archive type
        is_zip = src_zip_file.lower().endswith('.zip')
        is_tar_gz = src_zip_file.lower().endswith('.tar.gz')
        is_tar_xz = src_zip_file.lower().endswith('.tar.xz')

        if not (is_zip or is_tar_gz or is_tar_xz):
            raise Exception("Unsupported archive format. Only .zip, .tar.gz, and .tar.xz are supported")

        # Verify archive integrity
        try:
            if is_zip:
                with zipfile.ZipFile(src_zip_file, 'r') as test_zip:
                    if test_zip.testzip() is not None:
                        raise Exception("ZIP file is corrupted")
            else:  # tar.gz or tar.xz
                mode = "r:gz" if is_tar_gz else "r:xz"
                with tarfile.open(src_zip_file, mode) as test_tar:
                    test_tar.getmembers()
        except (zipfile.BadZipFile, tarfile.TarError) as e:
            raise Exception(f"Invalid archive file: {str(e)}")

        print(f"\nExtracting files to {dest_folder}...")

        def _extract_tar_with_symlinks_unresolved(tar_file_path, output_dir, source_sub_folder, symbol_list_output_path):
            with tarfile.open(tar_file_path, 'r:*') as tar_ref:
                all_members = tar_ref.getmembers()
                symlink_entries = []

                if source_sub_folder:
                    source_prefix = source_sub_folder.replace('\\', '/').rstrip('/')
                    members = [
                        m for m in all_members
                        if m.name.replace('\\', '/') == source_prefix
                        or m.name.replace('\\', '/').startswith(source_prefix + '/')
                    ]
                    base_dir_len = len(source_prefix) + 1
                else:
                    members = all_members
                    base_dir_len = 0

                total = len(members)

                for index, member in enumerate(members, 1):
                    member_to_extract = member
                    relative_name = member.name.replace('\\', '/')
                    if base_dir_len > 0:
                        new_member = copy.copy(member)
                        normalized_name = member.name.replace('\\', '/')
                        new_member.name = normalized_name[base_dir_len:]
                        if not new_member.name:
                            percent = (index * 100) // total
                            print(f"\rProgress: {percent}% [{index}/{total} files]", end="", flush=True)
                            continue
                        member_to_extract = new_member
                        relative_name = new_member.name.replace('\\', '/')

                    if member.issym() or member.islnk():
                        symlink_entries.append({
                            "path": relative_name,
                            "linkname": member.linkname.replace('\\', '/'),
                            "kind": "symlink" if member.issym() else "hardlink",
                        })

                    try:
                        tar_ref.extract(member_to_extract, output_dir)
                    except Exception as e:
                        # Keep going for environments where symlink creation is restricted.
                        print(f"\nWarning: could not extract {member.name}: {e}")

                    percent = (index * 100) // total
                    print(f"\rProgress: {percent}% [{index}/{total} files]", end="", flush=True)

                if symbol_list_output_path:
                    parent_dir = os.path.dirname(symbol_list_output_path)
                    if parent_dir:
                        os.makedirs(parent_dir, exist_ok=True)

                    symbol_payload = {
                        "source_archive": tar_file_path,
                        "generated_at": datetime.datetime.now(datetime.UTC).isoformat(),
                        "links": symlink_entries,
                    }
                    with open(symbol_list_output_path, 'w', encoding='utf-8') as sf:
                        json.dump(symbol_payload, sf, indent=2)
                    print(f"\nWrote symbol list: {symbol_list_output_path} ({len(symlink_entries)} entries)")
        
        if is_zip:
            with zipfile.ZipFile(src_zip_file, 'r') as zip_ref:
                # Get all members and filter by unzip_source if specified
                all_members = zip_ref.namelist()
                
                if unzip_source:
                    # Use unzip_source as the base directory
                    base_dir = unzip_source
                    # Ensure base_dir ends with / for proper prefix matching
                    if base_dir and not base_dir.endswith('/'):
                        base_dir_with_slash = base_dir + '/'
                    else:
                        base_dir_with_slash = base_dir
                    # Only extract files from the specified source folder
                    members = [m for m in all_members if m.startswith(base_dir_with_slash) or m == base_dir]
                    # Get the base directory to remove
                    base_dir_len = len(base_dir_with_slash)
                else:
                    members = all_members
                    base_dir_len = 0

                total = len(members)
                
                # Extract with progress
                for index, member in enumerate(members, 1):
                    if base_dir_len > 0:
                        # Remove the base directory prefix from the path
                        target_path = member[base_dir_len:]
                        if target_path:  # Skip if empty (was the base dir itself)
                            # Read the file content
                            file_data = zip_ref.read(member)
                            final_path = os.path.join(dest_folder, target_path)
                            
                            # Create parent directory if needed
                            os.makedirs(os.path.dirname(final_path), exist_ok=True)
                            
                            # Write the file directly to the target location
                            if not member.endswith('/'):
                                with open(final_path, 'wb') as f:
                                    f.write(file_data)
                    else:
                        zip_ref.extract(member, dest_folder)
                    percent = (index * 100) // total
                    print(f"\rProgress: {percent}% [{index}/{total} files]", end="", flush=True)
        else:  # tar.gz or tar.xz
            if self.m_system_name == "Windows":
                _extract_tar_with_symlinks_unresolved(src_zip_file, dest_folder, unzip_source, output_symbol_list)
                print("\nExtraction completed.")
                return

            mode = "r:gz" if is_tar_gz else "r:xz"
            with tarfile.open(src_zip_file, mode) as tar:
                # Get all members and filter by unzip_source if specified
                all_members = tar.getmembers()
                
                if unzip_source:
                    # Use unzip_source as the path filter
                    path_filter = unzip_source
                    # Only extract files from the specified path
                    members = [m for m in all_members if m.name.startswith(path_filter)]
                    # Remove the entire prefix
                    base_dir_len = len(unzip_source) + 1  # +1 for the slash
                else:
                    members = all_members
                    base_dir_len = 0

                total = len(members)
                
                # Extract with progress
                for index, member in enumerate(members, 1):
                    if base_dir_len > 0:
                        # Create a copy of the member to modify
                        new_member = copy.copy(member)
                        # Remove the prefix from the path
                        new_member.name = member.name[base_dir_len:]
                        if new_member.name:  # Skip if empty
                            tar.extract(new_member, dest_folder)
                    else:
                        tar.extract(member, dest_folder)
                    percent = (index * 100) // total
                    print(f"\rProgress: {percent}% [{index}/{total} files]", end="", flush=True)
        print("\nExtraction completed.")

    def _process_copy(self, copy_config, context):
        """Handle copy node."""
        # copy_config is the child node data: { src, dest }
        if not isinstance(copy_config, dict) or "src" not in copy_config or "dest" not in copy_config:
            return
        
        src_path = self._formalize_path(copy_config["src"])
        dest_path = self._formalize_path(copy_config["dest"])
        
        print(f"\nCopying files from {src_path} to {dest_path}...")
        
        if os.path.exists(src_path):
            
            if os.path.isdir(src_path):
                # Copy directory contents
                try:
                    # Create destination directory if it doesn't exist
                    os.makedirs(dest_path, exist_ok=True)
                    # Use copytree with dirs_exist_ok to allow overwriting
                    shutil.copytree(src_path, dest_path, dirs_exist_ok=True)
                    print(f"Successfully copied directory contents")
                except Exception as e:
                    print(f"Error copying directory: {e}")
                    raise
            else:
                # Copy single file
                try:
                    dest_file = dest_path
                    # create parent folder if not exists
                    os.makedirs(os.path.dirname(dest_file), exist_ok=True)
                    shutil.copy2(src_path, dest_file)
                    print(f"Successfully copied file")
                except Exception as e:
                    print(f"Error copying file: {e}")
                    raise
        else:
            print(f"Warning: Source path not found: {src_path}")

    def _process_resolve_symlinks(self, symlink_config, context):
        """Handle resolve_symlinks node.

        Expected format:
        resolve_symlinks:
          src: ${workspace}/path

        Recursively replaces symlinks under src with copies of their final targets.
        """
        if not isinstance(symlink_config, dict):
            return

        symbol_list_path = self._formalize_path(symlink_config.get("symbol_list", ""))
        src_path = self._formalize_path(symlink_config.get("src", ""))

        # If src is absent, derive root from the directory containing symbol_list.
        if not src_path and symbol_list_path:
            src_path = os.path.dirname(symbol_list_path)

        if not src_path or not os.path.exists(src_path):
            print(f"Warning: Source path not found for resolve_symlinks: {src_path}")
            return

        print(f"\nResolving symlinks under {src_path}...")

        max_depth = 10

        def _is_within_root(path, root):
            try:
                return os.path.commonpath([os.path.abspath(path), os.path.abspath(root)]) == os.path.abspath(root)
            except Exception:
                return False

        def _materialize_symbol_list(root_path, list_path):
            if not list_path:
                return

            if not os.path.exists(list_path):
                print(f"Warning: symbol_list file not found: {list_path}")
                return

            try:
                with open(list_path, 'r', encoding='utf-8') as sf:
                    symbol_data = json.load(sf)
            except Exception as e:
                print(f"Warning: failed to read symbol_list {list_path}: {e}")
                return

            if isinstance(symbol_data, dict):
                entries = symbol_data.get('links', [])
            elif isinstance(symbol_data, list):
                entries = symbol_data
            else:
                print(f"Warning: invalid symbol_list content in {list_path}")
                return

            created_count = 0
            skipped_count = 0

            # Filter to valid, parseable entries upfront
            pending = []
            for entry in entries:
                if not isinstance(entry, dict):
                    skipped_count += 1
                    continue
                rel_path = str(entry.get('path', '')).replace('\\', '/').strip()
                link_name = str(entry.get('linkname', '')).replace('\\', '/').strip()
                if not rel_path or not link_name:
                    skipped_count += 1
                    continue
                link_path = os.path.normpath(os.path.join(root_path, rel_path))
                if not _is_within_root(link_path, root_path):
                    print(f"Warning: skipped out-of-root link path: {rel_path}")
                    skipped_count += 1
                    continue
                if os.path.isabs(link_name):
                    target_path = os.path.normpath(os.path.join(root_path, link_name.lstrip('/\\')))
                else:
                    target_path = os.path.normpath(os.path.join(os.path.dirname(link_path), link_name))
                if not _is_within_root(target_path, root_path):
                    print(f"Warning: skipped out-of-root link target: {link_name}")
                    skipped_count += 1
                    continue
                pending.append((link_path, target_path))

            # Multi-pass: chained symlinks (A→B→C) need B materialized before A can be.
            max_passes = len(pending) + 1
            for _ in range(max_passes):
                if not pending:
                    break
                still_pending = []
                progress = False
                for link_path, target_path in pending:
                    # Already exists — nothing to do.
                    if os.path.lexists(link_path):
                        skipped_count += 1
                        progress = True
                        continue
                    if not os.path.exists(target_path):
                        still_pending.append((link_path, target_path))
                        continue
                    os.makedirs(os.path.dirname(link_path), exist_ok=True)
                    if os.path.isdir(target_path):
                        shutil.copytree(target_path, link_path, dirs_exist_ok=True)
                    else:
                        shutil.copy2(target_path, link_path)
                    created_count += 1
                    progress = True
                pending = still_pending
                if not progress:
                    break

            skipped_count += len(pending)

            print(f"  Symbol list materialization: created {created_count}, skipped {skipped_count}")

        _materialize_symbol_list(src_path, symbol_list_path)

        def collect_symlinks(root_path):
            symlink_paths = []
            if os.path.islink(root_path):
                symlink_paths.append(root_path)
                return symlink_paths
            if not os.path.isdir(root_path):
                return symlink_paths

            for entry in os.scandir(root_path):
                entry_path = entry.path
                if entry.is_symlink():
                    symlink_paths.append(entry_path)
                elif entry.is_dir(follow_symlinks=False):
                    symlink_paths.extend(collect_symlinks(entry_path))
            return symlink_paths

        dirty_paths = [src_path]

        for pass_index in range(1, max_depth + 1):
            symlink_paths = []
            seen_paths = set()
            for dirty_path in dirty_paths:
                if dirty_path in seen_paths:
                    continue
                seen_paths.add(dirty_path)
                symlink_paths.extend(collect_symlinks(dirty_path))

            if not symlink_paths:
                print(f"  No symlinks found on pass {pass_index}; done.")
                break

            print(f"  Pass {pass_index}: found {len(symlink_paths)} symlink(s)")
            resolved_count = 0
            next_dirty_paths = []

            for link_path in sorted(symlink_paths, key=lambda path: path.count(os.sep), reverse=True):
                if not os.path.lexists(link_path):
                    continue

                target_path = os.path.realpath(link_path)
                if not os.path.exists(target_path):
                    print(f"Warning: Broken symlink skipped: {link_path} -> {target_path}")
                    continue

                if os.path.isdir(link_path):
                    os.rmdir(link_path)
                    shutil.copytree(target_path, link_path)
                else:
                    os.unlink(link_path)
                    os.makedirs(os.path.dirname(link_path), exist_ok=True)
                    shutil.copy2(target_path, link_path)

                resolved_count += 1
                next_dirty_paths.append(link_path)
                print(f"  Resolved: {link_path}")

            if resolved_count == 0:
                print(f"  No symlinks resolved on pass {pass_index}; stopping.")
                break

            dirty_paths = next_dirty_paths
        else:
            remaining_symlinks = []
            seen_paths = set()
            for dirty_path in dirty_paths:
                if dirty_path in seen_paths:
                    continue
                seen_paths.add(dirty_path)
                remaining_symlinks.extend(collect_symlinks(dirty_path))
            if remaining_symlinks:
                print(f"Warning: resolve_symlinks reached max depth {max_depth} with {len(remaining_symlinks)} symlink(s) remaining")

    def _process_make_execute_permission(self, permission_config, context):
        """Handle make_execute_permission node."""
        # New expected form in YAML:
        # make_execute_permission:
        #   files:
        #     - ${workspace}/path/to/file_or_dir
        # The code keeps backward compatibility with the old form which was a simple
        # list of paths. Supports a single string, a list of strings, or a dict with
        # a 'files' key containing the list.

        # Normalize input into a list of path strings
        paths = []
        if isinstance(permission_config, dict):
            # look for 'files' key
            files_val = permission_config.get('files')
            if isinstance(files_val, list):
                paths = files_val
            else:
                # Nothing sensible to do
                raise TypeError("make_execute_permission 'files' key must be a list")
        else:
            raise TypeError("make_execute_permission must be a dict with 'files' key")

        print("\nSetting execute permissions...")
        for path_pattern in paths:
            # Replace workspace/configs/download variables
            path_pattern = self._formalize_path(path_pattern)

            if not path_pattern:
                continue

            if os.path.exists(path_pattern):
                # If it's a directory, walk it and set execute on files
                if os.path.isdir(path_pattern):
                    for root, dirs, files in os.walk(path_pattern):
                        # Ensure directories themselves are executable (useful for searching)
                        try:
                            self.make_executable(root)
                        except Exception:
                            pass
                        for filename in files:
                            file_path = os.path.join(root, filename)
                            try:
                                self.make_executable(file_path)
                            except Exception as e:
                                print(f"Warning: Could not set execute permission for {file_path}: {e}")
                    print(f"Set execute permissions for all files in: {path_pattern}")
                else:
                    # Single file: make it executable
                    try:
                        self.make_executable(path_pattern)
                        print(f"Set execute permission for: {path_pattern}")
                    except Exception as e:
                        print(f"Warning: Could not set execute permission for {path_pattern}: {e}")
            else:
                print(f"Warning: Path not found for execute permissions: {path_pattern}")

    def _process_environments(self, env_config, context):
        """Handle environments node."""
        
        print("\nSetting environment variables...")
        
        # Handle "set" environment variables
        if "set" in env_config and isinstance(env_config["set"], dict):
            for var_name, var_value in env_config["set"].items():
                # Replace variables in value
                var_value = self._formalize_path(var_value)
                # Set environment variable
                os.environ[var_name] = var_value
                print(f"  Set {var_name}={var_value}")
        
        # Handle "prepend" environment variables
        if "prepend" in env_config and isinstance(env_config["prepend"], list):
            for item_env in env_config["prepend"]:
                if isinstance(item_env, dict):
                    for var_name, var_value in item_env.items():
                        # Replace variables in value
                        var_value = self._formalize_path(var_value)
                        # Prepend to existing value
                        existing_value = os.environ.get(var_name, "")
                        if existing_value:
                            separator = ";" if self.m_system_name == "Windows" else ":"
                            os.environ[var_name] = f"{var_value}{separator}{existing_value}"
                        else:
                            os.environ[var_name] = var_value
                        print(f"  Prepended {var_name}={var_value}")

    def _process_execute(self, command_config, context):
        """Handle execute node."""
        print("\nExecuting installation command...")

        # Handle new object format: { command: [...], dest: "...", skip_if_exists: "..." }
        if isinstance(command_config, dict):
            # skip_if_exists: skip the command if the given path already exists
            skip_path = command_config.get("skip_if_exists", "")
            if skip_path:
                skip_path = self._formalize_path(skip_path)
                if os.path.exists(skip_path):
                    print(f"Skipping execute: '{skip_path}' already exists.")
                    return

            cmd_list = command_config.get("command", [])
            
            # Build command string from list, replacing variables
            command_parts = []
            for part in cmd_list:
                part = self._formalize_path(part)
                command_parts.append(part)
            
            command = " ".join(command_parts)
        # Handle old format: string or array
        elif isinstance(command_config, list):
            # If it's an array, join the parts with spaces
            command = " ".join(command_config)
            # Replace variables in the command
            command = self._formalize_path(command)
        elif isinstance(command_config, str):
            command = command_config
            # Replace variables in the command
            command = self._formalize_path(command)
        else:
            print("Warning: execute must be an object, string, or array")
            command = ""
        
        if command:
            # Execute the command
            try:
                print(f"Running command: {command}")
                subprocess.run(command, shell=True, check=True)
                print("Command executed successfully.")
            except subprocess.CalledProcessError as e:
                print(f"Error executing command: {e}")
                raise

    def _process_generator_active_batch(self, generator_active_batch, context):
        """Handle generator_active_batch node."""
        # generator_active_batch is the child node data: { file_path, environments }
        if "file_path" not in generator_active_batch or "environments" not in generator_active_batch:
            return
        
        # Process file path, replacing {workspace} with actual path
        file_path = self._formalize_path(generator_active_batch["file_path"])
        
        # Create the directory if it doesn't exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Prepare environment lists
        set_env_list = []
        prepend_env_list = []
        
        # Process set
        if "set" in generator_active_batch["environments"]:
            for var, value in generator_active_batch["environments"]["set"].items():
                # Replace workspace variable
                value = self._formalize_path(value)
                set_env_list.append((var, value))
        
        # Process prepend
        if "prepend" in generator_active_batch["environments"]:
            for item in generator_active_batch["environments"]["prepend"]:
                # Each item is a dictionary with a single key-value pair
                for var, value in item.items():
                    # Replace workspace variable
                    value = self._formalize_path(value)
                    prepend_env_list.append((var, value))
        
        # Generate the batch file
        self.generate_enviroment_set_batch_file(file_path, set_env_list, prepend_env_list)

    def _process_change_file_content(self, change_config, context):
        """Handle change_file_content node.

        Supported formats:
        - insert: insert a new line at 1-based line number
        - change: replace an existing line at 1-based line number (extend file if needed)

        Example:
        {
          "file_path": "${workspace}/path/to/file",
          "change": [ { "line": 55, "content": "..." } ],
          "insert": [ { "line": 60, "content": "..." } ]
        }

        Behavior:
        - Creates parent directory if missing.
        - If file doesn't exist, creates an empty file.
        - Applies 'change' operations first (replace), then 'insert' operations.
        - Line numbers are 1-based.
        """
        if not isinstance(change_config, dict):
            return

        file_path = change_config.get("file_path")
        inserts = change_config.get("insert", [])
        changes = change_config.get("change", [])

        if not file_path:
            print("Warning: change_file_content missing 'file_path'")
            return

        file_path = self._formalize_path(file_path)

        # Ensure parent directories exist
        parent = os.path.dirname(file_path)
        if parent:
            os.makedirs(parent, exist_ok=True)

        # Read existing lines (or start empty)
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        else:
            lines = []

        def _ensure_nl(s: str) -> str:
            return s if s.endswith('\n') else s + '\n'

        # Normalize and apply changes (replace specific lines)
        normalized_changes = []
        for item in changes:
            if not isinstance(item, dict):
                continue
            line_no = item.get('line')
            content = item.get('content', '')
            try:
                line_no = int(line_no)
            except Exception:
                continue
            # Expand variables in content
            content = self._formalize_path(content).replace('\\', '/')
            normalized_changes.append((line_no, content))

        normalized_changes.sort(key=lambda x: x[0])

        for line_no, content in normalized_changes:
            idx = max(0, line_no - 1)
            # If index beyond current length, extend with blank lines up to idx
            if idx >= len(lines):
                lines.extend(['\n'] * (idx - len(lines) + 1))

            # Replace the line at idx
            lines[idx] = _ensure_nl(self._formalize_path(content).replace('\\', '/'))

        # Normalize inserts: ensure list of dicts with line(int) and content(str)
        normalized_inserts = []
        for item in inserts:
            if not isinstance(item, dict):
                continue
            line_no = item.get('line')
            content = item.get('content', '')
            try:
                line_no = int(line_no)
            except Exception:
                continue
            # store as 1-based line numbers
            normalized_inserts.append((line_no, content))

        # Sort by line number ascending so earlier inserts don't offset later ones unexpectedly
        normalized_inserts.sort(key=lambda x: x[0])

        # Apply inserts with offset tracking
        offset = 0
        for line_no, content in normalized_inserts:
            idx = max(0, line_no - 1) + offset
            # If index beyond current length, extend with empty lines
            if idx > len(lines):
                lines.extend(['\n'] * (idx - len(lines)))

            lines.insert(idx, _ensure_nl(self._formalize_path(content).replace('\\', '/')))
            offset += 1

        # Write back
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)

        print(f"Modified file: {file_path}")

    def _process_install(self, install_node, context):
        # Define node handlers mapping (with context requirements)
        node_handlers = {
            'download': self._process_download,
            'unzip': self._process_unzip_source,
            'copy': self._process_copy,
            'resolve_symlinks': self._process_resolve_symlinks,
            'make_execute_permission': self._process_make_execute_permission,
            'change_file_content': self._process_change_file_content,
            'environments': self._process_environments,
            'execute': self._process_execute,
        }

        # Normalize install_node to an iterable list of (name, item) pairs.
        install_steps = []
        if isinstance(install_node, list):
            # new format: list of single-key mappings or multi-key mappings
            for entry in install_node:
                if not isinstance(entry, dict):
                    raise TypeError("each install entry must be an object")
                # multiple keys: treat each as its own install item
                for k, v in entry.items():
                    install_steps.append((k, v))
        else:
            raise TypeError("install node must be an object or an array")

        # Iterate over each install item
        for install_step_name, install_step in install_steps:
            # print(f"\n{'='*60}")
            print(f"Processing install item: '{install_step_name}'")
            # print(f"{'='*60}")
            self.m_current_install_step = install_step_name

            # Ensure install_item is a mapping
            if not isinstance(install_step, dict):
                raise TypeError(f"install item '{install_step_name}' must be an object")

            # Process nodes in order for this install item
            handler = node_handlers.get(install_step_name)
            if handler:
                # Special case: if the install_item_name matches a handler, process it directly
                try:
                    print(f"\nProcessing '{install_step_name}'...")
                    force_update = install_step.get("force_update", False)
                    dest_path = install_step.get("dest", None)
                    if dest_path:
                        dest_path = self._formalize_path(dest_path)
                        if os.path.exists(dest_path) and not force_update:
                            print(f"Destination already exists: {dest_path}")
                            print(f"Skipping install step: '{install_step_name}'")
                            continue
                    handler(install_step, context)
                except Exception as e:
                    raise Exception(f"Error processing '{install_step_name}': {e}") from e
                continue
            else:
                raise Exception(f"Unknown install item name: '{install_step_name}'")

    def _load_config_data(self, config_file_path):
        """Load one config file as YAML/JSON and return parsed object."""
        if not os.path.exists(config_file_path):
            raise FileNotFoundError(f"Configuration not found at {config_file_path}")

        config = None
        lower = config_file_path.lower()

        if lower.endswith('.yaml') or lower.endswith('.yml'):
            if yaml is not None:
                with open(config_file_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
            else:
                # PyYAML not available: try to read original JSON backup in same folder
                json_candidate = config_file_path[:-5] + '.json' if lower.endswith('.yaml') else config_file_path[:-4] + '.json'
                if os.path.exists(json_candidate):
                    with open(json_candidate, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                else:
                    # If not found, check the archived json_backup folder under configs/
                    try:
                        rel = os.path.relpath(config_file_path, self.m_configs_root_path)
                    except Exception:
                        rel = os.path.basename(config_file_path)

                    if rel.lower().endswith('.yaml'):
                        rel_json = rel[:-5] + '.json'
                    elif rel.lower().endswith('.yml'):
                        rel_json = rel[:-4] + '.json'
                    else:
                        rel_json = rel + '.json'

                    backup_candidate = os.path.join(self.m_configs_root_path, 'json_backup', rel_json)
                    if os.path.exists(backup_candidate):
                        with open(backup_candidate, 'r', encoding='utf-8') as f:
                            config = json.load(f)
                    else:
                        raise RuntimeError(
                            "YAML config provided but PyYAML is not installed and no JSON backup found: "
                            f"{config_file_path} (searched {json_candidate} and {backup_candidate})"
                        )
        else:
            with open(config_file_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

        if not isinstance(config, dict):
            raise TypeError(f"Config root must be an object in {config_file_path}")

        return config

    def _extract_dependencies(self, config_file_path, config):
        """Read and validate top-level dependencies list from config."""
        deps = config.get('dependencies', [])
        if deps is None:
            return []
        if not isinstance(deps, list):
            raise TypeError(f"'dependencies' must be a list in {config_file_path}")

        normalized = []
        for dep in deps:
            if not isinstance(dep, str):
                raise TypeError(f"All dependency entries must be strings in {config_file_path}")
            dep_text = dep.strip().replace('\\', '/')
            if dep_text:
                normalized.append(dep_text)

        return normalized

    def _resolve_dependency(self, dep_text, records_by_rel, records_by_basename, records_by_folder):
        """Resolve a dependency reference to a record key."""
        dep_norm = dep_text.strip().replace('\\', '/')

        configs_prefixes = ("${configs}/", "${settings}/")
        for configs_prefix in configs_prefixes:
            if dep_norm.startswith(configs_prefix):
                dep_norm = dep_norm[len(configs_prefix):]
                break

        # 1) Full relative path under configs, e.g. jdk/jdk_config.windows.yaml
        if dep_norm in records_by_rel:
            return dep_norm

        # 2) Basename match, e.g. jdk_config.windows.yaml
        by_base = records_by_basename.get(dep_norm, [])
        if len(by_base) == 1:
            return by_base[0]
        if len(by_base) > 1:
            raise RuntimeError(
                f"Ambiguous dependency '{dep_text}': matches multiple configs {by_base}. "
                "Use a configs-relative path like 'folder/file.windows.yaml'."
            )

        # 3) Folder key match, e.g. jdk
        by_folder = records_by_folder.get(dep_norm, [])
        if len(by_folder) == 1:
            return by_folder[0]
        if len(by_folder) > 1:
            raise RuntimeError(
                f"Ambiguous dependency '{dep_text}': folder maps to multiple configs {by_folder}."
            )

        raise RuntimeError(f"Unknown dependency '{dep_text}'")

    def install_from_config(self, config_file_path):
        """Generic installation function that handles downloading and extracting from configured URLs.
        Args:
            config_file_path (str): Path to the configuration JSON file
        """
        try:
            config = self._load_config_data(config_file_path)
        except json.JSONDecodeError:
            raise RuntimeError(f"Invalid JSON in configuration file: {config_file_path}")
        except Exception as e:
            raise RuntimeError(f"Unexpected error reading configuration '{config_file_path}': {e}") from e

        context = {
            'config': config
        }

        # Define config-level node handlers mapping
        config_handlers = {
            'install': self._process_install,
            'generator_active_batch': self._process_generator_active_batch,
        }
        
        # Process config nodes in order
        for node_name, handler in config_handlers.items():
            if node_name in config:
                self.m_current_node = node_name
                try:
                    print(f"\nProcessing '{node_name}' configuration...")
                    handler(config[node_name], context)
                except Exception as e:
                    raise RuntimeError(f"Error processing '{node_name}' configuration: {e}") from e

    def generate_enviroment_set_batch_file(self, output_file, set_env_list, prepend_env_list):
        # Assert the file_path has the correct extension for the current platform
        if self.m_system_name == "Windows":
            assert output_file.endswith(".bat"), \
                f"file_path must end with '.bat' on Windows, got: '{output_file}'"
        else:
            assert output_file.endswith(".sh"), \
                f"file_path must end with '.sh' on macOS/Linux, got: '{output_file}'"

        if self.m_system_name == "Windows":
            with open(output_file, 'w') as f:
                f.write("@echo off\n\n")
                f.write(":: Auto-generated environment setup script (Windows)\n")
                f.write(":: This script sets and appends environment variables\n\n")
                
                # Set commands (overwrite existing values)
                for var_name, value in set_env_list:
                    value = self._formalize_path(value)
                    f.write(f'set {var_name}={value}\n')
                
                if set_env_list and prepend_env_list:
                    f.write('\n')
                
                # Append commands
                for var_name, value in prepend_env_list:
                    value = self._formalize_path(value)
                    f.write(f'set {var_name}={value};%{var_name}%\n')
                
                f.write('\necho Environment variables set successfully\n')
        else:
            with open(output_file, 'w') as f:
                f.write("#!/bin/bash\n\n")
                f.write("# Auto-generated environment setup script\n")
                f.write("# This script sets and appends environment variables\n\n")
                
                # Write set commands (overwrite existing values)
                for var_name, value in set_env_list:
                    value = self._formalize_path(value)
                    f.write(f'export {var_name}="{value}"\n')
                
                if set_env_list and prepend_env_list:
                    f.write('\n')
                
                # Write append commands
                for var_name, value in prepend_env_list:
                    value = self._formalize_path(value)
                    f.write(f'export {var_name}="{value}:${var_name}"\n')
                
                f.write('\necho "Environment variables set successfully"\n')
        
        # Make the script executable
        import os
        os.chmod(output_file, 0o755)
        print(f"Bash script generated at: {output_file}")


    def install_all(self):
        # Determine the filename suffix for this platform's config files.
        suffix_map = {
            "Windows": ".windows.yaml",
            "Linux": ".linux.yaml",
            "Darwin": ".macos.yaml",
        }

        suffix = suffix_map.get(self.m_system_name)
        if not suffix:
            raise RuntimeError(f"Unsupported system: {self.m_system_name}")

        # Search only second-level folders under configs/ (e.g. configs/jdk/, configs/rustup/)
        config_files = []
        try:
            for entry in sorted(os.listdir(self.m_configs_root_path)):
                entry_path = os.path.join(self.m_configs_root_path, entry)
                if not os.path.isdir(entry_path):
                    # Only consider directories directly under configs/
                    continue

                # List files in this subdirectory (do NOT recurse deeper)
                for fname in sorted(os.listdir(entry_path)):
                    if fname.endswith(suffix):
                        config_files.append(os.path.join(entry_path, fname))
        except FileNotFoundError:
            raise RuntimeError(f"Configs directory not found: {self.m_configs_root_path}")

        if not config_files:
            raise RuntimeError(
                f"No configuration files found for system '{self.m_system_name}' in {self.m_configs_root_path}"
            )

        # Build dependency metadata for each config.
        records = {}
        records_by_basename = {}
        records_by_folder = {}

        for config_path in sorted(config_files):
            rel = os.path.relpath(config_path, self.m_configs_root_path).replace('\\', '/')
            folder_key = rel.split('/')[0] if '/' in rel else rel
            base_name = os.path.basename(config_path)

            try:
                config_data = self._load_config_data(config_path)
                dependencies = self._extract_dependencies(config_path, config_data)
            except Exception as e:
                raise RuntimeError(f"Error parsing dependencies in {config_path}: {e}") from e

            records[rel] = {
                'path': config_path,
                'rel': rel,
                'folder': folder_key,
                'base': base_name,
                'deps': dependencies,
            }

            records_by_basename.setdefault(base_name, []).append(rel)
            records_by_folder.setdefault(folder_key, []).append(rel)

        # Build graph edges dependency -> dependent.
        indegree = {k: 0 for k in records}
        adjacency = {k: set() for k in records}

        for rel, record in records.items():
            for dep_text in record['deps']:
                try:
                    dep_rel = self._resolve_dependency(
                        dep_text,
                        records,
                        records_by_basename,
                        records_by_folder,
                    )
                except Exception as e:
                    raise RuntimeError(f"Error resolving dependency for {rel}: {e}") from e

                if dep_rel == rel:
                    raise RuntimeError(f"Self dependency detected for {rel}")

                if rel not in adjacency[dep_rel]:
                    adjacency[dep_rel].add(rel)
                    indegree[rel] += 1

        # Topological sort with deterministic ordering.
        heap = []
        for rel, deg in indegree.items():
            if deg == 0:
                heapq.heappush(heap, rel)

        ordered = []
        while heap:
            node = heapq.heappop(heap)
            ordered.append(node)
            for nxt in sorted(adjacency[node]):
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    heapq.heappush(heap, nxt)

        if len(ordered) != len(records):
            cycle_nodes = sorted([k for k, deg in indegree.items() if deg > 0])
            cycle_text = "\n".join([f"  - {node}" for node in cycle_nodes])
            raise RuntimeError(f"Cyclic dependency detected among config files:\n{cycle_text}")

        print("\nResolved config execution order:")
        for index, rel in enumerate(ordered, 1):
            print(f"  {index}. {rel}")

        # Process each config file in dependency order.
        for rel in ordered:
            config_path = records[rel]['path']
            # Friendly display: show path relative to configs folder
            try:
                display_name = os.path.relpath(config_path, self.m_configs_root_path)
            except Exception:
                display_name = os.path.basename(config_path)

            print(f"\n{'='*70}")
            print(f"Processing config: {display_name}")
            print(f"{'='*70}")
            self.m_current_config = display_name
            self.m_current_node = None
            self.m_current_install_step = None
            try:
                self.install_from_config(config_path)
                self._record_config_summary(display_name, "SUCCESS")
            except Exception as e:
                self._record_config_summary(display_name, "FAILED", str(e))
                raise

def main():
    dev_env_installer = WorkspaceInstaller()
    run_error = None
    try:
        dev_env_installer.install_all()
    except Exception as e:
        run_error = e

    summary_text = dev_env_installer.build_run_summary(run_error)
    summary_path = dev_env_installer.write_run_summary(summary_text)
    print("\n" + summary_text)
    print(f"Summary written to: {summary_path}")

    if run_error:
        print(f"Install failed: {run_error}", file=sys.stderr)
        sys.exit(1)
    
if __name__ == "__main__":
    main()