#!/usr/bin/env python
"""Download the raw datasets SP1 uses, verify them, and unpack them.

Datasets are never committed (see ``data/README.md``), so a fresh clone has to be
able to rebuild ``data/raw/`` from a URL plus a checksum. That is what this script
does: download -> verify SHA-256 -> unpack (including nested archives) -> print the
command that consumes the result.

Usage
-----
    python subprojects/sp1-data-forecasting/scripts/fetch_datasets.py --list
    python subprojects/sp1-data-forecasting/scripts/fetch_datasets.py --dataset cn-charging-orders
    python subprojects/sp1-data-forecasting/scripts/fetch_datasets.py --all

A proxy is honoured through the usual ``HTTPS_PROXY`` / ``HTTP_PROXY`` environment
variables (urllib reads them), which is what this machine needs for GitHub, and is
harmless for figshare.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from sp1.config import repo_root, sp1_settings

#: Downloadable datasets. ``sha256`` is what this project actually downloaded and
#: checked; if upstream changes the file, the mismatch is reported rather than
#: silently accepted.
REGISTRY: dict[str, dict] = {
    "cn-charging-orders": {
        "dir": "figshare-28263986",
        "url": "https://ndownloader.figshare.com/files/51875117",
        "filename": "Charging_Record_Data.zip",
        "size_bytes": 13_513_961,
        "sha256": "54deec46afa5d39a6803ef15d694bcfe598f971f6551a0baf7809a1a039a060c",
        "licence": "MIT",
        "citation": (
            "Yu, Q. et al., 'Electric vehicle charging order data', figshare, "
            "DOI 10.6084/m9.figshare.28263986.v1"
        ),
        "landing_url": (
            "https://figshare.com/articles/dataset/Electric_vehicle_charging_order_data/28263986"
        ),
        "nested_archives": [
            "Charging_Record_Data-main/Beijing_charge_orders.zip",
            "Charging_Record_Data-main/Shanghai_charge_orders.zip",
            "Charging_Record_Data-main/Guangzhou_charge_orders.zip",
        ],
        "extract_to": "csv",
        "run": "--dataset cn-charging-orders",
    },
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dataset", help="registry key to fetch")
    group.add_argument("--all", action="store_true", help="fetch every registered dataset")
    group.add_argument("--list", action="store_true", help="list registry entries and exit")
    parser.add_argument("--force", action="store_true", help="re-download even if the file exists")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Fetch the requested datasets."""
    _force_utf8_stdout()
    args = parse_args(argv)

    if args.list:
        for key, entry in REGISTRY.items():
            print(f"{key}\n  {entry['citation']}\n  licence: {entry['licence']}\n  {entry['url']}")
        return 0

    keys = list(REGISTRY) if args.all else [args.dataset]
    unknown = [key for key in keys if key not in REGISTRY]
    if unknown:
        print(f"ERROR: unknown dataset(s) {unknown}; known: {sorted(REGISTRY)}", file=sys.stderr)
        return 2

    raw_dir = sp1_settings(root=repo_root()).raw_dir
    for key in keys:
        entry = REGISTRY[key]
        archive = raw_dir / entry.get("dir", key) / entry["filename"]
        print(f"[{key}] {entry['citation']}")
        print(f"[{key}] licence: {entry['licence']} — {entry['landing_url']}")
        _download(entry["url"], archive, entry, force=args.force)
        target = raw_dir / entry.get("dir", key) / entry["extract_to"]
        _unpack(archive, target)
        for nested in entry.get("nested_archives", []):
            _unpack_nested(archive, nested, target)
        print(f"[{key}] ready under {target}")
        print(f"[{key}] next: python subprojects/sp1-data-forecasting/scripts/run_sp1.py {entry['run']}")
    return 0


def _download(url: str, destination: Path, entry: dict, force: bool) -> None:
    """Download ``url`` to ``destination`` and verify size and checksum."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not force:
        if _verify(destination, entry):
            print(f"  already present and verified: {destination.name}")
            return
        print(f"  {destination.name} failed verification; re-downloading")
    print(f"  downloading {url}")
    with urllib.request.urlopen(url) as response, destination.open("wb") as handle:
        shutil.copyfileobj(response, handle)
    if not _verify(destination, entry):
        raise SystemExit(
            f"ERROR: {destination} does not match the recorded size/checksum. "
            "Datasets are pinned deliberately — check upstream before trusting it."
        )


def _verify(path: Path, entry: dict) -> bool:
    """Check file size and SHA-256 against the registry entry."""
    if not path.is_file():
        return False
    if entry.get("size_bytes") and path.stat().st_size != entry["size_bytes"]:
        return False
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest() == entry["sha256"]


def _unpack(archive: Path, target: Path) -> None:
    """Extract ``archive`` into ``target``, skipping macOS metadata entries."""
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        members = [m for m in bundle.namelist() if "__MACOSX" not in m and not m.endswith("/")]
        bundle.extractall(target, members=members)
    print(f"  extracted {len(members)} file(s) -> {target}")


def _unpack_nested(archive: Path, member: str, target: Path) -> None:
    """Extract an archive that lives *inside* ``archive`` into ``target/<stem>``."""
    with zipfile.ZipFile(archive) as bundle, bundle.open(member) as handle:
        inner = zipfile.ZipFile(handle)
        destination = target / Path(member).stem
        destination.mkdir(parents=True, exist_ok=True)
        members = [
            m for m in inner.namelist() if "__MACOSX" not in m and not m.endswith("/")
        ]
        inner.extractall(destination, members=members)
    print(f"  extracted nested {Path(member).name} -> {destination}")


def _force_utf8_stdout() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:  # pragma: no cover
        pass


if __name__ == "__main__":
    raise SystemExit(main())
