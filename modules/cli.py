import os
import re
import sys
from argparse import ArgumentTypeError, ArgumentParser, RawTextHelpFormatter, \
    ONE_OR_MORE
from enum import Enum
from pathlib import Path
from typing import Union, List, Pattern, Optional

from modules.constants import COUNTRY_REGION_CORRELATION, GITHUB_URL, \
    __version__

_FILE_PREFIX = "file:"

# TODO: we should handle CHDs
class OutputMode(Enum):
    PREVIEW = \
        ("Preview the list of selected ROMs",)
    COPY_RENAME = \
        ("Copy the files without restructuring or (un)compression",)
    UNCOMPRESSED = \
        ("Copy the files, uncompressing if needed",
         "Games with a single ROM are put in the root of the output directory",
         "Games with multiple ROMs have them grouped in subdirectories")
    UNCOMPRESSED_CLRMAMEPRO = \
        ("Same as above, but following ClrMamePro's folder structure",
         "ROMs are always in subdirectories, regardless of how many they are",
         "Reference: https://mamedev.emulab.it/clrmamepro/docs/htm/scanner.htm")
    COMPRESSED_ZIP = \
        ("Copy the files, compressing them to 'zip' if not already compressed",)
    RECOMPRESSED_ZIP = \
        ("Copy the files, always (re)compressing them to 'zip'",)
    COMPRESSED_7Z = \
        ("Copy the files, compressing them to '7z' if not already compressed",)
    RECOMPRESSED_7Z = \
        ("Copy the files, always (re)compressing them to '7z'",)
    CUSTOM_DAT = \
        ("Produces a custom DAT with the ROM selection",
         "If no output directory is given, the DAT is printed to the terminal",
         "Otherwise, it is written to '<out_dir>%s<dat>_custom_<date>%sdat'"
         % (os.path.sep, os.path.extsep))


def _make_dir(p):
    try:
        p.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass


def _file_path_input(arg: str) -> Path:
    p = Path(arg.strip()).expanduser()
    if p.is_file():
        return p
    raise ArgumentTypeError(f"'{arg}' is not a valid input file")


def _file_path_output(arg: str) -> Path:
    p = Path(arg.strip()).expanduser()
    if p.parent != p:
        _make_dir(p.parent)
    if (p.parent == p or p.parent.is_dir()) and (not p.exists() or p.is_file()):
        return p
    raise ArgumentTypeError(f"'{arg}' is not a valid output file")


def _dir_path_output(arg: str) -> Path:
    p = Path(arg.strip()).expanduser()
    _make_dir(p)
    if p.is_dir():
        return p
    raise ArgumentTypeError(f"'{arg}' is not a valid output directory")


def _dir_path_input(arg: str) -> Path:
    p = Path(arg.strip()).expanduser()
    if p.is_dir():
        return p
    raise ArgumentTypeError(f"'{arg}' is not a valid input directory")


def _mode(arg: str) -> OutputMode:
    code = arg.strip()
    try:
        index = int(code)
        return [o for o in OutputMode][index - 1]
    except (ValueError, IndexError):
        try:
            return OutputMode[code]
        except KeyError:
            raise ArgumentTypeError(f"'{arg}' is not a valid output mode")


def _region(arg: str) -> str:
    code = arg.strip().upper()
    if len(code) != 3:
        raise ArgumentTypeError(f"'{arg}' is not a valid region")
    for c in COUNTRY_REGION_CORRELATION:
        if c.code == code:
            return code
    print(
        f"WARNING: '{arg}' is likely not a recognized region",
        file=sys.stderr)
    return code


def _lang(arg: str) -> str:
    code = arg.strip().lower()
    if len(code) != 2:
        raise ArgumentTypeError(f"'{arg}' is not a valid language")
    return code


def _threads(arg: str) -> int:
    code = arg.strip()
    try:
        threads = int(code)
        if threads >= 1:
            return threads
    except ValueError:
        pass
    raise ArgumentTypeError(f"'{arg}' is not a valid positive integer")


def _extension(arg: str) -> str:
    return _not_blank(arg).lstrip(".")


def _words(arg: str) -> Union[str, Path]:
    val = _not_blank(arg)
    if val.startswith(_FILE_PREFIX):
        return _file_path_input(val[len(_FILE_PREFIX):])
    return val


def _not_blank(arg: str) -> str:
    if not arg or arg.isspace():
        raise ArgumentTypeError("cannot be blank")
    return arg.strip()


def _version_info():
    return f"1G1R ROMset Generator v{__version__}"


def _parse_pattern(arg: str, ignore_case: bool, regex: bool) -> Pattern:
    return re.compile(
        arg if regex else re.escape(arg),
        re.I if ignore_case else 0)


def _parse_words(args, ls) -> Optional[List[Pattern]]:
    if not ls:
        return None
    result = []
    for i in ls:
        if isinstance(i, str):
            result.append(_parse_pattern(i, args.ignore_case, args.regex))
        elif isinstance(i, Path):
            with i.open() as f:
                for line in f:
                    line = line.strip()
                    if not line.isspace():
                        result.append(_parse_pattern(
                            line,
                            args.ignore_case,
                            args.regex))
    return result


def parse_opts():
    # noinspection PyTypeChecker
    my_parser = ArgumentParser(
        prog="1g1r-romset-generator",
        description="Organize and customize ROM sets using DAT files",
        formatter_class=RawTextHelpFormatter,
        add_help=True,
        epilog="\n".join((
            "See the README file for more details",
            "",
            _version_info(),
            f"For updates, check {GITHUB_URL}")))
    my_parser.add_argument(
        "-v",
        "--version",
        action="store_true",
        help="display version information")
    my_parser.add_argument(
        "--debug",
        action="store_true",
        help="log more messages (useful when troubleshooting)")

    output_mode_group = my_parser.add_argument_group("Output mode")
    output_mode_group.add_argument(
        "-m",
        "--mode",
        type=_mode,
        help="The desired output mode. Choices are:\n"
             + "\n".join(("%*i. %s" % (2, i, "\n\t- ".join(m.value))
                          for i, m in enumerate((o for o in OutputMode), 1))),
        required=True)

    input_group = my_parser.add_argument_group("Input/output files and folders")
    input_group.add_argument(
        "-d",
        "--dat",
        metavar="INPUT_DAT",
        type=_file_path_input,
        help="The input DAT file",
        required=True)
    input_group.add_argument(
        "-o",
        "--output-dir",
        type=_dir_path_output,
        help="The output directory (for modes which create or copy files)")
    input_group.add_argument(
        "--move",
        action="store_true",
        help="Move files instead of copying")

    selection_group = my_parser.add_argument_group("ROM selection")
    selection_group.add_argument(
        "-r",
        "--regions",
        metavar="REGION",
        type=_region,
        nargs=ONE_OR_MORE,
        help="\n".join((
            "Regions, space-separated from most preferred to least preferred",
            "By default, acts as a filter and the primary selection criteria")),
        required=True)
    selection_group.add_argument(
        "-l",
        "--languages",
        metavar="LANGUAGE",
        type=_lang,
        nargs=ONE_OR_MORE,
        help="\n".join((
            "Languages, space-separated from most preferred to least preferred",
            "By default, acts only as a secondary prioritization criteria")))

    scanning_group = my_parser.add_argument_group("File scanning")
    scanning_group.add_argument(
        "-t",
        "--threads",
        metavar="NUM_THREADS",
        type=_threads,
        default=4,
        help="\n".join((
            "The number of I/O threads to be used to read files",
            "(default: %(default)d)")))
    scanning_group.add_argument(
        "-e",
        "--extension",
        metavar="EXT",
        type=_extension,
        help="\n".join((
            "When matching ROMs by name, search for files using this extension",
            "If not set, the default ROM extension in the DAT is used")))
    scanning_group.add_argument(
        "--fallback-names",
        action="store_true",
        help="Try to match by file name if match by checksum fails")

    filtering_group = my_parser.add_argument_group("Filtering")
    filtering_group.add_argument(
        "--no-bios",
        action="store_true",
        help="Filter out BIOSes")
    filtering_group.add_argument(
        "--no-program",
        action="store_true",
        help="Filter out Programs and Test Programs")
    filtering_group.add_argument(
        "--no-chip",
        action="store_true",
        help="Filter out Ehancement Chips")
    filtering_group.add_argument(
        "--no-proto",
        action="store_true",
        help="Filter out prototype ROMs")
    filtering_group.add_argument(
        "--no-beta",
        action="store_true",
        help="Filter out beta ROMs")
    filtering_group.add_argument(
        "--no-demo",
        action="store_true",
        help="Filter out demo ROMs")
    filtering_group.add_argument(
        "--no-sample",
        action="store_true",
        help="Filter out sample ROMs")
    filtering_group.add_argument(
        "--no-pirate",
        action="store_true",
        help="Filter out pirate ROMs")
    filtering_group.add_argument(
        "--no-promo",
        action="store_true",
        help="Filter out promotion ROMs")
    filtering_group.add_argument(
        "--no-all",
        action="store_true",
        help="Apply all filters ABOVE")
    filtering_group.add_argument(
        "--no-unlicensed",
        action="store_true",
        help="Filter out unlicensed ROMs")
    filtering_group.add_argument(
        "--all-regions",
        action="store_true",
        help="Includes files of unselected regions as a last resource")
    filtering_group.add_argument(
        "--all-with-lang",
        action="store_true",
        help="Same as above, but only if the ROM has some selected language")
    filtering_group.add_argument(
        "--only-with-lang",
        action="store_true",
        help="Filter out ROMs without any selected languages")

    adjustment_group = my_parser.add_argument_group(
        "Adjustment and customization")
    adjustment_group.add_argument(
        "--prefer",
        metavar="WORD",
        type=_words,
        nargs=ONE_OR_MORE,
        help="ROMs containing these words will be preferred")
    adjustment_group.add_argument(
        "--avoid",
        metavar="WORD",
        type=_words,
        nargs=ONE_OR_MORE,
        help="ROMs containing these words will be avoided (but not excluded)")
    adjustment_group.add_argument(
        "--exclude",
        metavar="WORD",
        type=_words,
        nargs=ONE_OR_MORE,
        help="ROMs containing these words will be excluded")
    adjustment_group.add_argument(
        "--exclude-after",
        metavar="WORD",
        type=_words,
        nargs=ONE_OR_MORE,
        help="If the best candidate contains these words, skip all candidates")
    adjustment_group.add_argument(
        "--ignore-case",
        action="store_true",
        help="Make the options above case-insensitive")
    adjustment_group.add_argument(
        "--regex",
        action="store_true",
        help="Use the options above as regular expressions")
    adjustment_group.add_argument(
        "--prioritize-languages",
        action="store_true",
        help="Matching by language will precede matching by region")
    adjustment_group.add_argument(
        "--early-revisions",
        action="store_true",
        help="ROMs of earlier revisions will be prioritized")
    adjustment_group.add_argument(
        "--early-versions",
        action="store_true",
        help="ROMs of earlier versions will be prioritized")
    adjustment_group.add_argument(
        "--prefer-parents",
        action="store_true",
        help="Parent ROMs will be prioritized over clones")

    args = my_parser.parse_args()

    args.no_beta |= args.no_all
    args.no_bios |= args.no_all
    args.no_chip |= args.no_all
    args.no_demo |= args.no_all
    args.no_pirate |= args.no_all
    args.no_program |= args.no_all
    args.no_promo |= args.no_all
    args.no_proto |= args.no_all
    args.no_sample |= args.no_all

    args.prefer = _parse_words(args, args.prefer)
    args.avoid = _parse_words(args, args.avoid)
    args.exclude = _parse_words(args, args.exclude)
    args.exclude_after = _parse_words(args, args.exclude_after)

    print(args)

    if args.version:
        print(_version_info())
    sys.exit()

    if args.extension and not args.use_names:
        my_parser.error(
            "argument --extension required that --fallback-names is enabled")

    return


if __name__ == "__main__":
    parse_opts()
