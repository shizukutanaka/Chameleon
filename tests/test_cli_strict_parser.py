"""The CLI must refuse long-option abbreviations, not silently rebind them.

argparse's default `allow_abbrev` treats any unambiguous prefix as the flag
itself. Verified on 2026-09-22: `chameleon process in.wav --normalize --output
out.wav` parsed `--output` as `--output-dir`, so the CLI created a directory
literally named `out.wav` containing `in_normalized.wav` -- while `midi
--output` in the same CLI is an output *file*. `stream --output 5` silently
became `--output-device 5`. A mistyped flag must exit 2, not bind to a
different one.
"""

import pytest


def _parse(parser, argv):
    import contextlib
    import io
    with contextlib.redirect_stderr(io.StringIO()):
        return parser.parse_args(argv)


def test_process_output_abbreviation_refused():
    import main
    parser = main.create_cli()
    with pytest.raises(SystemExit):
        _parse(parser, ["process", "in.wav", "--normalize",
                        "--output", "out.wav"])


def test_stream_output_abbreviation_refused():
    import main
    parser = main.create_cli()
    with pytest.raises(SystemExit):
        _parse(parser, ["stream", "--output", "5"])


def test_batch_output_abbreviation_refused():
    import main
    parser = main.create_cli()
    with pytest.raises(SystemExit):
        _parse(parser, ["batch", "indir", "analyze",
                        "--output", "outdir"])


def test_nested_plugin_subparser_abbreviation_refused():
    import main
    parser = main.create_cli()
    with pytest.raises(SystemExit):
        _parse(parser, ["plugins", "audit", "--direct", "/x"])


def test_explicit_flags_still_parse():
    import main
    parser = main.create_cli()

    ns = _parse(parser, ["process", "in.wav", "--normalize",
                         "--output-dir", "outdir"])
    assert ns.output_dir == "outdir"

    # midi --output is a file argument in this CLI -- it must keep working.
    ns = _parse(parser, ["midi", "compose", "--key", "C",
                         "--output", "x.mid"])
    assert ns.output == "x.mid"

    ns = _parse(parser, ["stream", "--output-device", "5"])
    assert ns.output_device == 5

    ns = _parse(parser, ["plugins", "audit", "--directory", "/x"])
    assert ns.plugins_sub_directory == ["/x"]
