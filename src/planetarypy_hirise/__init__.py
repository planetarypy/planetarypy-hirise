"""HiRISE support for planetarypy, shipped as a separate distribution.

The public import path is unchanged from when this lived in core::

    from planetarypy.instruments.mro.hirise import get_browse

That works because ``planetarypy.instruments`` and ``planetarypy.instruments.mro``
are PEP 420 namespace packages: neither carries an ``__init__.py``, so core and
this package contribute modules to the same dotted path. Adding an ``__init__.py``
at either level in either distribution breaks that and must never be done.

Core keeps the declarative catalog knowledge for HiRISE (the index registry
entries and name maps), so a core-only install can still discover and fetch
``mro.hirise.{edr,rdr,dtm}``. What lives here is the behaviour.
"""

__version__ = "0.2.0"

from planetarypy_hirise.label import fetch_label, iof_affine, read_label

__all__ = ["__version__", "fetch_label", "iof_affine", "read_label"]
