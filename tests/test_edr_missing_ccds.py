"""A CCD the archive never carried is not a download failure.

A HiRISE observation ships all 14 CCDs — RED0-9, IR10-11, BG12-13 — so a gap is
the exception, but it happens and the PDS answers 404. These tests pin the split
between "not in the archive" and "the download broke".
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from planetarypy.instruments.mro.hirise import (
    SOURCE_PRODUCT,
    _download_with_rich_task,
    create_mosaic,
    download_edr,
    edr_products,
    missing_ccds,
)
from planetarypy_hirise.cli import register

OBSID = "ESP_046769_0950"
_HIRISE = "planetarypy.instruments.mro.hirise"
_DOWNLOAD = f"{_HIRISE}.download_edr"


class FakeResponse:
    def __init__(self, status_code, payload=b""):
        self.status_code = status_code
        self.headers = {"content-length": str(len(payload))}
        self._payload = payload

    def iter_content(self, chunk_size=None):
        yield self._payload


class FakeSession:
    """Serves every product except the CCDs named in `absent`."""

    def __init__(self, absent=("RED9",), status=404, payload=b"IMGDATA"):
        self.absent = absent
        self.status = status
        self.payload = payload

    def get(self, url, **kwargs):
        if any(f"_{ccd}_" in url for ccd in self.absent):
            return FakeResponse(self.status)
        return FakeResponse(200, self.payload)

    def mount(self, prefix, adapter):
        pass

    def close(self):
        pass


class NullProgress:
    def update(self, *args, **kwargs):
        pass

    def advance(self, *args, **kwargs):
        pass


@pytest.fixture
def fake_session(monkeypatch):
    """Install a session factory; the test picks what the archive is missing."""

    def install(**kwargs):
        monkeypatch.setattr("requests.Session", lambda: FakeSession(**kwargs))

    return install


class TestMissingCcds:
    def test_absent_ccd_is_reported(self):
        requested = edr_products(OBSID)
        obtained = [p for p in requested if p.ccd != "RED9"]
        assert missing_ccds(requested, obtained) == ["RED9"]

    def test_both_channels_collapse_to_one_name(self):
        requested = edr_products(OBSID)
        obtained = [p for p in requested if p.spid != f"{OBSID}_RED9_0"]
        assert missing_ccds(requested, obtained) == ["RED9"]

    def test_empty_when_everything_arrived(self):
        requested = edr_products(OBSID)
        assert missing_ccds(requested, requested) == []

    def test_detector_order_not_alphabetical(self):
        requested = edr_products(OBSID, colors=["red", "ir", "bg"])
        obtained = [p for p in requested if p.ccd not in ("RED9", "IR10", "BG12")]
        assert missing_ccds(requested, obtained) == ["RED9", "IR10", "BG12"]


class TestDownloadClassification:
    def _run(self, status, tmp_path):
        prod = SOURCE_PRODUCT(f"{OBSID}_RED9_0", saveroot=tmp_path)
        prod.local_path.parent.mkdir(parents=True, exist_ok=True)
        session = FakeSession(absent=("RED9",), status=status)
        return _download_with_rich_task(prod, 0, NullProgress(), False, session)

    def test_404_is_missing(self, tmp_path):
        _, status, error = self._run(404, tmp_path)
        assert status == "missing"
        assert error is None

    def test_410_is_missing(self, tmp_path):
        _, status, error = self._run(410, tmp_path)
        assert status == "missing"

    def test_500_is_a_failure(self, tmp_path):
        _, status, error = self._run(500, tmp_path)
        assert status == "failed"
        assert "500" in error

    def test_403_is_a_failure(self, tmp_path):
        _, status, _ = self._run(403, tmp_path)
        assert status == "failed"

    def test_network_exception_is_a_failure(self, tmp_path):
        prod = SOURCE_PRODUCT(f"{OBSID}_RED0_0", saveroot=tmp_path)
        prod.local_path.parent.mkdir(parents=True, exist_ok=True)

        class Boom:
            def get(self, *args, **kwargs):
                raise OSError("connection reset")

        _, status, error = _download_with_rich_task(prod, 0, NullProgress(), False, Boom())
        assert status == "failed"
        assert "connection reset" in error

    def test_missing_product_leaves_no_partial_file(self, tmp_path):
        prod = SOURCE_PRODUCT(f"{OBSID}_RED9_0", saveroot=tmp_path)
        prod.local_path.parent.mkdir(parents=True, exist_ok=True)
        self._run(404, tmp_path)
        assert list(prod.local_path.parent.glob("*.part")) == []
        assert not prod.local_path.exists()


class TestDownloadEdr:
    def test_partial_archive_does_not_raise(self, tmp_path, fake_session):
        fake_session(absent=("RED9",))
        obtained = download_edr(OBSID, saveroot=tmp_path)
        assert len(obtained) == 18

    def test_partial_archive_omits_missing_products(self, tmp_path, fake_session):
        fake_session(absent=("RED9",))
        obtained = download_edr(OBSID, saveroot=tmp_path)
        assert missing_ccds(edr_products(OBSID, saveroot=tmp_path), obtained) == ["RED9"]

    def test_returned_products_are_on_disk(self, tmp_path, fake_session):
        fake_session(absent=("RED9",))
        obtained = download_edr(OBSID, saveroot=tmp_path)
        assert all(p.local_path.exists() for p in obtained)

    def test_genuine_failure_still_raises(self, tmp_path, fake_session):
        fake_session(absent=("RED9",), status=500)
        with pytest.raises(RuntimeError, match="downloads failed"):
            download_edr(OBSID, saveroot=tmp_path)

    def test_nothing_archived_raises_file_not_found(self, tmp_path, fake_session):
        fake_session(absent=SOURCE_PRODUCT.ccds)
        with pytest.raises(FileNotFoundError, match="check the observation ID"):
            download_edr(OBSID, saveroot=tmp_path)


class TestMosaicSkipsAbsentCcds:
    """The reduction runs on what the archive has, under an honest label."""

    def _mosaic_dir(self, tmp_path):
        return edr_products(OBSID, saveroot=tmp_path)[0].local_path.parent

    def _create(self, tmp_path, absent=("RED9",), **kwargs):
        obtained = [p for p in edr_products(OBSID, saveroot=tmp_path)
                    if p.ccd not in absent]
        with patch(f"{_HIRISE}._require_isis"), \
                patch(_DOWNLOAD, return_value=obtained):
            return create_mosaic(OBSID, saveroot=tmp_path, **kwargs)

    def test_label_lists_the_ccds_that_went_in(self, tmp_path):
        out_dir = self._mosaic_dir(tmp_path)
        out_dir.mkdir(parents=True, exist_ok=True)
        partial = out_dir / f"{OBSID}_RED012345678.mos.cub"
        partial.touch()
        assert self._create(tmp_path) == partial

    def test_complete_observation_keeps_the_plain_color_label(self, tmp_path):
        out_dir = self._mosaic_dir(tmp_path)
        out_dir.mkdir(parents=True, exist_ok=True)
        full = out_dir / f"{OBSID}_RED.mos.cub"
        full.touch()
        assert self._create(tmp_path, absent=()) == full

    def test_label_handles_a_gap_in_the_middle(self, tmp_path):
        out_dir = self._mosaic_dir(tmp_path)
        out_dir.mkdir(parents=True, exist_ok=True)
        partial = out_dir / f"{OBSID}_RED01245678.mos.cub"
        partial.touch()
        assert self._create(tmp_path, absent=("RED3", "RED9")) == partial

    def test_no_local_files_without_download_is_an_error(self, tmp_path):
        with patch(f"{_HIRISE}._require_isis"):
            with pytest.raises(FileNotFoundError, match="download=True"):
                create_mosaic(OBSID, saveroot=tmp_path, download=False)


app = typer.Typer()
register(app)
runner = CliRunner()


class TestHiedrCli:
    def _invoke(self, tmp_path, absent=("RED9",)):
        obtained = [p for p in edr_products(OBSID, saveroot=tmp_path)
                    if p.ccd not in absent]
        with patch(_DOWNLOAD, return_value=obtained):
            return runner.invoke(app, ["hiedr", OBSID, "--here"])

    def test_exit_code_is_zero(self, tmp_path):
        assert self._invoke(tmp_path).exit_code == 0

    def test_names_the_absent_ccd(self, tmp_path):
        assert "RED9" in self._invoke(tmp_path).output

    def test_reports_the_available_count(self, tmp_path):
        assert "9 of 10 requested CCDs" in self._invoke(tmp_path).output

    def test_does_not_call_it_an_error(self, tmp_path):
        assert "Error:" not in self._invoke(tmp_path).output

    def test_still_reports_where_files_landed(self, tmp_path):
        assert "Stored in:" in self._invoke(tmp_path).output

    def test_complete_observation_says_nothing_extra(self, tmp_path):
        result = self._invoke(tmp_path, absent=())
        assert result.exit_code == 0
        assert "requested CCDs" not in result.output

    def test_hard_failure_still_exits_nonzero(self, tmp_path):
        with patch(_DOWNLOAD, side_effect=RuntimeError("2/20 downloads failed")):
            result = runner.invoke(app, ["hiedr", OBSID, "--here"])
        assert result.exit_code == 1
        assert "Error:" in result.output
