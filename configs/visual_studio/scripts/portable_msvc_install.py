#!/usr/bin/env python3

import argparse
import hashlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

# NOTE: not all host & target architecture combinations are supported.
DEFAULT_HOST = "x64"
ALL_HOSTS = "x64 x86 arm64".split()

DEFAULT_TARGET = "x64"
ALL_TARGETS = "x64 x86 arm arm64".split()

DEFAULT_VERSION = "latest"
ALL_VERSIONS = "2019 2022 2026 latest".split()

MANIFEST_URLS = {
    "latest": ["https://aka.ms/vs/stable/channel", "https://aka.ms/vs/insiders/channel"],
    "2026": ["https://aka.ms/vs/18/stable/channel", "https://aka.ms/vs/18/insiders/channel"],
    "2022": ["https://aka.ms/vs/17/release/channel", "https://aka.ms/vs/17/pre/channel"],
    "2019": ["https://aka.ms/vs/16/release/channel", "https://aka.ms/vs/16/pre/channel"],
}


def first(items, cond=lambda x: True):
    return next((item for item in items if cond(item)), None)


def get_msi_cabs(msi_blob):
    # Basic parser to find referenced .cab payload names in MSI binary.
    index = 0
    while True:
        index = msi_blob.find(b".cab", index + 4)
        if index < 0:
            return
        yield msi_blob[index - 32:index + 4].decode("ascii")


class PortableMsvcInstaller:
    def __init__(self, msvc_output_dir, sdk_output_dir, downloads_dir, ssl_context=None):
        self.msvc_output = msvc_output_dir
        self.sdk_output = sdk_output_dir
        self.downloads = downloads_dir
        self.ssl_context = ssl_context
        self.total_download = 0

    def download(self, url):
        with urllib.request.urlopen(url, context=self.ssl_context) as res:
            return res.read()

    def download_progress(self, url, sha256, filename):
        path = self.downloads / filename
        path.parent.mkdir(parents=True, exist_ok=True)

        if path.exists():
            data = path.read_bytes()
            if hashlib.sha256(data).hexdigest().lower() == sha256.lower():
                print(f"\r{filename} ... OK")
                return data

        with path.open("wb") as out:
            data_buf = io.BytesIO()
            with urllib.request.urlopen(url, context=self.ssl_context) as res:
                total = int(res.headers.get("Content-Length", "0"))
                size = 0
                while True:
                    block = res.read(1 << 20)
                    if not block:
                        break
                    out.write(block)
                    data_buf.write(block)
                    size += len(block)
                    if total > 0:
                        pct = size * 100 // total
                        print(f"\r{filename} ... {pct}%", end="")
            print()

        data = data_buf.getvalue()
        digest = hashlib.sha256(data).hexdigest().lower()
        if digest != sha256.lower():
            sys.exit(f"Hash mismatch for {filename}")
        self.total_download += len(data)
        return data

    def get_main_manifest(self, vs_version, insiders):
        url = MANIFEST_URLS[vs_version][1 if insiders else 0]
        try:
            return json.loads(self.download(url))
        except urllib.error.URLError as err:
            import ssl

            if not isinstance(err.args[0], ssl.SSLCertVerificationError):
                raise

            print("ERROR: SSL certificate verification error")
            try:
                import certifi
            except ModuleNotFoundError:
                print("ERROR: please install 'certifi' package to use Mozilla certificates")
                print("ERROR: or update your Windows certs: https://woshub.com/updating-trusted-root-certificates-in-windows-10/#h2_3")
                sys.exit(1)

            print("NOTE: retrying with certifi certificates")
            self.ssl_context = ssl.create_default_context(cafile=certifi.where())
            return json.loads(self.download(url))

    @staticmethod
    def parse_versions(vsmanifest):
        packages = {}
        for pkg in vsmanifest["packages"]:
            packages.setdefault(pkg["id"].lower(), []).append(pkg)

        msvc_versions = {}
        sdk_versions = {}

        for pkg_id in packages:
            if (
                pkg_id.startswith("microsoft.vc.")
                and pkg_id.endswith(".tools.hostx64.targetx64.base")
                and "premium" not in pkg_id
            ):
                version = ".".join(pkg_id.split(".")[2:4])
                if version and version[0].isdigit():
                    msvc_versions[version] = pkg_id
            elif pkg_id.startswith("microsoft.visualstudio.component.windows10sdk.") or pkg_id.startswith(
                "microsoft.visualstudio.component.windows11sdk."
            ):
                version = pkg_id.split(".")[-1]
                if version.isnumeric():
                    sdk_versions[version] = pkg_id

        return packages, msvc_versions, sdk_versions

    @staticmethod
    def _latest_numeric_version(items):
        def key(v):
            parts = []
            for part in v.split("."):
                parts.append(int(part) if part.isdigit() else 0)
            return tuple(parts)

        return max(items, key=key)

    def download_msvc(self, packages, msvc_ver, host, targets):
        msvc_packages = [
            "microsoft.visualcpp.dia.sdk",
            f"microsoft.vc.{msvc_ver}.crt.headers.base",
            f"microsoft.vc.{msvc_ver}.crt.source.base",
            f"microsoft.vc.{msvc_ver}.asan.headers.base",
            f"microsoft.vc.{msvc_ver}.pgo.headers.base",
        ]

        for target in targets:
            msvc_packages += [
                f"microsoft.vc.{msvc_ver}.tools.host{host}.target{target}.base",
                f"microsoft.vc.{msvc_ver}.tools.host{host}.target{target}.res.base",
                f"microsoft.vc.{msvc_ver}.crt.{target}.desktop.base",
                f"microsoft.vc.{msvc_ver}.crt.{target}.store.base",
                f"microsoft.vc.{msvc_ver}.premium.tools.host{host}.target{target}.base",
                f"microsoft.vc.{msvc_ver}.pgo.{target}.base",
            ]
            if target in ["x86", "x64"]:
                msvc_packages += [f"microsoft.vc.{msvc_ver}.asan.{target}.base"]

            redist_suffix = ".onecore.desktop" if target == "arm" else ""
            redist_pkg = f"microsoft.vc.{msvc_ver}.crt.redist.{target}{redist_suffix}.base"
            if redist_pkg not in packages:
                redist_name = f"microsoft.visualcpp.crt.redist.{target}{redist_suffix}"
                redist = first(packages[redist_name])
                redist_pkg = first(redist["dependencies"], lambda dep: dep.endswith(".base")).lower()
            msvc_packages += [redist_pkg]

        for pkg in sorted(msvc_packages):
            if pkg not in packages:
                print(f"\r{pkg} ... !!! MISSING !!!")
                continue
            package = first(packages[pkg], lambda p: p.get("language") in (None, "en-US"))
            for payload in package["payloads"]:
                filename = payload["fileName"]
                self.download_progress(payload["url"], payload["sha256"], filename)
                with zipfile.ZipFile(self.downloads / filename) as archive:
                    for name in archive.namelist():
                        if not name.startswith("Contents/"):
                            continue
                        out_path = self.msvc_output / Path(name).relative_to("Contents")
                        out_path.parent.mkdir(parents=True, exist_ok=True)
                        out_path.write_bytes(archive.read(name))

    def download_windows_sdk(self, packages, sdk_pid, targets):
        sdk_packages = [
            "Windows SDK for Windows Store Apps Tools-x86_en-us.msi",
            "Windows SDK for Windows Store Apps Headers-x86_en-us.msi",
            "Windows SDK for Windows Store Apps Headers OnecoreUap-x86_en-us.msi",
            "Windows SDK for Windows Store Apps Libs-x86_en-us.msi",
            "Universal CRT Headers Libraries and Sources-x86_en-us.msi",
        ]

        for target in ALL_TARGETS:
            sdk_packages += [
                f"Windows SDK Desktop Headers {target}-x86_en-us.msi",
                f"Windows SDK OnecoreUap Headers {target}-x86_en-us.msi",
            ]

        for target in targets:
            sdk_packages += [f"Windows SDK Desktop Libs {target}-x86_en-us.msi"]

        with tempfile.TemporaryDirectory(dir=self.downloads) as _tmp:
            sdk_pkg = packages[sdk_pid][0]
            sdk_pkg = packages[first(sdk_pkg["dependencies"]).lower()][0]

            msi_files = []
            cabs = []

            for pkg in sorted(sdk_packages):
                payload = first(sdk_pkg["payloads"], lambda p: p["fileName"] == f"Installers\\{pkg}")
                if payload is None:
                    continue
                msi_files.append(self.downloads / pkg)
                data = self.download_progress(payload["url"], payload["sha256"], pkg)
                cabs += list(get_msi_cabs(data))

            for cab in cabs:
                payload = first(sdk_pkg["payloads"], lambda p: p["fileName"] == f"Installers\\{cab}")
                if payload is None:
                    continue
                self.download_progress(payload["url"], payload["sha256"], cab)

            print("Unpacking MSI files...")
            for msi in msi_files:
                subprocess.check_call(f'msiexec.exe /a "{msi}" /quiet /qn TARGETDIR="{self.sdk_output.resolve()}"')
                extracted_msi = self.sdk_output / msi.name
                if extracted_msi.exists():
                    extracted_msi.unlink()

            windowskits = self.sdk_output / "WindowsKits"
            if not windowskits.exists():
                legacy = first(
                    self.sdk_output.iterdir(),
                    lambda p: p.is_dir() and p.name.replace(" ", "").lower() == "windowskits" and p.name != "WindowsKits",
                )
                if legacy is not None:
                    legacy.rename(windowskits)

    def finalize_layout(self, host, targets):
        msvcv = first((self.msvc_output / "VC/Tools/MSVC").glob("*")).name
        sdkv = first((self.sdk_output / "WindowsKits/10/bin").glob("*")).name

        redist = self.msvc_output / "VC/Redist"
        if redist.exists():
            redistv = first((redist / "MSVC").glob("*")).name
            src = redist / "MSVC" / redistv / "debug_nonredist"
            for target in targets:
                for dll in (src / target).glob("**/*.dll"):
                    dst = self.msvc_output / "VC/Tools/MSVC" / msvcv / f"bin/Host{host}" / target
                    dst.mkdir(parents=True, exist_ok=True)
                    dll.replace(dst / dll.name)
            shutil.rmtree(redist)

        msdia140dll = {
            "x86": "msdia140.dll",
            "x64": "amd64/msdia140.dll",
            "arm": "arm/msdia140.dll",
            "arm64": "arm64/msdia140.dll",
        }

        dst = self.msvc_output / "VC/Tools/MSVC" / msvcv / f"bin/Host{host}"
        src = self.msvc_output / "DIA%20SDK/bin" / msdia140dll[host]
        for target in targets:
            shutil.copyfile(src, dst / target / src.name)

        shutil.rmtree(self.msvc_output / "DIA%20SDK")

        shutil.rmtree(self.msvc_output / "Common7", ignore_errors=True)
        shutil.rmtree(self.msvc_output / "VC/Tools/MSVC" / msvcv / "Auxiliary", ignore_errors=True)

        for target in targets:
            for folder in ["store", "uwp", "enclave", "onecore"]:
                shutil.rmtree(self.msvc_output / "VC/Tools/MSVC" / msvcv / "lib" / target / folder, ignore_errors=True)
            shutil.rmtree(self.msvc_output / "VC/Tools/MSVC" / msvcv / f"bin/Host{host}" / target / "onecore", ignore_errors=True)

        for folder in ["Catalogs", "DesignTime", f"bin/{sdkv}/chpe", f"Lib/{sdkv}/ucrt_enclave"]:
            shutil.rmtree(self.sdk_output / "WindowsKits/10" / folder, ignore_errors=True)

        for arch in ALL_TARGETS:
            if arch not in targets:
                shutil.rmtree(self.sdk_output / "WindowsKits/10/Lib" / sdkv / "ucrt" / arch, ignore_errors=True)
                shutil.rmtree(self.sdk_output / "WindowsKits/10/Lib" / sdkv / "um" / arch, ignore_errors=True)
            if arch != host:
                shutil.rmtree(self.msvc_output / "VC/Tools/MSVC" / msvcv / f"bin/Host{arch}", ignore_errors=True)
                shutil.rmtree(self.sdk_output / "WindowsKits/10/bin" / sdkv / arch, ignore_errors=True)

        for target in targets:
            (self.msvc_output / "VC/Tools/MSVC" / msvcv / f"bin/Host{host}/{target}/vctip.exe").unlink(missing_ok=True)

        build = self.msvc_output / "VC/Auxiliary/Build"
        build.mkdir(parents=True, exist_ok=True)
        (build / "vcvarsall.bat").write_text(
            "rem both bat files are here only for nvcc, do not call them manually",
            encoding="utf-8",
        )
        (build / "vcvars64.bat").touch()

        sdk_dir = str(self.sdk_output.resolve())

        for target in targets:
            setup = rf"""@echo off

set VSCMD_ARG_HOST_ARCH={host}
set VSCMD_ARG_TGT_ARCH={target}

set VCToolsVersion={msvcv}
set WindowsSDKVersion={sdkv}\

set VCToolsInstallDir=%~dp0VC\Tools\MSVC\{msvcv}\
set WindowsSdkBinPath={sdk_dir}\WindowsKits\10\bin\

set PATH=%~dp0VC\Tools\MSVC\{msvcv}\bin\Host{host}\{target};{sdk_dir}\WindowsKits\10\bin\{sdkv}\{host};{sdk_dir}\WindowsKits\10\bin\{sdkv}\{host}\ucrt;%PATH%
set INCLUDE=%~dp0VC\Tools\MSVC\{msvcv}\include;{sdk_dir}\WindowsKits\10\Include\{sdkv}\ucrt;{sdk_dir}\WindowsKits\10\Include\{sdkv}\shared;{sdk_dir}\WindowsKits\10\Include\{sdkv}\um;{sdk_dir}\WindowsKits\10\Include\{sdkv}\winrt;{sdk_dir}\WindowsKits\10\Include\{sdkv}\cppwinrt
set LIB=%~dp0VC\Tools\MSVC\{msvcv}\lib\{target};{sdk_dir}\WindowsKits\10\Lib\{sdkv}\ucrt\{target};{sdk_dir}\WindowsKits\10\Lib\{sdkv}\um\{target}
"""
            (self.msvc_output / f"setup_{target}.bat").write_text(setup, encoding="utf-8")

        metadata = {
            "host": host,
            "targets": targets,
            "msvc_version": msvcv,
            "sdk_version": sdkv,
            "msvc_root": str(self.msvc_output.resolve()),
            "sdk_root": str(self.sdk_output.resolve()),
        }
        (self.msvc_output / "portable_msvc.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def _parse_msvc_version_prefix(value):
    """Extract the major.minor toolset prefix from a full or short MSVC version.

    The VS manifest keys toolsets by 'major.minor' (e.g. '14.51').
    Accepts both short form '14.51' and full form '14.51.36014'.

    Examples:
      '14.51'       -> '14.51'
      '14.51.36014' -> '14.51'
    """
    parts = value.strip().split(".")
    if len(parts) < 2:
        sys.exit(f"Invalid --msvc-version: {value!r}. Expected at least 'major.minor', e.g. 14.51 or 14.51.36014.")
    return f"{parts[0]}.{parts[1]}"


def _parse_sdk_build_number(value):
    """Accept either a bare build number ('26100') or full dotted form ('10.0.26100.7705')
    and return the bare build number string used by the VS manifest package IDs."""
    if not value:
        return value
    # Strip optional leading 'NN.N.' prefix (e.g. '10.0.') and optional trailing '.PATCH'
    parts = value.split(".")
    # Full form: 10.0.26100.7705 → 4 parts; extract the 3rd
    if len(parts) >= 3 and not parts[0].isnumeric() is False and int(parts[0]) < 20:
        # Heuristic: first segment is a small number like 10 → dotted SDK form
        build = parts[2]
    else:
        # Already a bare build number
        build = parts[0]
    if not build.isnumeric():
        sys.exit(f"Cannot parse Windows SDK build number from: {value}")
    return build


def _parse_bool_arg(value, *, arg_name):
    if isinstance(value, bool):
        return value
    val = str(value).strip().lower()
    if val in {"1", "true", "yes", "y", "on"}:
        return True
    if val in {"0", "false", "no", "n", "off"}:
        return False
    sys.exit(f"Invalid {arg_name}: {value!r}. Expected true/false.")


def _find_sdk_version_dirs(sdk_output, sdk_build):
    root = sdk_output / "WindowsKits/10/bin"
    if not root.exists():
        return []
    return [p for p in root.glob(f"10.0.{sdk_build}.*") if p.is_dir()]


def _toolchain_already_installed(msvc_output, sdk_output, msvc_version, sdk_build):
    msvc_dir = msvc_output / "VC/Tools/MSVC" / msvc_version
    sdk_dirs = _find_sdk_version_dirs(sdk_output, sdk_build)
    return msvc_dir.exists() and len(sdk_dirs) > 0, msvc_dir, sdk_dirs


def _find_msvc_version_dirs_from_arg(msvc_output, msvc_version_arg):
    root = msvc_output / "VC/Tools/MSVC"
    if not root.exists() or not msvc_version_arg:
        return []

    parts = msvc_version_arg.strip().split(".")
    if len(parts) >= 3:
        exact = root / msvc_version_arg.strip()
        return [exact] if exact.exists() else []

    if len(parts) >= 2:
        return [p for p in root.glob(f"{parts[0]}.{parts[1]}*") if p.is_dir()]

    return []


def _toolchain_already_installed_from_args(msvc_output, sdk_output, msvc_version_arg, windows_sdk_version_arg):
    msvc_dirs = _find_msvc_version_dirs_from_arg(msvc_output, msvc_version_arg)
    sdk_build = _parse_sdk_build_number(windows_sdk_version_arg)
    sdk_dirs = _find_sdk_version_dirs(sdk_output, sdk_build)
    return len(msvc_dirs) > 0 and len(sdk_dirs) > 0, msvc_dirs, sdk_dirs


def parse_args():
    ap = argparse.ArgumentParser(description="Install portable MSVC + Windows SDK")
    ap.add_argument("--show-versions", action="store_true", help="Show available MSVC and Windows SDK versions")
    ap.add_argument("--accept-license", action="store_true", help="Automatically accept license")
    ap.add_argument("--msvc-version", help="MSVC toolset version, short or full, e.g. 14.51 or 14.51.36014.")
    ap.add_argument("--windows-sdk-version", help="Windows SDK version, e.g. 10.0.26100.7705 or bare build 26100")
    ap.add_argument("--vs", default=DEFAULT_VERSION, choices=ALL_VERSIONS, help="Visual Studio channel family")
    ap.add_argument("--insiders", "--preview", action="store_true", help="Use insiders/preview feed")
    ap.add_argument("--target", dest="targets", action="append", choices=ALL_TARGETS, metavar="ARCH",
                    help=f"Target architecture, repeat for multiple. Choices: {', '.join(ALL_TARGETS)}")
    ap.add_argument("--host", default=DEFAULT_HOST, choices=ALL_HOSTS, help="Host architecture")
    ap.add_argument("--msvc-output", default="msvc", help="Output directory for MSVC toolset")
    ap.add_argument("--windows-sdk-output", default="win_sdk", help="Output directory for Windows SDK")
    ap.add_argument("--downloads", default="downloads", help="Persistent downloads directory")
    ap.add_argument(
        "--skip-if-output-folder-exists",
        default="false",
        help="Skip install when both versioned MSVC and Windows SDK output folders already exist (true/false)",
    )
    return ap.parse_args()


def main():
    args = parse_args()

    host = args.host
    targets = args.targets or [DEFAULT_TARGET]

    msvc_output = Path(args.msvc_output)
    sdk_output = Path(args.windows_sdk_output)
    downloads = Path(args.downloads)

    skip_if_output_folder_exists = _parse_bool_arg(
        args.skip_if_output_folder_exists,
        arg_name="--skip-if-output-folder-exists",
    )

    if skip_if_output_folder_exists and args.msvc_version and args.windows_sdk_version:
        installed, msvc_dirs, sdk_dirs = _toolchain_already_installed_from_args(
            msvc_output,
            sdk_output,
            args.msvc_version,
            args.windows_sdk_version,
        )
        if installed:
            print("Skipping install before manifest download because versioned output folders already exist:")
            print(f"  MSVC: {', '.join(str(p) for p in msvc_dirs)}")
            print(f"  SDK:  {', '.join(str(p) for p in sdk_dirs)}")
            return 0

    installer = PortableMsvcInstaller(msvc_output_dir=msvc_output, sdk_output_dir=sdk_output, downloads_dir=downloads)

    print("Fetching Visual Studio manifests...")
    manifest = installer.get_main_manifest(args.vs, args.insiders)

    item_name = "Microsoft.VisualStudio.Manifests.VisualStudioPreview" if args.insiders else "Microsoft.VisualStudio.Manifests.VisualStudio"
    vs = first(manifest["channelItems"], lambda x: x["id"] == item_name)
    payload = vs["payloads"][0]["url"]
    vsmanifest = json.loads(installer.download(payload))

    packages, msvc_versions, sdk_versions = installer.parse_versions(vsmanifest)

    if args.show_versions:
        print("MSVC versions:", " ".join(sorted(msvc_versions.keys())))
        print("Windows SDK versions:", " ".join(sorted(sdk_versions.keys())))
        return 0

    if not msvc_versions or not sdk_versions:
        sys.exit("Unable to resolve available MSVC/Windows SDK versions from manifest")

    if args.msvc_version:
        toolset_prefix = _parse_msvc_version_prefix(args.msvc_version)
        candidates = [v for v in msvc_versions if v.startswith(toolset_prefix)]
        if not candidates:
            sys.exit(
                f"No MSVC toolset found for version {args.msvc_version!r} "
                f"(prefix {toolset_prefix!r}). "
                f"Available: {' '.join(sorted(msvc_versions))}"
            )
        msvc_ver = installer._latest_numeric_version(candidates)
        print(f"--msvc-version {args.msvc_version} -> prefix {toolset_prefix} -> selected toolset {msvc_ver}")
    else:
        msvc_ver = installer._latest_numeric_version(msvc_versions.keys())

    sdk_build = _parse_sdk_build_number(args.windows_sdk_version) if args.windows_sdk_version else None
    sdk_ver = sdk_build or installer._latest_numeric_version(sdk_versions.keys())

    if msvc_ver not in msvc_versions:
        sys.exit(f"Unknown MSVC toolset version: {msvc_ver}. Available: {' '.join(sorted(msvc_versions))}")
    if sdk_ver not in sdk_versions:
        sys.exit(f"Unknown Windows SDK version: {args.windows_sdk_version!r} (resolved build: {sdk_ver}). Available: {' '.join(sorted(sdk_versions))}")

    msvc_pid = msvc_versions[msvc_ver]
    msvc_ver = msvc_pid.removeprefix("microsoft.vc.").removesuffix(".tools.hostx64.targetx64.base")
    sdk_pid = sdk_versions[sdk_ver]

    if skip_if_output_folder_exists:
        installed, msvc_dir, sdk_dirs = _toolchain_already_installed(msvc_output, sdk_output, msvc_ver, sdk_ver)
        if installed:
            sdk_dirs_text = ", ".join(str(p) for p in sdk_dirs)
            print("Skipping install because versioned output folders already exist:")
            print(f"  MSVC: {msvc_dir}")
            print(f"  SDK:  {sdk_dirs_text}")
            return 0

    print(f"Preparing portable toolchain: MSVC v{msvc_ver}, Windows SDK v{sdk_ver}")

    tools = first(manifest["channelItems"], lambda x: x["id"] == "Microsoft.VisualStudio.Product.BuildTools")
    resource = first(tools["localizedResources"], lambda x: x["language"] == "en-us")
    license_url = resource["license"]

    if not args.accept_license:
        accept = input(f"Do you accept Visual Studio license at {license_url} [Y/N] ? ")
        if not accept or accept[0].lower() != "y":
            return 0

    msvc_output.mkdir(parents=True, exist_ok=True)
    sdk_output.mkdir(parents=True, exist_ok=True)
    downloads.mkdir(parents=True, exist_ok=True)

    installer.download_msvc(packages, msvc_ver, host, targets)
    installer.download_windows_sdk(packages, sdk_pid, targets)
    installer.finalize_layout(host, targets)

    print(f"Total downloaded: {installer.total_download >> 20} MB")
    print(f"Portable MSVC installed at: {msvc_output.resolve()}")
    print(f"Windows SDK installed at:   {sdk_output.resolve()}")
    print("Done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
