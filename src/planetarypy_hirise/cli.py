"""``plp`` command-line surface for HiRISE.

``register(app)`` is the ``planetarypy.cli_plugins`` entry point: core calls it
for every ``plp`` invocation, which is what makes the verbs below appear.

The module-level ``hirise`` import is load-bearing and must not be made lazy.
Importing it runs the ``register_storage_resolver`` and ``register_meta_handler``
side effects, so ``plp meta mro.hirise.edr`` finds the HiRISE row formatter even
though that command never touches this module. Core dropped its hard-coded
fallback for exactly that lookup when HiRISE moved out.
"""

from __future__ import annotations

import click
import typer

from planetarypy.instruments.mro import hirise as hirise  # noqa: F401  (side effects)

_PANEL_FETCH = "Fetch & download"
_PANEL_VISUALIZE = "Visualize"


def _parse_ccds(specs) -> list[int] | None:
    """Flatten a ``--ccds`` spec into a list of CCD numbers (ints).

    Same dual-idiom shape as :func:`_parse_columns` — accepts repeated
    flags, comma-separated values inside one flag, and mixed forms:

    - ``--ccds 4 --ccds 5`` → ``[4, 5]``
    - ``--ccds "4,5"`` → ``[4, 5]``
    - ``--ccds 4 --ccds "5,6"`` → ``[4, 5, 6]``

    Returns ``None`` when no spec is given. Raises ``typer.BadParameter``
    on a value that isn't a positive int — CCD numbers are always
    small integers (HiRISE: 0..13).
    """
    if specs is None:
        return None
    if isinstance(specs, str):
        specs = [specs]
    nums: list[int] = []
    for spec in specs:
        if not spec:
            continue
        for n in spec.split(","):
            n = n.strip()
            if not n:
                continue
            try:
                nums.append(int(n))
            except ValueError:
                raise typer.BadParameter(
                    f"--ccds expects integers; got {n!r} in {spec!r}."
                )
    return nums or None


def _complete_hirise_obsid_rdr(incomplete: str) -> list[str]:
    """Tab-completion for HiRISE obsids with RDR products (browse, RDR fetch)."""
    from planetarypy.pds import complete_pid
    return complete_pid(incomplete, "mro.hirise.rdr")


def _complete_hirise_obsid_edr(incomplete: str) -> list[str]:
    """Tab-completion for HiRISE obsids from EDR index (all observations)."""
    from planetarypy.pds import complete_pid
    return complete_pid(incomplete, "mro.hirise.edr")


def register(app: typer.Typer) -> None:
    """Mount the HiRISE verbs onto the ``plp`` app."""
    @app.command(rich_help_panel=_PANEL_FETCH)
    def hibrowse(
        ctx: typer.Context,
        product_id: str = typer.Argument(
            None,
            help="HiRISE product ID, e.g. PSP_003092_0985_RED or PSP_004238_1135_RED1_1",
            autocompletion=_complete_hirise_obsid_rdr,
        ),
        annotated: bool = typer.Option(
            True, "--annotated/--clean", "-a/-c", help="Annotated (default) or clean browse"
        ),
        here: bool = typer.Option(False, "--here", "-H", help="Download into current directory"),
        force: bool = typer.Option(False, "--force", "-f", help="Re-download even if cached"),
    ):
        """Download a HiRISE browse JPEG from EXTRAS.

        Bare observation IDs default to RDR RED browse.

        Examples:
            plp hibrowse PSP_003092_0985_RED          (annotated browse)
            plp hibrowse --clean PSP_003092_0985_RED   (clean browse)
            plp hibrowse ESP_075422_2040_COLOR
            plp hibrowse PSP_004238_1135_RED1_1       (EDR CCD)
            plp hibrowse PSP_003092_0985              (defaults to RDR RED)
        """
        if product_id is None:
            typer.echo(ctx.get_help())
            raise typer.Exit()

        from pathlib import Path
        from planetarypy.instruments.mro.hirise import browse_url, get_browse

        # Show URL immediately so user knows we're waiting on the server
        typer.echo(f"Fetching {browse_url(product_id, annotated=annotated)}", err=True)

        try:
            dest = Path.cwd() if here else None
            outpath = get_browse(product_id, annotated=annotated, dest=dest, force=force)
            # Raw path on stdout so `qgis (plp hibrowse …)` and similar
            # shell substitutions capture just the path.
            typer.echo(outpath)
        except Exception as e:
            typer.echo(f"Error: {e}", err=True)
            raise typer.Exit(1)

        import platform
        if platform.system() == "Darwin":
            import subprocess
            subprocess.Popen(["open", str(outpath)])

    @app.command(rich_help_panel=_PANEL_FETCH)
    def hiedr(
        ctx: typer.Context,
        obsid: str = typer.Argument(None, help="HiRISE observation ID, e.g. PSP_003092_0985",
                                    autocompletion=_complete_hirise_obsid_edr),
        red: bool = typer.Option(False, "--red", help="Download RED CCDs (RED0–RED9, 20 files)"),
        ir: bool = typer.Option(False, "--ir", help="Download IR CCDs (IR10–IR11, 4 files)"),
        bg: bool = typer.Option(False, "--bg", help="Download BG CCDs (BG12–BG13, 4 files)"),
        ccds: list[str] = typer.Option(
            None, "--ccds",
            help="Specific CCD numbers. Repeatable AND comma-separated: "
                 "'--ccds 4 --ccds 5' is equivalent to '--ccds 4,5'.",
        ),
        here: bool = typer.Option(False, "--here", "-H", help="Download into current directory"),
        force: bool = typer.Option(False, "--force", "-f", help="Re-download even if cached"),
    ):
        """Download HiRISE EDR channel files by observation ID.

        Downloads both channels (0 and 1) for each CCD in the selected color.
        If no color flag is given, defaults to --red.

        Examples:
            plp hiedr PSP_003092_0985 --red           (all 20 RED files)
            plp hiedr PSP_003092_0985 --red --ccds 4,5 (RED4+RED5 only, 4 files)
            plp hiedr PSP_003092_0985 --ir             (IR10+IR11, 4 files)
            plp hiedr PSP_003092_0985 --bg             (BG12+BG13, 4 files)
            plp hiedr PSP_003092_0985 --here --ccds 4,5 (download to current dir)
        """
        if obsid is None:
            typer.echo(ctx.get_help())
            raise typer.Exit()

        from pathlib import Path
        from planetarypy.instruments.mro.hirise import download_edr, edr_products

        # Default to RED if nothing specified
        if not red and not ir and not bg:
            red = True

        colors = []
        if red:
            colors.append("red")
        if ir:
            colors.append("ir")
        if bg:
            colors.append("bg")

        ccd_nums = _parse_ccds(ccds)
        saveroot = Path.cwd() if here else None

        products = edr_products(obsid, colors=colors, ccds=ccd_nums, saveroot=saveroot)
        typer.echo(f"{obsid}: {len(products)} EDR files from {products[0].url.parent}")

        try:
            download_edr(obsid, colors=colors, ccds=ccd_nums, saveroot=saveroot, overwrite=force)
        except Exception as e:
            typer.echo(f"Error: {e}", err=True)
            raise typer.Exit(1)

        typer.echo(f"Stored in: {products[0].local_path.parent}")

    @app.command(rich_help_panel=_PANEL_FETCH)
    def himos(
        ctx: typer.Context,
        obsid: str = typer.Argument(
            None,
            help="HiRISE observation ID, e.g. PSP_003092_0985",
            autocompletion=_complete_hirise_obsid_edr,
        ),
        red: bool = typer.Option(False, "--red", help="Process RED CCDs"),
        ir: bool = typer.Option(False, "--ir", help="Process IR CCDs"),
        bg: bool = typer.Option(False, "--bg", help="Process BG CCDs"),
        ccds: list[str] = typer.Option(
            None, "--ccds",
            help="Specific CCD numbers. Repeatable AND comma-separated: "
                 "'--ccds 4 --ccds 5' is equivalent to '--ccds 4,5'.",
        ),
        mapfile: str = typer.Option(None, "--map", "-m", help="ISIS map projection file (.map)"),
        overwrite: bool = typer.Option(False, "--force", "-f", help="Reprocess even if mosaic exists"),
    ):
        """Create a HiRISE CCD mosaic from EDR data via ISIS.

        Full pipeline: download → hi2isis → spiceinit → hical → histitch →
        cubenorm → cam2map → equalizer → automos.

        If no color flag is given, defaults to --red.

        Examples:
            plp himos PSP_003092_0985                    (all 10 RED CCDs)
            plp himos PSP_003092_0985 --ccds 4,5         (RED4+RED5 central pair)
            plp himos PSP_003092_0985 --ir               (IR mosaic)
            plp himos PSP_003092_0985 --red --ir --bg    (all three colors)
            plp himos PSP_003092_0985 --map mymap.map    (custom projection)
        """
        if obsid is None:
            typer.echo(ctx.get_help())
            raise typer.Exit()

        from planetarypy.instruments.mro.hirise import create_mosaics

        if not red and not ir and not bg:
            red = True

        colors = []
        if red:
            colors.append("red")
        if ir:
            colors.append("ir")
        if bg:
            colors.append("bg")

        ccd_nums = _parse_ccds(ccds)

        try:
            results = create_mosaics(
                obsid, colors=colors, ccds=ccd_nums,
                mapfile=mapfile, overwrite=overwrite,
            )
        except Exception as e:
            typer.echo(f"Error: {e}", err=True)
            raise typer.Exit(1)

        for color, path in results.items():
            typer.echo(f"{color.upper()} mosaic: {path}")

    @app.command(rich_help_panel=_PANEL_FETCH)
    def hitif(
        ctx: typer.Context,
        jp2: str = typer.Argument(None, help="Projected HiRISE .JP2 file"),
        out: str = typer.Argument(None, help="Output .tif (default: input with .tif suffix)"),
        iau_code: int = typer.Option(
            None, "--iau-code",
            help="IAU_2015 projected code (default: matched to the source projection)",
        ),
        compress: str = typer.Option("deflate", "--compress", help="GeoTIFF compression"),
        blocksize: int = typer.Option(1024, "--blocksize", help="Tile size"),
        overviews: bool = typer.Option(
            True, "--overviews/--no-overviews",
            help="Build internal overviews, levels 2..256 (on by default)",
        ),
        nodata: float = typer.Option(
            0.0, "--nodata", help="Output NoData value (HiRISE reserves 0 for null)"
        ),
        no_nodata: bool = typer.Option(
            False, "--no-nodata", help="Leave NoData unset instead of tagging 0"
        ),
        threads: int = typer.Option(
            None, "--threads", help="Decode/warp threads (default: CPU count)"
        ),
        overwrite: bool = typer.Option(False, "--force", "-f", help="Overwrite existing output"),
        quiet: bool = typer.Option(
            False, "--quiet", "-q", help="Don't echo the rio / kdu_expand commands"
        ),
    ):
        """Convert a projected HiRISE JP2 to a GeoTIFF with an official IAU CRS.

        HiRISE polar RDRs carry an ISIS-style CRS on a sphere of Mars' polar
        radius, which no IAU_2015 code describes — so this reprojects rather than
        relabels. The transform is a pure uniform scale, so the output lands on an
        exactly 1:1 pixel grid and is bit-exact.

        Each rio / kdu_expand command is echoed to stderr before it runs, so the
        equivalent one-liner is there to copy. Uses Kakadu's kdu_expand for the
        JP2 decode when it's on PATH (~17x faster than OpenJPEG), else rio alone.

        An 8-level overview pyramid is built by default (--no-overviews to skip), and
        NoData is tagged as 0 (--no-nodata to skip) since HiRISE reserves 0 for null.

        Examples:
            plp hitif ESP_081720_2650_RED.JP2
            plp hitif ESP_081720_2650_RED.JP2 out.tif --no-overviews
            plp hitif in.JP2 --iau-code 49935          (force south polar)
            plp hitif in.JP2 --compress zstd --blocksize 512
        """
        if jp2 is None:
            typer.echo(ctx.get_help())
            raise typer.Exit()

        from planetarypy.instruments.mro.hirise import jp2_to_geotiff

        try:
            path = jp2_to_geotiff(
                jp2, out,
                iau_code=iau_code,
                compress=compress,
                blocksize=blocksize,
                overviews=overviews,
                nodata=None if no_nodata else nodata,
                threads=threads,
                overwrite=overwrite,
                echo=not quiet,
            )
        except Exception as e:
            typer.echo(f"Error: {e}", err=True)
            raise typer.Exit(1)

        typer.echo(str(path))

