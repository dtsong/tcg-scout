"""Publish exported data and SQLite backups to a rolling GitHub Release.

The Harness scrape pipeline keeps ``data/*.db`` and ``web/public/data/`` in
Harness cache between runs, but that cache expires after 15 days and can be
evicted. This script makes a GitHub Release (tag ``data``, prerelease so it
never becomes the repo's "Latest") the durable copy and the public download
that Vercel's ``web/scripts/prebuild.mjs`` fetches.

Commands (token read from ``GITHUB_TOKEN``, never printed):

    restore     Fill ``data/`` from ``dbs.tar.gz`` and ``web/public/data/`` from the
                newest ``data-*.tar.gz`` when either is empty. Falls back to the
                public ``data-latest.tar.gz`` on GCS while the release is new.
    publish     Tar ``web/public/data``, upload it and ``dbs.tar.gz``, prune old
                data tarballs, and write ``web/data-manifest.json``.
    upload-dbs  Upload ``dbs.tar.gz`` only (one-time seeding from a laptop).

Stdlib only: it runs on a bare Harness runner before ``uv sync``.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPO = "dtsong/tcg-scout"
DEFAULT_TAG = "data"
DATA_ASSET_PREFIX = "data-"
DBS_ASSET = "dbs.tar.gz"
DEFAULT_KEEP = 8
FALLBACK_DATA_URL = "https://storage.googleapis.com/tcg-scout-data/data-latest.tar.gz"
API_VERSION = "2022-11-28"


class Http(Protocol):
    def request(
        self, method: str, url: str, data: bytes | None = None, headers: dict | None = None
    ) -> tuple[int, bytes]: ...


class UrllibHttp:
    """Thin urllib wrapper: returns (status, body) and never raises on 4xx/5xx."""

    def request(
        self, method: str, url: str, data: bytes | None = None, headers: dict | None = None
    ) -> tuple[int, bytes]:
        req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()


class ReleaseError(RuntimeError):
    pass


class GitHubRelease:
    """A single release identified by tag, with its assets."""

    def __init__(self, repo: str, tag: str, token: str, http: Http | None = None) -> None:
        self.repo = repo
        self.tag = tag
        self._token = token
        self._http = http or UrllibHttp()
        self._api = f"https://api.github.com/repos/{repo}/releases"
        self._info: dict | None = None

    def _headers(self, **extra: str) -> dict:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": API_VERSION,
            **extra,
        }

    def _call(self, method: str, url: str, data: bytes | None = None, **headers: str) -> dict:
        status, body = self._http.request(method, url, data, self._headers(**headers))
        if status >= 300:
            raise ReleaseError(f"{method} {url} returned HTTP {status}")
        return json.loads(body) if body else {}

    def ensure(self) -> dict:
        """Return the release, creating it as a prerelease when the tag is missing."""
        if self._info is not None:
            return self._info
        status, body = self._http.request(
            "GET", f"{self._api}/tags/{self.tag}", None, self._headers()
        )
        if status == 200:
            self._info = json.loads(body)
        elif status == 404:
            payload = {
                "tag_name": self.tag,
                "name": "Scout data (rolling)",
                "body": "Exported JSON tarballs and SQLite backups written by the Harness scrape pipeline.",
                "prerelease": True,
            }
            self._info = self._call(
                "POST",
                self._api,
                json.dumps(payload).encode(),
                **{"Content-Type": "application/json"},
            )
        else:
            raise ReleaseError(f"GET release {self.tag} returned HTTP {status}")
        return self._info

    def assets(self) -> list[dict]:
        return list(self.ensure().get("assets", []))

    def upload_asset(self, path: Path, name: str) -> dict:
        upload_url = self.ensure()["upload_url"].split("{", 1)[0]
        asset = self._call(
            "POST",
            f"{upload_url}?name={name}",
            path.read_bytes(),
            **{"Content-Type": "application/gzip"},
        )
        self.ensure()["assets"] = [a for a in self.assets() if a["name"] != name] + [asset]
        return asset

    def delete_asset(self, asset_id: int) -> None:
        self._call("DELETE", f"{self._api}/assets/{asset_id}")
        self.ensure()["assets"] = [a for a in self.assets() if a["id"] != asset_id]

    def download_asset(self, name: str, dest: Path) -> bool:
        """Download a public asset by name; False when the release has no such asset."""
        match = next((a for a in self.assets() if a["name"] == name), None)
        if match is None:
            return False
        download(self._http, match["browser_download_url"], dest)
        return True


def download(http: Http, url: str, dest: Path) -> None:
    status, body = http.request("GET", url, None, {"Accept": "application/octet-stream"})
    if status != 200:
        raise ReleaseError(f"GET {url} returned HTTP {status}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(body)


def _extract(archive: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, mode="r:gz") as tar:
        tar.extractall(dest, filter="data")


def _tar_directory(src: Path, dest: Path) -> None:
    """Equivalent of ``tar -czf dest --exclude='._*' -C src .``"""
    with tarfile.open(dest, mode="w:gz") as tar:
        tar.add(
            src, arcname=".", filter=lambda ti: None if Path(ti.name).name.startswith("._") else ti
        )


def _tar_files(paths: Iterable[Path], dest: Path) -> None:
    with tarfile.open(dest, mode="w:gz") as tar:
        for path in sorted(paths):
            tar.add(path, arcname=path.name)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def data_assets(release: GitHubRelease) -> list[dict]:
    """Data tarballs, oldest first (timestamped names sort chronologically)."""
    return sorted(
        (a for a in release.assets() if a["name"].startswith(DATA_ASSET_PREFIX)),
        key=lambda a: a["name"],
    )


def upload_dbs(release: GitHubRelease, data_dir: Path) -> dict:
    """Back up ``*.db`` (not WAL/SHM sidecars) as ``dbs.tar.gz``, replacing any previous copy."""
    dbs = sorted(data_dir.glob("*.db"))
    if not dbs:
        raise ReleaseError(f"no .db files in {data_dir}")
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / DBS_ASSET
        _tar_files(dbs, archive)
        for stale in (a for a in release.assets() if a["name"] == DBS_ASSET):
            release.delete_asset(stale["id"])
        return release.upload_asset(archive, DBS_ASSET)


def publish(
    release: GitHubRelease,
    export_dir: Path,
    data_dir: Path,
    manifest_path: Path,
    now: str | None = None,
    keep: int = DEFAULT_KEEP,
) -> dict:
    """Upload the export tarball and DB backup, prune, and write the manifest."""
    stamp = now or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")  # noqa: UP017 (runner python may be 3.10)
    name = f"{DATA_ASSET_PREFIX}{stamp}.tar.gz"
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / name
        _tar_directory(export_dir, archive)
        sha = _sha256(archive)
        asset = release.upload_asset(archive, name)
    upload_dbs(release, data_dir)
    for stale in data_assets(release)[:-keep] if keep > 0 else []:
        release.delete_asset(stale["id"])
    manifest = {
        "version": 1,
        "archives": [{"url": asset["browser_download_url"], "sha256": sha, "created_at": stamp}],
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def restore(
    release: GitHubRelease,
    data_dir: Path,
    export_dir: Path,
    fallback_url: str = FALLBACK_DATA_URL,
) -> list[str]:
    """Fill empty working dirs from the release; returns the sources used."""
    restored: list[str] = []
    data_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        if not any(data_dir.glob("*.db")):
            archive = Path(tmp) / DBS_ASSET
            if release.download_asset(DBS_ASSET, archive):
                _extract(archive, data_dir)
                restored.append(DBS_ASSET)
        if not (export_dir / "formats.json").exists():
            archive = Path(tmp) / "export.tar.gz"
            newest = data_assets(release)[-1:]
            if newest:
                download(release._http, newest[0]["browser_download_url"], archive)
                restored.append(newest[0]["name"])
            else:
                download(release._http, fallback_url, archive)
                restored.append(fallback_url)
            _extract(archive, export_dir)
    return restored


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1 or args[0] not in {"restore", "publish", "upload-dbs"}:
        raise SystemExit(f"usage: {Path(__file__).name} restore|publish|upload-dbs")
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        raise SystemExit("GITHUB_TOKEN is not set")
    release = GitHubRelease(
        os.environ.get("GITHUB_REPO", DEFAULT_REPO),
        os.environ.get("DATA_RELEASE_TAG", DEFAULT_TAG),
        token,
    )
    data_dir = ROOT / "data"
    export_dir = ROOT / "web" / "public" / "data"
    if args[0] == "restore":
        used = restore(release, data_dir, export_dir)
        print("restored from: " + (", ".join(used) if used else "nothing (cache was warm)"))
    elif args[0] == "publish":
        manifest = publish(release, export_dir, data_dir, ROOT / "web" / "data-manifest.json")
        print(f"published {manifest['archives'][0]['url']}")
    else:
        asset = upload_dbs(release, data_dir)
        print(f"uploaded {asset['name']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
