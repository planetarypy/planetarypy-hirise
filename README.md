# planetarypy-hirise

MRO HiRISE support for [planetarypy](https://github.com/planetarypy/planetarypy).

```bash
pip install planetarypy-hirise          # pure-Python half
pip install planetarypy-hirise[isis]    # + the ISIS mosaic pipeline
```

or, equivalently, from core's extra:

```bash
pip install planetarypy[hirise]
```

## The import path is unchanged

Code written against core's in-tree HiRISE module keeps working verbatim:

```python
from planetarypy.instruments.mro.hirise import get_browse, get_metadata
```

`planetarypy.instruments` and `planetarypy.instruments.mro` are PEP 420 namespace
packages — neither carries an `__init__.py` — so core and this package contribute
modules to the same dotted path. **Never add an `__init__.py` at either level**, in
either distribution; it converts them back to regular packages and the split breaks.

## What is here, and what stayed in core

Core keeps the *declarative* catalog knowledge: the index registry entries for
`mro.hirise.{edr,rdr,dtm}` and the mission/instrument name maps. A core-only
install can therefore still run `plp indexes peek mro.hirise.edr`,
`plp fetch mro.hirise.edr`, and find HiRISE in the catalog **without this package**.

This package adds the behaviour:

| | |
|---|---|
| browse images | `browse_url`, `get_browse` |
| metadata | `get_metadata`, `format_meta`, `sun_azimuth_from_top` |
| EDR products | `SOURCE_PRODUCT`, `RED_PRODUCT`, `edr_products`, `download_edr` |
| GeoTIFF conversion | `jp2_to_geotiff` |
| ISIS pipeline (`[isis]`) | `ingest_edr`, `calibrate_channel`, `stitch_channels`, `map_project`, `create_mosaic`, `create_mosaics`, `create_red_mosaic` |

## CLI

Installing this package adds four verbs to `plp`, via the
`planetarypy.cli_plugins` entry point:

```
plp hibrowse OBSID      download a browse JPEG from EXTRAS
plp hiedr    OBSID      download EDR channel products
plp himos    OBSID      build a CCD mosaic via ISIS
plp hitif    FILE.JP2   convert a projected JP2 to GeoTIFF in an official IAU CRS
```

## How the plugin registers

`planetarypy_hirise.cli:register` is the entry point core calls on every `plp`
invocation. It imports `planetarypy.instruments.mro.hirise` **at module load**,
which is load-bearing rather than incidental: that import runs
`register_storage_resolver` and `register_meta_handler`, so `plp meta
mro.hirise.edr` finds the HiRISE row formatter. Core removed its hard-coded
fallback for that lookup when HiRISE moved out, so making the import lazy would
silently regress `plp meta` to a generic two-column dump.

## License

BSD-3.
