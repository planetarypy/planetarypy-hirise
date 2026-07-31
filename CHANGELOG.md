# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-07-31

Initial extraction from `planetarypy` core.

### Added

- **`planetarypy.instruments.mro.hirise`** — moved verbatim from core, import path preserved via PEP 420 namespace packages. Browse download, metadata shaping, EDR source products, `sun_azimuth_from_top`, `jp2_to_geotiff`, and the ISIS mosaic pipeline behind the `[isis]` extra.
- **Four `plp` verbs** — `hibrowse`, `hiedr`, `himos`, `hitif` — mounted through the `planetarypy.cli_plugins` entry point.
- Self-registration of the HiRISE storage resolver and meta-display handler on import, replacing core's hard-coded fallbacks.
