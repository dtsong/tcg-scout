"""Tests for scripts/publish_data_release.py against a fake HTTP layer.

The script is the only code that talks to the GitHub Release holding the
exported data tarballs and the SQLite backup. Nothing here touches the
network: ``FakeHttp`` scripts responses per (method, url) and records every
request so the tests can assert on ordering, payloads, and that the token
never leaks into a URL.
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
import tarfile
from dataclasses import dataclass, field
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import publish_data_release as pdr  # noqa: E402

REPO = "dtsong/tcg-scout"
TAG = "data"
API = f"https://api.github.com/repos/{REPO}/releases"
TOKEN = "ghs_fake_token_value"


def _asset(asset_id: int, name: str) -> dict:
    return {
        "id": asset_id,
        "name": name,
        "browser_download_url": f"https://github.com/{REPO}/releases/download/{TAG}/{name}",
        "url": f"https://api.github.com/repos/{REPO}/releases/assets/{asset_id}",
    }


def _release(assets: list[dict] | None = None) -> dict:
    return {
        "id": 77,
        "tag_name": TAG,
        "upload_url": f"https://uploads.github.com/repos/{REPO}/releases/77/assets{{?name,label}}",
        "assets": assets or [],
    }


def _targz(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, content in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
    return buf.getvalue()


@dataclass
class FakeHttp:
    """Scripted responses keyed by (method, url); unmatched requests raise."""

    scripts: dict[tuple[str, str], tuple[int, bytes]]
    calls: list[tuple[str, str, bytes | None, dict]] = field(default_factory=list)

    def request(
        self, method: str, url: str, data: bytes | None = None, headers: dict | None = None
    ) -> tuple[int, bytes]:
        self.calls.append((method, url, data, headers or {}))
        try:
            return self.scripts[(method, url)]
        except KeyError as exc:
            raise AssertionError(f"unexpected request {method} {url}") from exc

    def urls(self, method: str | None = None) -> list[str]:
        return [u for m, u, _, _ in self.calls if method is None or m == method]


def _json(payload: dict | list) -> tuple[int, bytes]:
    return 200, json.dumps(payload).encode()


class TestGitHubRelease:
    def test_ensure_creates_prerelease_when_tag_is_missing(self):
        http = FakeHttp(
            {
                ("GET", f"{API}/tags/{TAG}"): (404, b"{}"),
                ("POST", API): (201, json.dumps(_release()).encode()),
            }
        )
        release = pdr.GitHubRelease(REPO, TAG, TOKEN, http)

        info = release.ensure()

        assert info["id"] == 77
        method, url, body, headers = http.calls[-1]
        assert (method, url) == ("POST", API)
        payload = json.loads(body)
        assert payload["tag_name"] == TAG
        assert payload["prerelease"] is True
        assert headers["Authorization"] == f"Bearer {TOKEN}"

    def test_ensure_reuses_existing_release(self):
        http = FakeHttp({("GET", f"{API}/tags/{TAG}"): _json(_release())})
        release = pdr.GitHubRelease(REPO, TAG, TOKEN, http)

        assert release.ensure()["id"] == 77
        assert http.urls("POST") == []

    def test_upload_asset_posts_gzip_to_uploads_host(self, tmp_path: Path):
        blob = tmp_path / "x.tar.gz"
        blob.write_bytes(b"gzipbytes")
        upload_url = f"https://uploads.github.com/repos/{REPO}/releases/77/assets?name=x.tar.gz"
        http = FakeHttp(
            {
                ("GET", f"{API}/tags/{TAG}"): _json(_release()),
                ("POST", upload_url): (201, json.dumps(_asset(1, "x.tar.gz")).encode()),
            }
        )
        release = pdr.GitHubRelease(REPO, TAG, TOKEN, http)

        asset = release.upload_asset(blob, "x.tar.gz")

        assert asset["name"] == "x.tar.gz"
        _, _, body, headers = http.calls[-1]
        assert body == b"gzipbytes"
        assert headers["Content-Type"] == "application/gzip"

    def test_token_never_appears_in_any_url(self):
        http = FakeHttp({("GET", f"{API}/tags/{TAG}"): _json(_release())})
        pdr.GitHubRelease(REPO, TAG, TOKEN, http).ensure()

        assert all(TOKEN not in url for url in http.urls())


class TestPublish:
    @pytest.fixture()
    def workspace(self, tmp_path: Path) -> dict[str, Path]:
        export_dir = tmp_path / "web" / "public" / "data"
        (export_dir / "storm-emeralda").mkdir(parents=True)
        (export_dir / "formats.json").write_text("[]")
        (export_dir / "storm-emeralda" / "meta.json").write_text("{}")
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "storm-emeralda.db").write_bytes(b"sqlite")
        (data_dir / "storm-emeralda.db-wal").write_bytes(b"wal")
        return {
            "export": export_dir,
            "data": data_dir,
            "manifest": tmp_path / "web" / "data-manifest.json",
        }

    def test_publish_uploads_tarballs_prunes_old_assets_and_writes_manifest(
        self, workspace: dict[str, Path]
    ):
        old = [_asset(i, f"data-2026090{i}T000000Z.tar.gz") for i in range(1, 10)]
        old.append(_asset(50, "dbs.tar.gz"))
        uploads = "https://uploads.github.com/repos/dtsong/tcg-scout/releases/77/assets"
        new_name = "data-20260915T060000Z.tar.gz"
        http = FakeHttp(
            {
                ("GET", f"{API}/tags/{TAG}"): _json(_release(old)),
                ("POST", f"{uploads}?name={new_name}"): (
                    201,
                    json.dumps(_asset(99, new_name)).encode(),
                ),
                ("DELETE", f"{API}/assets/50"): (204, b""),
                ("POST", f"{uploads}?name=dbs.tar.gz"): (
                    201,
                    json.dumps(_asset(51, "dbs.tar.gz")).encode(),
                ),
                ("DELETE", f"{API}/assets/1"): (204, b""),
                ("DELETE", f"{API}/assets/2"): (204, b""),
            }
        )
        release = pdr.GitHubRelease(REPO, TAG, TOKEN, http)

        manifest = pdr.publish(
            release,
            export_dir=workspace["export"],
            data_dir=workspace["data"],
            manifest_path=workspace["manifest"],
            now="20260915T060000Z",
            keep=8,
        )

        archive = manifest["archives"][0]
        assert archive["url"] == f"https://github.com/{REPO}/releases/download/{TAG}/{new_name}"
        assert archive["created_at"] == "20260915T060000Z"
        uploaded_data = next(b for m, u, b, _ in http.calls if u.endswith(f"name={new_name}"))
        assert archive["sha256"] == hashlib.sha256(uploaded_data).hexdigest()
        with tarfile.open(fileobj=io.BytesIO(uploaded_data), mode="r:gz") as tar:
            assert "./storm-emeralda/meta.json" in tar.getnames()
        assert json.loads(workspace["manifest"].read_text()) == manifest

        # Newest 8 data tarballs survive (9 old + 1 new = 10, so the two oldest go).
        deleted = sorted(http.urls("DELETE"))
        assert deleted == sorted([f"{API}/assets/1", f"{API}/assets/2", f"{API}/assets/50"])
        uploaded_dbs = next(b for m, u, b, _ in http.calls if u.endswith("name=dbs.tar.gz"))
        with tarfile.open(fileobj=io.BytesIO(uploaded_dbs), mode="r:gz") as tar:
            assert tar.getnames() == ["storm-emeralda.db"], "WAL sidecars are not backed up"


class TestRestore:
    def _http(self, assets: list[dict], downloads: dict[str, bytes]) -> FakeHttp:
        scripts = {("GET", f"{API}/tags/{TAG}"): _json(_release(assets))}
        for url, body in downloads.items():
            scripts[("GET", url)] = (200, body)
        return FakeHttp(scripts)

    def test_noop_when_dbs_and_export_are_present(self, tmp_path: Path):
        data_dir, export_dir = tmp_path / "data", tmp_path / "export"
        data_dir.mkdir()
        export_dir.mkdir()
        (data_dir / "a.db").write_bytes(b"x")
        (export_dir / "formats.json").write_text("[]")
        http = self._http([], {})

        restored = pdr.restore(
            pdr.GitHubRelease(REPO, TAG, TOKEN, http),
            data_dir=data_dir,
            export_dir=export_dir,
            fallback_url="https://example.invalid/data-latest.tar.gz",
        )

        assert restored == []
        assert http.calls == []

    def test_downloads_dbs_backup_and_newest_data_tarball(self, tmp_path: Path):
        data_dir, export_dir = tmp_path / "data", tmp_path / "export"
        dbs = _asset(1, "dbs.tar.gz")
        older = _asset(2, "data-20260901T000000Z.tar.gz")
        newer = _asset(3, "data-20260914T000000Z.tar.gz")
        http = self._http(
            [dbs, older, newer],
            {
                dbs["browser_download_url"]: _targz({"a.db": b"sqlite"}),
                newer["browser_download_url"]: _targz({"./formats.json": b"[]"}),
            },
        )

        restored = pdr.restore(
            pdr.GitHubRelease(REPO, TAG, TOKEN, http),
            data_dir=data_dir,
            export_dir=export_dir,
            fallback_url="https://example.invalid/data-latest.tar.gz",
        )

        assert restored == ["dbs.tar.gz", newer["name"]]
        assert (data_dir / "a.db").read_bytes() == b"sqlite"
        assert (export_dir / "formats.json").read_text() == "[]"
        assert older["browser_download_url"] not in http.urls()

    def test_falls_back_to_public_url_when_release_has_no_data_asset(self, tmp_path: Path):
        data_dir, export_dir = tmp_path / "data", tmp_path / "export"
        data_dir.mkdir()
        (data_dir / "a.db").write_bytes(b"x")
        fallback = "https://storage.googleapis.com/tcg-scout-data/data-latest.tar.gz"
        http = self._http([], {fallback: _targz({"./formats.json": b"[]"})})

        restored = pdr.restore(
            pdr.GitHubRelease(REPO, TAG, TOKEN, http),
            data_dir=data_dir,
            export_dir=export_dir,
            fallback_url=fallback,
        )

        assert restored == [fallback]
        assert (export_dir / "formats.json").exists()

    def test_missing_dbs_backup_is_not_an_error(self, tmp_path: Path):
        data_dir, export_dir = tmp_path / "data", tmp_path / "export"
        export_dir.mkdir()
        (export_dir / "formats.json").write_text("[]")
        http = self._http([], {})

        restored = pdr.restore(
            pdr.GitHubRelease(REPO, TAG, TOKEN, http),
            data_dir=data_dir,
            export_dir=export_dir,
            fallback_url="https://example.invalid/x",
        )

        assert restored == []
        assert data_dir.is_dir()


class TestCli:
    def test_main_requires_token(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        with pytest.raises(SystemExit, match="GITHUB_TOKEN"):
            pdr.main(["publish"])

    def test_main_rejects_unknown_command(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("GITHUB_TOKEN", TOKEN)
        with pytest.raises(SystemExit):
            pdr.main(["frobnicate"])
