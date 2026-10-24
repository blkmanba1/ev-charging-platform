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
import csv
import hashlib
import json
import os
import shutil
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from sp1.config import repo_root, sp1_settings

ARCGIS_PAGE_SIZE = 1000

#: Downloadable datasets. ``sha256`` is what this project actually downloaded and
#: checked; if upstream changes the file, the mismatch is reported rather than
#: silently accepted. ArcGIS layers are paged live services, so they record an
#: observed row count instead — their byte hash is not reproducible.
REGISTRY: dict[str, dict] = {
    "us-caltech-acn": {
        "kind": "acn_api",
        "dir": "acn-data",
        "filename": "ACN_Data_sessions.csv",
        "sites": ["caltech", "jpl", "office001"],
        "token_env": "ACN_API_TOKEN",
        "licence": (
            "Caltech ACN-Data terms — free for educational and research use; "
            "redistribution is NOT granted, so the data stays git-ignored"
        ),
        "citation": (
            "Lee, Z. J., Li, T., & Low, S. H. (2019). ACN-Data: Analysis and Applications "
            "of an Open EV Charging Dataset. e-Energy '19. https://ev.caltech.edu/dataset"
        ),
        "landing_url": "https://ev.caltech.edu/dataset",
        "run": "--dataset us-caltech-acn",
    },
    "us-palo-alto-ev": {
        "kind": "file",
        "dir": "palo-alto-194693",
        "url": (
            "https://data.paloalto.gov/datasets/"
            "194693-electric-vehicle-charging-station-usage-july-2011-dec-2020.download/"
        ),
        "filename": "ChargePoint_Data_2011-2020.download",
        "size_bytes": 85_445_823,
        "sha256": "e65f5f5d3861cdd6bf3da2de97aabe590d7708e001db1532202eec52081ba82c",
        "licence": "PDDL (public domain dedication)",
        "citation": (
            "City of Palo Alto Open Data, 'Electric Vehicle Charging Station Usage "
            "(July 2011 - Dec 2020)', data.paloalto.gov"
        ),
        "landing_url": (
            "https://data.paloalto.gov/datasets/"
            "194693-electric-vehicle-charging-station-usage-july-2011-dec-2020/"
        ),
        "run": "--dataset us-palo-alto-ev",
    },
    "us-boulder-ev": {
        "kind": "arcgis",
        "dir": "boulder-ev",
        "service": (
            "https://services.arcgis.com/ePKBjXrBZ2vEEgWd/arcgis/rest/services/"
            "Electric_Vehicle_Charging_Station_Data/FeatureServer/0"
        ),
        "filename": "Boulder_EV_Charging_Station_Data.csv",
        "min_rows": 148_136,
        "licence": "CC0 1.0 (public domain dedication)",
        "citation": (
            "City of Boulder Open Data, 'Electric Vehicle Charging Station Data', "
            "open-data.bouldercolorado.gov"
        ),
        "landing_url": "https://open-data.bouldercolorado.gov/",
        "run": "--dataset us-boulder-ev",
    },
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
            print(f"{key}\n  {entry['citation']}\n  licence: {entry['licence']}")
            print(f"  {entry.get('landing_url') or entry.get('url')}")
        return 0

    keys = list(REGISTRY) if args.all else [args.dataset]
    unknown = [key for key in keys if key not in REGISTRY]
    if unknown:
        print(f"ERROR: unknown dataset(s) {unknown}; known: {sorted(REGISTRY)}", file=sys.stderr)
        return 2

    raw_dir = sp1_settings(root=repo_root()).raw_dir
    for key in keys:
        entry = REGISTRY[key]
        directory = raw_dir / entry.get("dir", key)
        print(f"[{key}] {entry['citation']}")
        print(f"[{key}] licence: {entry['licence']} — {entry['landing_url']}")

        if entry.get("kind") == "arcgis":
            destination = directory / entry["filename"]
            download_arcgis_layer(entry["service"], destination, entry, force=args.force)
            print(f"[{key}] ready: {destination}")
        elif entry.get("kind") == "acn_api":
            destination = directory / entry["filename"]
            download_acn_sessions(destination, entry, force=args.force)
            print(f"[{key}] ready: {destination}")
        else:
            archive = directory / entry["filename"]
            _download(entry["url"], archive, entry, force=args.force)
            if entry.get("extract_to"):
                target = directory / entry["extract_to"]
                _unpack(archive, target)
                for nested in entry.get("nested_archives", []):
                    _unpack_nested(archive, nested, target)
                print(f"[{key}] ready under {target}")
            else:
                print(f"[{key}] ready: {archive}")

        print(f"[{key}] next: python subprojects/sp1-data-forecasting/scripts/run_sp1.py {entry['run']}")
    return 0


def download_acn_sessions(destination: Path, entry: dict, force: bool = False) -> int:
    """Download Caltech ACN-Data sessions with the official ``acnportal`` client.

    ACN-Data's REST API is credential-gated (an unauthenticated request returns
    HTTP 401), and the token comes from a free self-registration at
    ``https://ev.caltech.edu/register`` under a research/educational-use term.

    The token is read from the environment variable named in ``token_env`` — it is
    **never** written to disk, logged, or committed (see the repository's rules on
    credentials). Install the client with ``pip install acnportal``.

    Returns
    -------
    int
        Number of sessions written.
    """
    token = os.environ.get(entry.get("token_env", "ACN_API_TOKEN"), "").strip()
    if not token:
        raise SystemExit(
            "ERROR: no ACN-Data token found.\n"
            "  1. register (free) at https://ev.caltech.edu/register\n"
            "  2. set the token in the environment, e.g.\n"
            f"     PowerShell:  $env:{entry.get('token_env', 'ACN_API_TOKEN')}='<your token>'\n"
            f"     bash:        export {entry.get('token_env', 'ACN_API_TOKEN')}='<your token>'\n"
            "  3. re-run this command. The token is read from the environment and never stored."
        )
    try:
        from acnportal.acndata import DataClient
    except ImportError as error:
        raise SystemExit(
            "ERROR: the official ACN-Data client is not installed. Run:\n"
            "  pip install acnportal"
        ) from error

    if destination.exists() and not force:
        print(f"  already present: {destination.name} ({_row_count(destination):,} rows)")
        return _row_count(destination)

    client = DataClient(token)
    rows: list[dict] = []
    fieldnames: list[str] = []
    for site in entry["sites"]:
        print(f"  fetching site {site} ...")
        try:
            sessions = client.get_sessions(site, timeseries=False)
            for session in sessions:
                flat = {
                    key: json.dumps(value, ensure_ascii=False)
                    if isinstance(value, (list, dict))
                    else value
                    for key, value in session.items()
                }
                flat["site"] = site
                for key in flat:
                    if key not in fieldnames:
                        fieldnames.append(key)
                rows.append(flat)
        except Exception as error:
            raise SystemExit(
                f"ERROR: ACN-Data refused site '{site}': {type(error).__name__}: {error}\n"
                "  A 401 here means the token was rejected — re-issue it at "
                "https://ev.caltech.edu/login"
            ) from error

    if not rows:
        raise SystemExit("ERROR: ACN-Data returned no sessions; nothing written.")

    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"  wrote {len(rows):,} sessions -> {destination}")
    return len(rows)


def arcgis_metadata(service_url: str) -> dict:
    """Return the ArcGIS layer metadata (field list, ``maxRecordCount``)."""
    payload = _arcgis_request(f"{service_url}?f=json")
    if "error" in payload:
        raise SystemExit(f"ERROR: ArcGIS layer refused the request: {payload['error']}")
    return payload


def download_arcgis_layer(
    service_url: str, destination: Path, entry: dict, force: bool = False
) -> int:
    """Page through an ArcGIS FeatureServer layer and write it as CSV.

    ArcGIS caps every response at ``maxRecordCount`` rows, so the layer is pulled
    in pages ordered by ``ObjectID`` — without a stable order, paging silently
    duplicates and drops rows. The layer is a live service, so the check is a
    **row count** (``min_rows``) rather than a byte hash.

    Parameters
    ----------
    service_url : str
        e.g. ``https://services.arcgis.com/<org>/.../FeatureServer/0``.
    destination : pathlib.Path
        CSV to write.
    entry : dict
        Registry entry; ``min_rows`` is the count observed when the dataset was
        first validated.
    force : bool
        Re-download even if the file already looks complete.

    Returns
    -------
    int
        Number of rows written.
    """
    metadata = arcgis_metadata(service_url)
    fields = [field["name"] for field in metadata.get("fields", [])]
    page_size = min(ARCGIS_PAGE_SIZE, int(metadata.get("maxRecordCount", ARCGIS_PAGE_SIZE)))

    if destination.exists() and not force and _row_count(destination) >= entry.get("min_rows", 0):
        print(f"  already present with {_row_count(destination):,} rows: {destination.name}")
        return _row_count(destination)

    print(f"  paging {metadata.get('name')} ({len(fields)} fields, {page_size}/page)")
    destination.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    order_field = "ObjectID" if "ObjectID" in fields else fields[0]
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        offset = 0
        while True:
            payload = _arcgis_request(
                f"{service_url}/query",
                {
                    "where": "1=1",
                    "outFields": "*",
                    "returnGeometry": "false",
                    "orderByFields": order_field,
                    "resultOffset": offset,
                    "resultRecordCount": page_size,
                    "f": "json",
                },
            )
            if "error" in payload:
                raise SystemExit(f"ERROR: ArcGIS query failed at offset {offset}: {payload['error']}")
            features = payload.get("features", [])
            for feature in features:
                writer.writerow(feature.get("attributes", {}))
            total += len(features)
            print(f"    {total:,} rows", end="\r")
            if len(features) < page_size:
                break
            offset += page_size
    print(f"  wrote {total:,} rows -> {destination}")

    minimum = entry.get("min_rows")
    if minimum and total < minimum:
        raise SystemExit(
            f"ERROR: {destination} has {total:,} rows but {minimum:,} were expected. "
            "The upstream layer may have been truncated — check before trusting it."
        )
    return total


def _arcgis_request(url: str, params: dict | None = None, attempts: int = 5) -> dict:
    """GET an ArcGIS REST endpoint and return the decoded JSON, retrying resets.

    This network resets long downloads intermittently (see the workspace pitfall
    log: "Connection was reset" is usually transient — retry before suspecting
    configuration). A 149-page layer pull must survive that.
    """
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        request = urllib.request.Request(
            url, headers={"User-Agent": "ev-charging-platform/SP1 (academic use)"}
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.loads(response.read())
        except Exception as error:  # noqa: BLE001 - transport errors vary
            last_error = error
            if attempt == attempts:
                break
            print(f"    transient error ({type(error).__name__}), retry {attempt}/{attempts - 1}")
            time.sleep(2 * attempt)
    raise SystemExit(f"ERROR: ArcGIS request failed after {attempts} attempts: {last_error}")


def _row_count(path: Path) -> int:
    """Number of data rows in a CSV (header excluded)."""
    if not path.is_file():
        return 0
    with path.open(encoding="utf-8") as handle:
        return max(0, sum(1 for _ in handle) - 1)


def _download(url: str, destination: Path, entry: dict, force: bool) -> None:
    """Download ``url`` to ``destination`` and verify size and checksum."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not force:
        if _verify(destination, entry):
            print(f"  already present and verified: {destination.name}")
            return
        print(f"  {destination.name} failed verification; re-downloading")
    print(f"  downloading {url}")
    request = urllib.request.Request(
        url, headers={"User-Agent": "ev-charging-platform/SP1 (academic use)"}
    )
    with urllib.request.urlopen(request, timeout=300) as response, destination.open("wb") as handle:
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
