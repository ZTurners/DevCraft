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
import datetime
import zipfile
import tarfile
import copy
import heapq
import re
import threading
import time

# The workspace python is an embeddable build governed by python313._pth,
# which pins sys.path and never adds the script's own directory; insert it
# explicitly so the sibling download module imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import download

# File-level config variables: '$var{name}' tokens in a config are replaced at
# load time with values from its top-level 'variables' mapping (merged with the
# variables inherited from its dependencies). The syntax is deliberately
# distinct from the '${workspace}'-style path tokens resolved by
# _formalize_path, so the two mechanisms never interact.
_CONFIG_VARIABLE_PATTERN = re.compile(r"\$var\{([A-Za-z0-9_]+)\}")
_CONFIG_VARIABLE_NAME_PATTERN = re.compile(r"[A-Za-z0-9_]+")

# Matches the SGR escape sequences _colorize emits; used to keep summary.txt
# ANSI-free while the console copy stays colored
_ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-9;]*m")

class _InstallProgressBar:
    """Sticky status line pinned to the terminal's bottom row during installs.

    The last terminal row is reserved via a DECSTBM scroll region, so normal
    output (including passthrough child processes) scrolls above it while the
    line is redrawn once per second and on every state change. Entirely
    disabled when stdout is not a terminal.
    """

    _REFRESH_INTERVAL_SECONDS = 1.0

    def __init__(self, use_colors):
        self.m_use_colors = use_colors
        self.m_enabled = sys.stdout.isatty()
        self.m_active = False
        self.m_total = 0
        self.m_done = 0
        self.m_skipped = 0
        # "work" items are configs that actually install this run (fresh +
        # reinstall); skips and no-sdk_root runs do not count as installs
        self.m_work_total = 0
        self.m_work_done = 0
        self.m_current = ""
        self.m_step = ""
        self.m_started_at = 0.0
        self.m_lock = threading.Lock()
        self.m_refresh_thread = None

    def start(self, total, work_total=None):
        if not self.m_enabled:
            return
        columns, lines = shutil.get_terminal_size()
        if lines < 4:
            self.m_enabled = False
            return
        self.m_total = total
        self.m_work_total = work_total if work_total is not None else total
        self.m_started_at = time.monotonic()
        self.m_active = True
        # Reserve the bottom row. The screen is scrolled up two rows first so
        # the cursor provably stays inside the region; DECSTBM homes the
        # cursor, hence the save/restore around it.
        sys.stdout.write(f"\033[2S\033[2A\0337\033[1;{lines - 1}r\0338")
        sys.stdout.flush()
        self._render()
        self.m_refresh_thread = threading.Thread(target=self._refresh_loop, daemon=True)
        self.m_refresh_thread.start()

    def _refresh_loop(self):
        while self.m_active:
            time.sleep(self._REFRESH_INTERVAL_SECONDS)
            if self.m_active:
                self._render()

    def begin_config(self, name):
        if not self.m_active:
            return
        with self.m_lock:
            self.m_current = name
            self.m_step = ""
        self._render()

    def set_step(self, step):
        if not self.m_active:
            return
        with self.m_lock:
            self.m_step = step
        self._render()

    def finish_config(self, skipped=False, work=False):
        if not self.m_active:
            return
        with self.m_lock:
            self.m_done += 1
            self.m_skipped += 1 if skipped else 0
            self.m_work_done += 1 if work else 0
            self.m_current = ""
            self.m_step = ""
        self._render()

    def stop(self):
        if not self.m_active:
            return
        self.m_active = False
        if self.m_refresh_thread is not None:
            self.m_refresh_thread.join(timeout=self._REFRESH_INTERVAL_SECONDS * 2)
            self.m_refresh_thread = None
        columns, lines = shutil.get_terminal_size()
        # Clear the reserved row and restore full-screen scrolling; the run
        # summary continues from the cleared bottom row.
        sys.stdout.write(f"\033[{lines};1H\033[2K\033[r\033[{lines};1H")
        sys.stdout.flush()

    def _render(self):
        columns, lines = shutil.get_terminal_size()
        with self.m_lock:
            text = self._format_line(columns)
        # Re-assert the region (keeps working across terminal resizes), then
        # redraw the reserved row and put the cursor back where it was.
        sys.stdout.write(f"\0337\033[1;{lines - 1}r\0338\0337\033[{lines};1H\033[2K{text}\0338")
        sys.stdout.flush()

    def _format_line(self, columns):
        elapsed_seconds = int(time.monotonic() - self.m_started_at)
        elapsed_text = time.strftime("%H:%M:%S", time.gmtime(elapsed_seconds))
        # [configs processed this run / total configs]; skipped configs count
        # too, so the head keeps moving through already-installed stretches
        in_progress = bool(self.m_current)
        index = self.m_done + (1 if in_progress else 0)
        head = f"[{index}/{self.m_total}] "
        if self.m_current:
            middle = f"Installing: {self.m_current}"
            if self.m_step:
                middle += f" ({self.m_step})"
        else:
            middle = ""
        # Installed/Remaining count real installs only (fresh + reinstall);
        # Remaining includes the one currently in progress
        remaining = max(0, self.m_work_total - self.m_work_done)
        skipped_note = f" ({self.m_skipped} up-to-date)" if self.m_skipped else ""
        tail = f" | Installed: {self.m_work_done}{skipped_note} | Remaining: {remaining} | {elapsed_text}"

        budget = columns - 1 - len(head) - len(tail)
        if middle and budget < len(middle):
            if budget >= 12:
                middle = middle[: budget - 3] + "..."
            else:
                middle = ""

        def _join(tail_text):
            if middle:
                return head + middle + tail_text
            return head + tail_text.lstrip(" |")

        # Degrade on narrow terminals: drop the skipped note, then the stats,
        # keeping only the elapsed time, then hard-truncate what is left. The
        # flags record what survived so the colored rebuild below produces the
        # exact same visible text.
        include_note = bool(skipped_note)
        include_stats = True
        line = _join(tail)
        if len(line) > columns - 1 and include_note:
            include_note = False
            line = _join(f" | Installed: {self.m_work_done} | Remaining: {remaining} | {elapsed_text}")
        if len(line) > columns - 1:
            include_stats = False
            line = _join(f" | {elapsed_text}")
        if len(line) > columns - 1:
            line = line[: columns - 1]
            if self.m_use_colors:
                line = "\033[36m" + line + "\033[0m"
            return line

        if not self.m_use_colors:
            return line

        # Colored rebuild of the identical visible text: head + current config
        # cyan, installed count blue (SUCCESS-INSTALLED), skipped note green
        # (up-to-date), remaining count red — matching the summary palette.
        if include_stats:
            tail_colored = f"\033[38;5;117mInstalled: {self.m_work_done}\033[0m"
            if include_note:
                tail_colored += f" \033[92m({self.m_skipped} up-to-date)\033[0m"
            tail_colored += f" | \033[31mRemaining: {remaining}\033[0m | \033[36m{elapsed_text}\033[0m"
        else:
            tail_colored = f"\033[36m{elapsed_text}\033[0m"
        if middle:
            return f"\033[36m{head}{middle}\033[0m | {tail_colored}"
        return f"\033[36m{head}\033[0m{tail_colored}"

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
        self.m_user_aborted = False
        self.m_nothing_to_do = False
        # Colored console output: only when writing to a terminal and NO_COLOR
        # is unset. ANSI processing is enabled for any terminal on Windows
        # (not just colored runs) because the bottom progress bar also emits
        # escape sequences; "os.system('')" turns them on in legacy Windows
        # consoles (Windows Terminal supports them natively).
        self.m_use_colors = (not os.environ.get("NO_COLOR")) and sys.stdout.isatty()
        if sys.stdout.isatty() and self.m_system_name == "Windows":
            os.system("")
        self.m_progress_bar = _InstallProgressBar(self.m_use_colors)

    def build_failure_summary(self, error):
        """Build a compact failure summary for console output."""
        lines = ["Failure summary:"]
        lines.append(f"  Config: {self.m_current_config or 'N/A'}")
        lines.append(f"  Node: {self.m_current_node or 'N/A'}")
        lines.append(f"  Install step: {self.m_current_install_step or 'N/A'}")
        lines.append(f"  Error: {error}")
        return "\n".join(lines)

    def _record_unprocessed_configs(self, ordered, records):
        """After an aborted run, record the configs the processing loop never reached.

        Planned installs that never started become red SKIPPED entries; configs the
        plan already considered installed become UP-TO-DATE. Without this the
        summary would silently omit everything after the failure point.
        """
        recorded = {item["config"] for item in self.m_summary_data}
        for rel in ordered:
            config_path = records[rel]['path']
            try:
                display_name = os.path.relpath(config_path, self.m_configs_root_path)
            except Exception:
                display_name = os.path.basename(config_path)
            if display_name in recorded:
                continue
            if records[rel].get('install_status') == "up to date":
                self._record_config_summary(display_name, "SKIPPED", "already installed (config unchanged)", records[rel]['variables'])
            else:
                self._record_config_summary(display_name, "NOT STARTED", "planned this run but not started (run aborted)", records[rel]['variables'])

    def _record_config_summary(self, config_name, status, message="", variables=None, duration_seconds=None):
        """Record per-config install result for final summary output."""
        sdk_name = config_name.replace('\\', '/').split('/', 1)[0] if isinstance(config_name, str) and config_name else "N/A"
        self.m_summary_data.append({
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            "sdk": sdk_name,
            "config": config_name,
            "status": status,
            "message": message,
            "variables": variables or {},
            "duration_seconds": duration_seconds,
        })

    @staticmethod
    def _format_duration(seconds):
        seconds = int(round(seconds))
        if seconds < 60:
            return f"{seconds}s"
        minutes, sec = divmod(seconds, 60)
        if minutes < 60:
            return f"{minutes}m{sec:02d}s"
        hours, minutes = divmod(minutes, 60)
        return f"{hours}h{minutes:02d}m{sec:02d}s"

    def build_run_summary(self, run_error=None):
        """Build a timestamped summary for the full install run."""
        run_finished_at = datetime.datetime.now(datetime.UTC)
        total_seconds = int((run_finished_at - self.m_run_started_at).total_seconds())
        total_count = len(self.m_summary_data)
        success_items = [item for item in self.m_summary_data if item.get("status") == "SUCCESS"]
        failed_items = [item for item in self.m_summary_data if item.get("status") == "FAILED"]
        skipped_items = [item for item in self.m_summary_data if item.get("status") == "SKIPPED"]
        nosdkroot_items = [item for item in self.m_summary_data if item.get("status") == "no sdk_root"]
        notstarted_items = [item for item in self.m_summary_data if item.get("status") == "NOT STARTED"]

        lines = []
        lines.append("DevCraft Install Summary")
        lines.append(f"Started (UTC): {self.m_run_started_at.isoformat()}")
        lines.append(f"Finished (UTC): {run_finished_at.isoformat()}")
        lines.append(f"Duration (seconds): {total_seconds}")
        overall = "FAILED" if run_error else "SUCCESS"
        lines.append(self._colorize(f"Overall result: {overall}", overall, light=True))
        lines.append(f"Configs processed: {total_count}")
        lines.append(self._colorize(f"New SDK installs (this run): {len(success_items)}", "SUCCESS", light=True))
        # keep a zero-failure count uncolored; red is reserved for real failures
        if failed_items:
            lines.append(self._colorize(f"Failed SDK installs: {len(failed_items)}", "FAILED", light=True))
        else:
            lines.append(f"Failed SDK installs: {len(failed_items)}")
        lines.append(self._colorize(f"Up-to-date SDK installs (config unchanged): {len(skipped_items)}", "SKIPPED", light=True))
        if nosdkroot_items:
            lines.append(self._colorize(f"No sdk_root configs (install steps run every time): {len(nosdkroot_items)}", "no sdk_root", light=True))
        if notstarted_items:
            lines.append(self._colorize(f"Planned but not started (run aborted): {len(notstarted_items)}", "NOT STARTED", light=True))

        # Single per-config listing covering ALL configs, mirroring the install
        # plan: name first (padded, tag column aligned at the end). SUCCESS
        # entries carry the elapsed-time suffix; FAILED / NOT STARTED entries
        # print their message; variables print as sub-lines.
        lines.append("")
        lines.append("Config statuses (this run):")
        shown_items = list(self.m_summary_data)
        name_width = max((len(str(item["config"])) for item in shown_items), default=0)
        tag_width = len("[SUCCESS-INSTALLED]")
        for index, item in enumerate(shown_items, start=1):
            status = item.get("status", "UNKNOWN")
            config_name = self._colorize(str(item["config"]).ljust(name_width), status, light=True)
            tag_text = f"[{self._status_tag(status)}]"
            tag = self._colorize(tag_text, status, light=True)
            tag_pad = " " * (tag_width - len(tag_text))
            duration_text = ""
            duration = item.get("duration_seconds")
            if duration is not None:
                duration_text = f" | elapsed time: {self._format_duration(duration)}"
            lines.append(f"  {index:>2}. {config_name}  {tag}{tag_pad}{duration_text}".rstrip())
            if status in ("FAILED", "NOT STARTED"):
                message = item.get("message") or "Unknown error"
                lines.append(self._colorize(f"        - {message}", status))
            for name, value in item["variables"].items():
                lines.append(self._colorize(f"        - {name}={value}", status))

        if run_error:
            lines.append("")
            lines.append(self._colorize(self.build_failure_summary(run_error), "FAILED", light=True))

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

    def _formalize_path_in_active_file(self, path):
        """Formalize a path for generated active files: ${workspace} is rendered
        as a runtime DEVCRAFT_WORKSPACE reference so the file stays relocatable
        after the workspace is copied. Install-time path resolution keeps using
        _formalize_path (absolute paths)."""
        if not isinstance(path, str) or path == "":
            return path
        if "${workspace}" in path:
            var = "%DEVCRAFT_WORKSPACE%" if self.m_system_name == "Windows" else "${DEVCRAFT_WORKSPACE}"
            return path.replace("${workspace}", var)
        return self._formalize_path(path)

    def _process_download(self, download_config, context):
        """Handle download node."""
        # download_config is the child node data: { src: {url, auth_required, MD5, SHA-256, SHA-512}, dest }

        # Handle src as either nested object or flat src_url
        if "src" in download_config and isinstance(download_config["src"], dict):
            src_url = download_config["src"]["url"]
            need_auth = download_config["src"].get("auth_required", False)
            expected_md5_hash = download_config["src"].get("MD5", None)
            expected_sha256_hash = download_config["src"].get("SHA-256", None)
            expected_sha512_hash = download_config["src"].get("SHA-512", None)

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

        # The multi-threaded download and verification pipeline lives in
        # download.py; its staged '.downloading' file is only renamed to dest
        # after Content-Length and all requested checksums pass
        download.download_file(
            src_url,
            downloaded_file,
            expected_md5_hash=expected_md5_hash,
            expected_sha256_hash=expected_sha256_hash,
            expected_sha512_hash=expected_sha512_hash,
            need_auth=need_auth)

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
        is_tar_gz = src_zip_file.lower().endswith(('.tar.gz', '.tgz'))
        is_tar_xz = src_zip_file.lower().endswith('.tar.xz')

        if not (is_zip or is_tar_gz or is_tar_xz):
            raise Exception("Unsupported archive format. Only .zip, .tar.gz, .tgz, and .tar.xz are supported")

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
                if not isinstance(var_value, str):
                    # os.environ only accepts strings; an unquoted number in a
                    # config would otherwise die with an opaque TypeError
                    raise TypeError(
                        f"environment variable '{var_name}' must be a quoted string "
                        f"in the config (got {type(var_value).__name__}: {var_value!r})"
                    )
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
                        if not isinstance(var_value, str):
                            raise TypeError(
                                f"environment variable '{var_name}' must be a quoted string "
                                f"in the config (got {type(var_value).__name__}: {var_value!r})"
                            )
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
        passthrough = False

        # Handle new object format: { command: [...], dest: "...", skip_if_exists: "..." }
        if isinstance(command_config, dict):
            # skip_if_exists: skip the command if the given path already exists
            skip_path = command_config.get("skip_if_exists", "")
            if skip_path:
                skip_path = self._formalize_path(skip_path)
                if os.path.exists(skip_path):
                    print(f"Skipping execute: '{skip_path}' already exists.")
                    return

            # terminal: pass the child's stdout/stderr straight to the console
            # instead of capturing them. CLIs like cargo/pip/npm only render
            # progress bars when attached to a real terminal.
            passthrough = bool(command_config.get("terminal", False))

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
                result = subprocess.run(
                    command,
                    shell=True,
                    check=True,
                    text=True,
                    stdout=None if passthrough else subprocess.PIPE,
                    stderr=None if passthrough else subprocess.PIPE,
                )
                if not passthrough and result.stdout:
                    print(result.stdout.rstrip())
                print("Command executed successfully.")
            except subprocess.CalledProcessError as e:
                stdout = (e.stdout or "").rstrip()
                stderr = (e.stderr or "").rstrip()
                if stdout:
                    print("Command stdout:")
                    print(stdout)
                if stderr:
                    print("Command stderr:")
                    print(stderr)

                details = [f"Command failed with exit code {e.returncode}"]
                if stdout:
                    details.append(f"stdout: {stdout}")
                if stderr:
                    details.append(f"stderr: {stderr}")
                error_message = " | ".join(details)
                print(f"Error executing command: {error_message}")
                raise RuntimeError(error_message) from e

    def _extract_set_variables_nodes(self, install_node):
        """Collect (name, source) declarations from all 'set_variables' install steps."""
        decls = []
        if not isinstance(install_node, list):
            return decls
        for entry in install_node:
            if not isinstance(entry, dict):
                continue
            for step_name, step_data in entry.items():
                if step_name != 'set_variables' or not isinstance(step_data, dict):
                    continue
                for name, source in step_data.items():
                    decls.append((name, source))
        return decls

    def _set_variables_source_path(self, name, source, config_file_path, variables):
        """Interpolate and formalize the 'json_file' of one set_variables declaration."""
        if not isinstance(source, dict) or 'json_file' not in source or 'json_key' not in source:
            raise RuntimeError(
                f"'set_variables' entry '{name}' must provide 'json_file' and 'json_key' "
                f"in {config_file_path}")
        return self._formalize_path(
            self._interpolate_config_text(str(source['json_file']), variables, config_file_path))

    def _read_set_variables_value(self, name, source, config_file_path, variables):
        """Resolve one set_variables declaration from its JSON source; fail loud on problems."""
        json_file = self._set_variables_source_path(name, source, config_file_path, variables)
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            raise RuntimeError(f"'set_variables' cannot read '{json_file}' for '{name}': {e}") from e
        key = source['json_key']
        if key not in data or not isinstance(data[key], str) or not data[key].strip():
            raise RuntimeError(f"'set_variables': '{json_file}' has no non-empty string value at key '{key}'")
        return data[key].strip(), json_file

    def _apply_set_variables_from_disk(self, record):
        """Pre-resolve set_variables sources that already exist on disk.

        A skipped config never runs its install steps, so without this its derived
        variables would stay unresolved when dependents apply its exported
        environments. Sources that do not exist yet (fresh install) are left to
        the install-time 'set_variables' step.
        """
        for name, source in record['set_variables_decls']:
            json_file = self._set_variables_source_path(name, source, record['path'], record['effective_variables'])
            if not os.path.exists(json_file):
                continue
            value, json_file = self._read_set_variables_value(name, source, record['path'], record['effective_variables'])
            print(f"set_variables (from disk): {name}={value} (from {json_file})")
            record['effective_variables'][name] = value

    def _process_set_variables(self, set_variables_config, context):
        """Handle set_variables node: derive variables from install-produced files.

        Shape:
            - set_variables:
                <name>:
                  json_file: <path to a JSON file produced by earlier install steps>
                  json_key: <top-level key whose string value becomes $var{<name>}

        Values land in the live effective-variables mapping, so this config's
        generator_active_batch (interpolated after the install steps) and
        dependents applying this config's exported environments see them. Install
        steps are interpolated before any step runs, so they can only reference
        statically defined variables.
        """
        variables = context.get('variables')
        if not isinstance(variables, dict):
            raise RuntimeError("'set_variables' requires an install-time variables context")
        config_file_path = context.get('config_file_path', '')
        if not isinstance(set_variables_config, dict) or not set_variables_config:
            raise RuntimeError(f"'set_variables' must be a non-empty mapping in {config_file_path}")
        for name, source in set_variables_config.items():
            value, json_file = self._read_set_variables_value(name, source, config_file_path, variables)
            variables[name] = value
            print(f"set_variables: {name}={value} (from {json_file})")

    def _process_generator_active_batch(self, generator_active_batch, context):
        """Handle generator_active_batch node."""
        # generator_active_batch is the child node data: { file_path, environments }
        if "file_path" not in generator_active_batch or "environments" not in generator_active_batch:
            return

        # Interpolate at processing time (after the install steps ran) so values
        # derived by 'set_variables' steps are visible in the generated file.
        generator_active_batch = self._interpolate_config_variables(
            generator_active_batch,
            context.get('variables') or {},
            context.get('config_file_path', ''))
        
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
                value = self._formalize_path_in_active_file(value)
                set_env_list.append((var, value))
        
        # Process prepend
        if "prepend" in generator_active_batch["environments"]:
            for item in generator_active_batch["environments"]["prepend"]:
                # Each item is a dictionary with a single key-value pair
                for var, value in item.items():
                    # Replace workspace variable
                    value = self._formalize_path_in_active_file(value)
                    prepend_env_list.append((var, value))
        
        # Generate the batch file
        commands = generator_active_batch.get("commands", [])
        if isinstance(commands, str):
            commands = [commands]
        self.generate_enviroment_set_batch_file(file_path, set_env_list, prepend_env_list, commands)

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
            'set_variables': self._process_set_variables,
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
            self.m_progress_bar.set_step(install_step_name)

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

    def _extract_variables(self, config_file_path, config):
        """Read and validate the optional top-level variables mapping from a config.

        Values must be scalars (str/int/float); they are literal and never
        interpolated themselves. Returns {} when the config declares none.
        """
        variables = config.get('variables')
        if variables is None:
            return {}
        if not isinstance(variables, dict):
            raise TypeError(f"'variables' must be a mapping in {config_file_path}")

        validated = {}
        for name, value in variables.items():
            if not isinstance(name, str) or not _CONFIG_VARIABLE_NAME_PATTERN.fullmatch(name):
                raise TypeError(
                    f"Invalid variable name {name!r} in {config_file_path} "
                    f"(allowed: letters, digits, underscore)"
                )
            if isinstance(value, bool) or not isinstance(value, (str, int, float)):
                raise TypeError(f"Variable '{name}' must map to a scalar value in {config_file_path}")
            validated[name] = value
        return validated

    def _interpolate_config_text(self, text, variables, config_file_path):
        """Replace every $var{name} token in one string; unknown names are an error."""
        def _replace(match):
            name = match.group(1)
            if name not in variables:
                raise RuntimeError(f"Undefined variable '$var{{{name}}}' in {config_file_path}")
            return str(variables[name])

        return _CONFIG_VARIABLE_PATTERN.sub(_replace, text)

    def _interpolate_config_variables(self, node, variables, config_file_path):
        """Recursively interpolate $var{name} tokens in all strings of a config tree."""
        if isinstance(node, dict):
            return {
                key: self._interpolate_config_variables(value, variables, config_file_path)
                for key, value in node.items()
            }
        if isinstance(node, list):
            return [self._interpolate_config_variables(item, variables, config_file_path) for item in node]
        if isinstance(node, str):
            return self._interpolate_config_text(node, variables, config_file_path)
        return node

    def _compute_effective_variables(self, records):
        """Merge each config's variables with the variables inherited from its dependencies.

        Resolution walks the dependency closure, so a config sees the effective
        variables (own + inherited) of every config it depends on. A name defined
        twice with different values is an error: a version must have a single
        source of truth. Same name with the same value is allowed.
        """
        effective_by_rel = {}

        def _resolve(rel, pending):
            if rel in effective_by_rel:
                return effective_by_rel[rel]
            if rel in pending:
                cycle = " -> ".join(pending + [rel])
                raise RuntimeError(f"Cyclic dependency while resolving variables: {cycle}")

            inherited = {}
            for dep_rel in records[rel]['dep_rels']:
                for name, value in _resolve(dep_rel, pending + [rel]).items():
                    if name in inherited and inherited[name] != value:
                        raise RuntimeError(
                            f"Conflicting values for variable '{name}' among dependencies of "
                            f"{records[rel]['path']}: '{dep_rel}' provides {value!r}, "
                            f"another dependency provides {inherited[name]!r}"
                        )
                    inherited[name] = value

            own = records[rel]['variables']
            for name, value in own.items():
                if name in inherited and inherited[name] != value:
                    raise RuntimeError(
                        f"Variable '{name}' in {records[rel]['path']} ({value!r}) conflicts with the "
                        f"value inherited from its dependencies ({inherited[name]!r}); "
                        f"remove the local override or align the values"
                    )

            effective_by_rel[rel] = {**inherited, **own}
            return effective_by_rel[rel]

        for rel in records:
            _resolve(rel, [])
        return effective_by_rel

    def _extract_sdk_root(self, config_file_path, config):
        """Read optional top-level sdk_root path from config."""
        sdk_root = config.get('sdk_root', '')
        if sdk_root is None:
            return ''
        if not isinstance(sdk_root, str):
            raise TypeError(f"'sdk_root' must be a string in {config_file_path}")
        return sdk_root.strip()

    def _calculate_file_md5(self, file_path):
        """Calculate the MD5 checksum of a file."""
        md5 = hashlib.md5()
        with open(file_path, 'rb') as fh:
            for chunk in iter(lambda: fh.read(8192), b''):
                md5.update(chunk)
        return md5.hexdigest()

    def _resolve_sdk_root(self, config_file_path, sdk_root_raw):
        """Formalize and validate the sdk_root declared by a config."""
        sdk_root = os.path.abspath(self._formalize_path(sdk_root_raw))
        protected_paths = {
            os.path.abspath(self.m_dev_env_root_path),
            os.path.abspath(self.m_workspace_root_path),
            os.path.abspath(self.m_configs_root_path),
            os.path.abspath(self.m_download_root_path),
        }
        if sdk_root in protected_paths:
            raise RuntimeError(
                f"Invalid sdk_root '{sdk_root}' in {config_file_path}: "
                "it must be a dedicated folder, not a DevCraft/workspace root"
            )
        return sdk_root

    def _installed_config_marker_path(self, sdk_root, config_file_path):
        """Path of the config copy stored inside an installed sdk root."""
        return os.path.join(sdk_root, os.path.basename(config_file_path))

    # Inline delete-progress redraw cadence; per-item prints would dominate
    # the runtime on SDK-sized trees
    _REMOVE_PROGRESS_INTERVAL_SECONDS = 0.1

    def _rmtree_force(self, path, progress_label=None):
        """shutil.rmtree that clears read-only flags before retrying.

        Archives for Unix targets (e.g. LLVM's Linux tarballs) contain files
        with 0444/0555 permissions; on Windows these map to read-only files
        that plain shutil.rmtree cannot delete (WinError 5).

        With progress_label (and a terminal stdout), the tree is scanned and
        deleted entry by entry while an inline percentage line is redrawn.
        """
        if (progress_label and sys.stdout.isatty()
                and os.path.isdir(path) and not os.path.islink(path)):
            self._rmtree_with_progress(path, progress_label)
            return

        def _clear_readonly(func, target, _exc):
            os.chmod(target, stat.S_IWRITE)
            func(target)

        if sys.version_info >= (3, 12):
            shutil.rmtree(path, onexc=_clear_readonly)
        else:
            shutil.rmtree(path, onerror=_clear_readonly)

    def _rmtree_with_progress(self, path, label):
        """Delete a tree bottom-up, redrawing 'label: NN% [done/total]' as it goes."""
        started = time.monotonic()
        last_draw = 0.0

        def _draw(body, force=False):
            nonlocal last_draw
            now = time.monotonic()
            if not force and now - last_draw < self._REMOVE_PROGRESS_INTERVAL_SECONDS:
                return
            last_draw = now
            # \033[K wipes the tail of the previous, possibly longer line
            print(f"\r{label}: {body}\033[K", end="", flush=True)

        # Scan pass: entry counts are needed before the delete pass can show a
        # percentage; counting a big tree takes a while, so it shares the line
        file_paths = []
        dir_paths = []
        for root, dirs, files in os.walk(path, topdown=False, followlinks=False):
            for name in files:
                file_paths.append(os.path.join(root, name))
            for name in dirs:
                dir_paths.append(os.path.join(root, name))
            _draw(f"scanning... {len(file_paths)} files")

        total = len(file_paths) + len(dir_paths)
        done = 0

        def _draw_progress():
            _draw(f"{done * 100 // max(1, total)}% [{done}/{total} items]")

        try:
            for file_path in file_paths:
                self._remove_file_force(file_path)
                done += 1
                _draw_progress()
            # topdown=False yields children before parents, so directories
            # disappear in dependency order; symlinked dirs were never
            # descended into and are removed as links
            for dir_path in dir_paths:
                self._remove_dir_force(dir_path)
                done += 1
                _draw_progress()
            os.rmdir(path)
        except Exception:
            print()  # leave the progress line before the error text
            raise
        elapsed_text = self._format_duration(time.monotonic() - started)
        _draw(f"100% [{total} items removed in {elapsed_text}]", force=True)
        print()

    @staticmethod
    def _remove_file_force(path):
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass  # already gone; the goal is an empty tree
        except PermissionError:
            os.chmod(path, stat.S_IWRITE)
            os.unlink(path)

    @staticmethod
    def _remove_dir_force(path):
        if os.path.islink(path):
            try:
                os.unlink(path)  # POSIX directory symlinks
                return
            except OSError:
                pass  # Windows directory symlinks/junctions need rmdir below
        try:
            os.rmdir(path)
        except FileNotFoundError:
            pass
        except PermissionError:
            os.chmod(path, stat.S_IWRITE)
            os.rmdir(path)

    def _validate_installed_config_state(self, config_file_path, sdk_root, reinstall_reason=None, preserve_rel_paths=None):
        """Wipe the sdk root when the stored config copy is missing or changed.

        The stored copy is compared with the current config file by MD5; any
        difference (or a missing copy) means the sdk was installed from a
        different config and must be reinstalled from scratch. When
        reinstall_reason is set (a dependency is missing or being
        reinstalled), the sdk root is wiped even though its own copy matches,
        so the dependent is regenerated against the new dependency state.
        Paths listed in the config's preserve_on_reinstall (relative or
        ${workspace}-style absolute, always inside the sdk root) survive the wipe.
        """
        if not sdk_root or not os.path.exists(sdk_root):
            return

        if reinstall_reason is None:
            marker_path = self._installed_config_marker_path(sdk_root, config_file_path)
            if not os.path.exists(marker_path):
                reason = f"no installed config copy found at '{marker_path}'"
            elif self._calculate_file_md5(marker_path) != self._calculate_file_md5(config_file_path):
                reason = f"installed config copy '{marker_path}' differs from '{config_file_path}' (MD5 mismatch)"
            else:
                return
        else:
            reason = reinstall_reason

        print(f"\nReinstall required: {reason}.")
        if preserve_rel_paths:
            print(f"Removing sdk root except preserve_on_reinstall paths "
                  f"({', '.join(preserve_rel_paths)}): {sdk_root}")
        else:
            print(f"Removing sdk root for a clean reinstall: {sdk_root}")
        self.m_progress_bar.set_step("removing old install")
        self._rmtree_sdk_root_excluding(sdk_root, preserve_rel_paths, "Removing old install")

    def _rmtree_sdk_root_excluding(self, sdk_root, preserve_rel_paths, progress_label):
        """Remove an sdk root except the subpaths listed in the config's
        preserve_on_reinstall (paths relative to the sdk root or
        ${workspace}-style absolute, kept in place during the wipe)."""
        if not preserve_rel_paths:
            self._rmtree_force(sdk_root, progress_label=progress_label)
            return

        sdk_abs = os.path.abspath(sdk_root)
        keep = set()
        for rel in preserve_rel_paths:
            kept = os.path.abspath(os.path.join(sdk_abs, rel))
            if os.path.commonpath([kept, sdk_abs]) != sdk_abs or kept == sdk_abs:
                raise RuntimeError(
                    f"preserve_on_reinstall path '{rel}' escapes sdk root '{sdk_root}'")
            keep.add(os.path.normcase(kept))

        def _delete_selective(path):
            path_abs = os.path.abspath(path)
            path_nc = os.path.normcase(path_abs)
            if path_nc in keep:
                return
            # a kept path nested under this entry: keep the entry, prune inside
            if any(os.path.commonpath([k, path_nc]) == path_nc for k in keep):
                for name in os.listdir(path_abs):
                    _delete_selective(os.path.join(path_abs, name))
                return
            if os.path.isdir(path_abs) and not os.path.islink(path_abs):
                self._rmtree_force(path_abs, progress_label=progress_label)
            else:
                os.remove(path_abs)

        _delete_selective(sdk_abs)

    def _remove_failed_sdk_root(self, sdk_root, config_display_name, preserve_rel_paths=None):
        """Remove the sdk root after a failed install so no broken state remains.
        Subpaths listed in the config's preserve_on_reinstall are kept."""
        if not sdk_root or not os.path.exists(sdk_root):
            return

        print(f"\nInstall failed for '{config_display_name}'; removing sdk root: {sdk_root}")
        self.m_progress_bar.set_step("removing failed install")
        try:
            self._rmtree_sdk_root_excluding(
                sdk_root, preserve_rel_paths, "Removing failed install")
        except Exception as e:
            print(f"Warning: could not remove sdk root '{sdk_root}': {e}")

    def _store_installed_config_marker(self, config_file_path, sdk_root):
        """Copy the current config file into the sdk root as install-state marker."""
        marker_path = self._installed_config_marker_path(sdk_root, config_file_path)
        os.makedirs(sdk_root, exist_ok=True)
        shutil.copyfile(config_file_path, marker_path)
        print(f"Stored installed config copy: {marker_path}")

    def _get_install_status_detail(self, config_file_path, sdk_root):
        """Return (status, short reason) for a config without touching the sdk root.

        The reason is set for the own-config reinstall-needed cases so the plan
        can show why; None when the tag speaks for itself.
        """
        if not sdk_root:
            return "no sdk_root", None
        if not os.path.exists(sdk_root):
            return "missing", None
        marker_path = self._installed_config_marker_path(sdk_root, config_file_path)
        if not os.path.exists(marker_path):
            return "reinstall-needed", "no installed config copy found"
        if self._calculate_file_md5(marker_path) != self._calculate_file_md5(config_file_path):
            return "reinstall-needed", "installed config copy differs (MD5 mismatch)"
        return "up to date", None

    def _get_install_status(self, config_file_path, sdk_root):
        """Return the install status tag for a config without touching the sdk root.

        up to date         sdk root exists and its stored config copy matches
        missing            sdk root does not exist yet
        reinstall-needed   sdk root exists but the stored copy is missing/changed
        no sdk_root        config does not take part in the marker mechanism
        """
        return self._get_install_status_detail(config_file_path, sdk_root)[0]

    def _confirm_proceed(self):
        """Ask the user to confirm the install plan before proceeding."""
        try:
            answer = input("\nProceed with installation? [y/N]: ").strip().lower()
        except EOFError:
            print("\nNo interactive input available; aborting.")
            return False
        return answer in ("y", "yes")

    @staticmethod
    def _status_tag(status):
        """Display form of a status for [TAG] labels: uppercase, hyphen-joined."""
        if status == "SUCCESS":
            return "SUCCESS-INSTALLED"
        if status == "SKIPPED":
            return "UP-TO-DATE"
        if status == "no sdk_root":
            return "SKIP"
        return status.upper().replace(" ", "-").replace("_", "-")

    def _colorize(self, text, status, light=False):
        """Wrap text in the ANSI color assigned to an install status.

        light=True picks the brighter variant of the status color (summary
        titles, stat lines and entry / package name lines); the base palette
        is kept only for the var (parameter) lines nested under them.
        """
        if not self.m_use_colors:
            return text
        palette = {
            "up to date": "\033[32m",        # green (sub-line tier)
            "missing": "\033[31m",           # red
            "reinstall-needed": "\033[31m",  # red
            "no sdk_root": "\033[38;5;240m", # gray (sub-line tier)
            "SUCCESS": "\033[38;5;75m",      # blue (sub-line tier)
            "FAILED": "\033[31m",            # red
            "SKIPPED": "\033[32m",           # green (sub-line tier)
            "NOT STARTED": "\033[31m",       # red: planned this run, never started
        }
        light_palette = {
            "up to date": "\033[92m",       # green (entry tier)
            "missing": "\033[91m",           # bright red
            "reinstall-needed": "\033[91m",  # bright red
            "no sdk_root": "\033[90m",       # bright gray (entry tier)
            "SUCCESS": "\033[38;5;117m",    # blue (entry tier)
            "FAILED": "\033[91m",            # bright red
            "SKIPPED": "\033[92m",          # green (entry tier)
            "NOT STARTED": "\033[91m",       # bright red
        }
        ansi = (light_palette if light else palette).get(status)
        return f"{ansi}{text}\033[0m" if ansi else text

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

    def install_from_config(self, config_file_path, variables=None):
        """Generic installation function that handles downloading and extracting from configured URLs.
        Args:
            config_file_path: Path to the configuration YAML/JSON file
            variables: Effective variable values (own + inherited from dependencies)
                used to interpolate $var{name} tokens in this config
        """
        try:
            config = self._load_config_data(config_file_path)
        except json.JSONDecodeError:
            raise RuntimeError(f"Invalid JSON in configuration file: {config_file_path}")
        except Exception as e:
            raise RuntimeError(f"Unexpected error reading configuration '{config_file_path}': {e}") from e

        # Interpolate $var{} tokens with the effective variables, then drop the
        # 'variables' block so install handlers never see it. Install steps are
        # interpolated up front and can only reference statically defined
        # variables; generator_active_batch is excluded here and interpolated at
        # processing time instead, so 'set_variables' steps (which run during
        # install) can feed derived values into the generated batch file.
        raw_config = dict(config)
        config.pop('variables', None)
        config.pop('generator_active_batch', None)
        live_variables = variables if isinstance(variables, dict) else {}
        config = self._interpolate_config_variables(config, live_variables, config_file_path)

        context = {
            'config': config,
            'variables': live_variables,
            'config_file_path': config_file_path,
        }

        # Define config-level node handlers mapping
        config_handlers = {
            'install': self._process_install,
            'generator_active_batch': self._process_generator_active_batch,
        }

        # Process config nodes in order. generator_active_batch reads the raw
        # (not yet interpolated) node so its late interpolation sees any
        # install-time 'set_variables' values.
        for node_name, handler in config_handlers.items():
            source = raw_config if node_name == 'generator_active_batch' else config
            if node_name in source:
                self.m_current_node = node_name
                try:
                    print(f"\nProcessing '{node_name}' configuration...")
                    handler(source[node_name], context)
                except Exception as e:
                    raise RuntimeError(f"Error processing '{node_name}' configuration: {e}") from e

    def generate_enviroment_set_batch_file(self, output_file, set_env_list, prepend_env_list, commands=None):
        commands = commands or []
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
                
                # Append commands
                for var_name, value in prepend_env_list:
                    value = self._formalize_path(value)
                    f.write(f'set {var_name}={value};%{var_name}%\n')

                for command in commands:
                    f.write(f'\n{self._formalize_path(command)}\n')

                # Set commands (overwrite existing values) after setup commands
                for var_name, value in set_env_list:
                    value = self._formalize_path(value)
                    f.write(f'set {var_name}={value}\n')
                
                f.write('\necho Environment variables set successfully\n')
        else:
            with open(output_file, 'w') as f:
                f.write("#!/bin/bash\n\n")
                f.write("# Auto-generated environment setup script\n")
                f.write("# This script sets and appends environment variables\n\n")
                
                # Write append commands
                for var_name, value in prepend_env_list:
                    value = self._formalize_path(value)
                    f.write(f'export {var_name}="{value}:${var_name}"\n')

                for command in commands:
                    f.write(f'\n{self._formalize_path(command)}\n')

                # Write set commands (overwrite existing values) after setup commands
                for var_name, value in set_env_list:
                    value = self._formalize_path(value)
                    f.write(f'export {var_name}="{value}"\n')
                
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
                sdk_root_raw = self._extract_sdk_root(config_path, config_data)
                preserve_paths = config_data.get('preserve_on_reinstall') or []
                if not isinstance(preserve_paths, list) or not all(
                        isinstance(p, str) for p in preserve_paths):
                    raise RuntimeError(
                        "preserve_on_reinstall must be a list of paths "
                        "(relative to the sdk root or ${workspace}-style)")
                preserve_paths = [self._formalize_path(p) for p in preserve_paths]
                variables = self._extract_variables(config_path, config_data)
                set_variables_decls = self._extract_set_variables_nodes(config_data.get('install'))
                batch_environments = (config_data.get('generator_active_batch') or {}).get('environments') or {}
            except Exception as e:
                raise RuntimeError(f"Error parsing config '{config_path}': {e}") from e

            records[rel] = {
                'path': config_path,
                'rel': rel,
                'folder': folder_key,
                'base': base_name,
                'deps': dependencies,
                'sdk_root': sdk_root_raw,
                'preserve_on_reinstall': preserve_paths,
                'variables': variables,
                'set_variables_decls': set_variables_decls,
                'batch_environments': batch_environments,
                'reinstall_reason': None,
            }

            records_by_basename.setdefault(base_name, []).append(rel)
            records_by_folder.setdefault(folder_key, []).append(rel)

        # Build graph edges dependency -> dependent.
        indegree = {k: 0 for k in records}
        adjacency = {k: set() for k in records}

        for rel, record in records.items():
            record['dep_rels'] = []
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
                if dep_rel not in record['dep_rels']:
                    record['dep_rels'].append(dep_rel)

        # Resolve each config's effective variables (own + inherited through the
        # dependency closure), then interpolate $var{} tokens in sdk_root so the
        # duplicate check and status pass below see real paths.
        effective_variables_by_rel = self._compute_effective_variables(records)
        for rel, record in records.items():
            record['effective_variables'] = effective_variables_by_rel[rel]
            # Resolve 'set_variables' sources already on disk (a skipped config
            # never runs its install steps). batch_environments stay raw here and
            # are interpolated when applied to a dependent, after any dependency
            # (re)installed earlier in the run has derived its variables.
            self._apply_set_variables_from_disk(record)
            if record['sdk_root']:
                record['sdk_root'] = self._interpolate_config_text(
                    record['sdk_root'], record['effective_variables'], record['path'])

        # Detect multiple configs declaring the same sdk root: a config-change
        # wipe from one config would silently destroy the other's install.
        sdk_root_owners = {}
        for rel, record in records.items():
            sdk_root_raw = record.get('sdk_root', '')
            if not sdk_root_raw:
                continue
            sdk_root_key = os.path.normcase(os.path.abspath(self._formalize_path(sdk_root_raw)))
            if sdk_root_key in sdk_root_owners and sdk_root_owners[sdk_root_key] != rel:
                raise RuntimeError(
                    f"Multiple configs declare the same sdk_root '{sdk_root_key}': "
                    f"{sdk_root_owners[sdk_root_key]} and {rel}"
                )
            sdk_root_owners[sdk_root_key] = rel

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

        # Dependency closure per config (own deps + their transitive deps),
        # built in topological order so each dep's closure is already final.
        dep_closure = {}
        for rel in ordered:
            closure = set()
            for dep_rel in records[rel]['dep_rels']:
                closure.add(dep_rel)
                closure |= dep_closure[dep_rel]
            dep_closure[rel] = closure

        print("\nResolved config execution order:")
        name_width = max(len(rel) for rel in ordered)
        status_counts = {}
        for index, rel in enumerate(ordered, 1):
            config_path = records[rel]['path']
            sdk_root_raw = records[rel].get('sdk_root', '')
            sdk_root = self._resolve_sdk_root(config_path, sdk_root_raw) if sdk_root_raw else ''
            status, own_reason = self._get_install_status_detail(config_path, sdk_root)
            records[rel]['reinstall_reason'] = own_reason
            # Propagate reinstalls through the dependency graph: an installed
            # sdk embeds its dependencies' state (paths, versions, exported
            # environments), so a dependent must be regenerated whenever a
            # dependency is installed fresh or reinstalled. `ordered` is a
            # topological order, so every dependency's status — including its
            # own propagated upgrade — is already final here, which makes the
            # propagation transitive. Dependencies without an sdk_root are
            # excluded on purpose: their install steps run on every install
            # anyway and they carry no marker, so they would otherwise force
            # a reinstall of every dependent on every run.
            if status == "up to date":
                triggered_dep = next(
                    (dep_rel for dep_rel in records[rel]['dep_rels']
                     if records[dep_rel]['install_status'] in ("missing", "reinstall-needed")),
                    None)
                if triggered_dep is not None:
                    status = "reinstall-needed"
                    records[rel]['reinstall_reason'] = (
                        f"dependency '{triggered_dep}' is missing or being reinstalled")
            status_counts[status] = status_counts.get(status, 0) + 1
            records[rel]['install_status'] = status
            line = f"  {index:>2}. {self._colorize(rel.ljust(name_width), status, light=True)}  [{self._colorize(self._status_tag(status), status, light=True)}]"
            if records[rel]['reinstall_reason']:
                line += " " + self._colorize(records[rel]['reinstall_reason'], status)
            print(line)
            for name, value in records[rel]['variables'].items():
                print(self._colorize(f"        - {name}={value}", status))

        def _summary_line(status, note):
            tag = f"[{self._status_tag(status)}]".ljust(len("[REINSTALL-NEEDED]"))
            print(f"  {self._colorize(tag, status, light=True)}  {status_counts.get(status, 0)} ({note})")

        print("\nInstall plan:")
        _summary_line("up to date", "no reinstall needed")
        _summary_line("missing", "fresh install")
        _summary_line("reinstall-needed", "sdk root will be removed and reinstalled (own config or a dependency changed)")
        _summary_line("no sdk_root", "no marker mechanism; install steps run every time")

        # Nothing missing and nothing to reinstall: skip the confirmation
        # prompt, the install pass and the run summary entirely.
        if status_counts.get("missing", 0) + status_counts.get("reinstall-needed", 0) == 0:
            print("\nNothing to install — all configs are already up to date. Exiting.")
            self.m_nothing_to_do = True
            return

        if not self._confirm_proceed():
            self.m_user_aborted = True
            print("Aborted by user. No changes were made.")
            return

        self.m_progress_bar.start(
            len(ordered),
            status_counts.get("missing", 0) + status_counts.get("reinstall-needed", 0))

        # Process each config file in dependency order.
        applied_env_rels = set()
        for rel in ordered:
            config_path = records[rel]['path']
            # Friendly display: show path relative to configs folder
            try:
                display_name = os.path.relpath(config_path, self.m_configs_root_path)
            except Exception:
                display_name = os.path.basename(config_path)

            config_started = time.monotonic()

            print(f"\n{'='*70}")
            print(f"Processing config: {display_name}")
            print(f"{'='*70}")
            self.m_current_config = display_name
            self.m_current_node = None
            self.m_current_install_step = None
            self.m_progress_bar.begin_config(display_name)

            sdk_root = ""
            try:
                # Apply the environments exported by this config's dependencies
                # (from their generator_active_batch declarations, whether or not
                # they are being reinstalled) so install steps below can use the
                # tools those dependencies provide. Kept inside the try so a
                # failure here records this config as FAILED in the run summary
                # instead of aborting the run without any summary entry.
                for dep_rel in ordered:
                    if dep_rel not in dep_closure[rel] or dep_rel in applied_env_rels:
                        continue
                    applied_env_rels.add(dep_rel)
                    if not records[dep_rel]['batch_environments']:
                        continue
                    print(f"\nApplying environments from dependency: {records[dep_rel]['base']}")
                    # Interpolate at apply time: dependencies processed earlier in
                    # this run may carry 'set_variables' values that did not exist
                    # at plan time (fresh installs).
                    batch_env = self._interpolate_config_variables(
                        records[dep_rel]['batch_environments'],
                        records[dep_rel]['effective_variables'],
                        records[dep_rel]['path'])
                    self._process_environments(batch_env, None)

                sdk_root_raw = records[rel].get('sdk_root', '')
                if sdk_root_raw:
                    sdk_root = self._resolve_sdk_root(config_path, sdk_root_raw)
                    # Wipes the sdk root when its own config copy changed, or
                    # when a dependency forced a reinstall through the
                    # propagated reinstall_reason. After a wipe the status
                    # check below reports "missing", so everything that must
                    # install falls through to install_from_config.
                    self._validate_installed_config_state(
                        config_path, sdk_root, records[rel].get('reinstall_reason'),
                        preserve_rel_paths=records[rel].get('preserve_on_reinstall') or [])
                    if self._get_install_status(config_path, sdk_root) == "up to date":
                        print(self._colorize("Already installed and up to date, skipping install.", "up to date"))
                        self._record_config_summary(display_name, "SKIPPED", "already installed (config unchanged)", records[rel]['variables'])
                        self.m_progress_bar.finish_config(skipped=True)
                        continue
                self.install_from_config(config_path, records[rel]['effective_variables'])
            except Exception as e:
                self._remove_failed_sdk_root(
                    sdk_root, display_name,
                    preserve_rel_paths=records[rel].get('preserve_on_reinstall') or [])
                self._record_config_summary(display_name, "FAILED", str(e), records[rel]['variables'])
                self._record_unprocessed_configs(ordered, records)
                raise

            if sdk_root:
                self._store_installed_config_marker(config_path, sdk_root)
            # A config without sdk_root installs no SDK: its steps just ran (as
            # they do on every run), so record it as 'no sdk_root' — it must not
            # count as a new SDK install.
            self._record_config_summary(
                display_name, "SUCCESS" if sdk_root else "no sdk_root",
                variables=records[rel]['variables'],
                duration_seconds=time.monotonic() - config_started)
            self.m_progress_bar.finish_config(
                work=records[rel].get('install_status') in ("missing", "reinstall-needed"))

def main():
    dev_env_installer = WorkspaceInstaller()
    run_error = None
    try:
        try:
            dev_env_installer.install_all()
        finally:
            # Always release the terminal's reserved status row, even when the
            # install aborts with an exception or KeyboardInterrupt.
            dev_env_installer.m_progress_bar.stop()
    except Exception as e:
        run_error = e

    if dev_env_installer.m_nothing_to_do:
        sys.exit(0)

    if dev_env_installer.m_user_aborted:
        print("\nInstall aborted by user (confirmation declined).")
        sys.exit(1)

    summary_text = dev_env_installer.build_run_summary(run_error)
    # Console copy is colored; summary.txt gets the same text with the color
    # escapes stripped so the file stays plain
    summary_path = dev_env_installer.write_run_summary(_ANSI_ESCAPE_PATTERN.sub("", summary_text))
    print("\n" + summary_text)
    print(f"Summary written to: {summary_path}")

    if run_error:
        print(f"Install failed: {run_error}", file=sys.stderr)
        sys.exit(1)
    
if __name__ == "__main__":
    main()
