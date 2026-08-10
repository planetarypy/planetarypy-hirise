"""Detached PDS3 label access for HiRISE RDR products.

The ``mro.hirise.rdr`` catalog resolves only the JP2 (the RDR cumulative index
lists no label in ``FILE_NAME_SPECIFICATION``), yet the radiometric calibration
lives exclusively in the detached ``.LBL``. Until the core resolver grows a
generic sibling-label heuristic, this module derives the label URL from the
resolved JP2 URL, caches the file beside the product, and parses it with
``pvl`` — no hand-rolled regexes (matching the bare word ``OFFSET`` famously
also matches ``LINE_PROJECTION_OFFSET``).
"""

from __future__ import annotations

import urllib.request
from pathlib import Path

import pvl

from planetarypy.catalog import default_product_dir, get_product_urls

__all__ = ["fetch_label", "read_label", "iof_affine"]

_KEY = "mro.hirise.rdr"


def _label_url(product_id: str, key: str = _KEY) -> str:
    """Derive the detached label URL from the product's primary file URL."""
    urls = get_product_urls(key, product_id)
    primary = next(iter(urls.values()))
    stem, dot, suffix = primary.rpartition(".")
    if not dot or suffix.upper() not in ("JP2", "IMG"):
        raise ValueError(f"cannot derive label URL from {primary!r}")
    return f"{stem}.LBL"


def fetch_label(product_id: str, key: str = _KEY, force: bool = False) -> Path:
    """Download (or reuse) the detached ``.LBL`` for ``product_id``.

    The file lands in the same per-product directory that ``fetch_product``
    uses, so label and image live together.
    """
    mission, instrument, ptype = key.split(".")
    dest_dir = default_product_dir(mission, instrument, ptype, product_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{product_id}.LBL"
    if force or not dest.exists():
        with urllib.request.urlopen(_label_url(product_id, key), timeout=60) as r:
            dest.write_bytes(r.read())
    return dest


def read_label(product_id: str, key: str = _KEY) -> pvl.PVLModule:
    """Fetch (if needed) and parse the product's detached PDS3 label."""
    return pvl.load(str(fetch_label(product_id, key)))


def _find_image_object(node):
    """Depth-first search for the (sub)object carrying the I/F calibration."""
    try:
        items = list(node.items())
    except AttributeError:
        return None
    keys = {k for k, _ in items}
    if "SCALING_FACTOR" in keys and "OFFSET" in keys:
        return node
    for _, v in items:
        found = _find_image_object(v)
        if found is not None:
            return found
    return None


def iof_affine(product_id: str, key: str = _KEY) -> tuple[float, float]:
    """Return ``(scale, offset)`` with ``I/F = scale * DN + offset``.

    Values come from the ``IMAGE`` object of the detached RDR label. A
    plausibility guard rejects accidental matches (e.g. projection offsets).
    """
    img = _find_image_object(read_label(product_id, key))
    if img is None:
        raise KeyError(f"no SCALING_FACTOR/OFFSET object in label of {product_id}")
    scale = float(img["SCALING_FACTOR"])
    offset = float(img["OFFSET"])
    if not (1e-7 < scale < 1e-3 and -0.1 < offset < 0.1):
        raise ValueError(f"implausible I/F affine for {product_id}: {scale}, {offset}")
    return scale, offset
