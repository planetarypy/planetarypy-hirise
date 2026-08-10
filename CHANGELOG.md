# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-08-10

### Added

- **`label` module** — `fetch_label`, `read_label`, `iof_affine`: detached PDS3 `.LBL` access for RDR products with pvl parsing. `iof_affine(product_id)` returns the `(scale, offset)` of `I/F = scale * DN + offset` with a plausibility guard. Works around the catalog resolver not (yet) declaring label companions for `mro.hirise.rdr`.
- **`missing_ccds(requested, obtained)`** — the CCD names an observation's archive entry does not carry, in detector order.

### Fixed

- **A CCD the archive never carried is no longer a failed download.** An observation ships all 14 CCDs, but occasionally one never reached the archive; the PDS answers 404 and `plp hiedr` now says so — naming the absent CCDs and how many of the requested ones are available — instead of exiting 1 and discarding the files that did arrive. Genuine failures (any other status, network errors) still raise, and an obsid with nothing in the archive raises `FileNotFoundError`.

### Changed

- `download_edr` returns the products actually on disk rather than the ones requested, so callers can diff the two.
- `create_mosaic` reduces the CCDs that exist instead of failing on the gap, and labels the output for that set — e.g. `ESP_046769_0950_RED012345678.mos.cub` for an observation missing RED9, so a partial mosaic can never be mistaken for a full one. With `download=False` the same narrowing is driven by which EDRs are present locally.

## [0.1.0] - 2026-07-31

Initial extraction from `planetarypy` core.

### Added

- **`planetarypy.instruments.mro.hirise`** — moved verbatim from core, import path preserved via PEP 420 namespace packages. Browse download, metadata shaping, EDR source products, `sun_azimuth_from_top`, `jp2_to_geotiff`, and the ISIS mosaic pipeline behind the `[isis]` extra.
- **Four `plp` verbs** — `hibrowse`, `hiedr`, `himos`, `hitif` — mounted through the `planetarypy.cli_plugins` entry point.
- Self-registration of the HiRISE storage resolver and meta-display handler on import, replacing core's hard-coded fallbacks.
- A `CONTRIBUTES` manifest declaring the four verbs, the `mro.hirise` storage resolver and the `mro.hirise.edr` meta handler, which core verifies once the plugin is loaded and reports on stderr if anything is missing. Its `panel` also groups these verbs under a `HiRISE ·` section in `plp --help`.
