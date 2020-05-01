import getopt
import sys
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import NamedTuple, List, Callable, TypeVar, Generic, Tuple, \
    Optional

__version__ = "1.9.4-SNAPSHOT"

from modules.classes import Score

_D = TypeVar("_D")


# TODO: we should handle CHDs
class OutputMode(Enum):
    PREVIEW = \
        ("Preview the list of selected ROMs",)
    COPY_RENAME = \
        ("Copy the files without restructuring or (un)compression",)
    UNCOMPRESSED = \
        ("Copy the files, uncompressing if needed",
         "Games with a single ROM are pur in the root of the output directory",
         "Games with multiple ROMs have them grouped in subdirectories")
    UNCOMPRESSED_CLRMAMEPRO = \
        ("Same as above, but following ClrMamePro's folder structure",
         "ROMs are always in subdirectories, regardless of the number of them",
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
         "Otherwise, it will be written to '<out_dir>/<dat>_custom_<date>.dat'")


class _Section(Enum):
    ROM_SELECTION = "ROM selection and file manipulation"
    FILE_SCANNING = "File scanning"
    FILTERING = "Filtering"
    ADJUSTMENT = "Adjustment and customization"
    HELP = "Help and debugging"


class _Flag(NamedTuple):
    section: _Section
    short_name: Optional[str]
    long_name: Optional[str]
    description: Tuple[str, ...]


class _Option(ABC, Generic[_D]):

    def __init__(
            self,
            section: _Section,
            short_name: str,
            long_name: str,
            description: Tuple[str, ...]) -> None:
        self.__section = section
        self.__short_name = short_name
        self.__long_name = long_name
        self.__description = description

    @property
    def section(self) -> _Section:
        return self.__section

    @property
    def short_name(self) -> str:
        return self.__short_name

    @property
    def long_name(self) -> str:
        return self.__long_name

    @property
    def description(self) -> Tuple[str, ...]:
        return self.__description

    @abstractmethod
    def parse(self, arg: str) -> _D:
        pass

    @abstractmethod
    def validate(self, result: _D) -> None:
        pass


class _RegionsOption(_Option[List[str]]):

    def parse(self, arg: str) -> List[str]:
        return [s.upper() for s in (r.strip() for r in arg.split(",")) if s]

    def validate(self, result: List[str]) -> None:
        if not result:
            raise ValueError("%s is required" % self.long_name)
        invalid_values = [r for r in result if len(r) != 3]
        if invalid_values:
            raise ValueError(
                "Invalid values for %s: %s"
                % (self.long_name, invalid_values))


class _Parameters(NamedTuple):
    mode: OutputMode
    move: bool
    dat_file: str
    input_dirs: Tuple[Path, ...]
    output_dir: Path
    regions: Tuple[str, ...]
    languages: Tuple[str, ...]
    language_weight: int
    parent_weight: int
    prioritize_languages: bool
    name_avoids: Tuple[Callable[[str], bool], ...]
    name_prefers: Tuple[Callable[[str], bool], ...]
    name_filters: Tuple[Callable[[str], bool], ...]
    name_filters_after: Tuple[Callable[[str], bool], ...]
    region_filter: Tuple[Callable[[Score], bool], ...]
    language_filter: Tuple[Callable[[Score], bool], ...]
    revision_multiplier: int
    version_multiplier: int
    no_scan: bool
    extension: str
    chunk_size: int
    threads: int
    debug: bool


class _Flags(Enum):
    MOVE = _Flag(
        _Section.ROM_SELECTION,
        None,
        "move",
        ("If set, move files instead of copying",))
    NO_SCAN = _Flag(
        _Section.FILE_SCANNING,
        None,
        "no-scan",
        ("If set, try to match ROMs by name only, ignoring file checksums",))
    NO_BIOS = _Flag(
        _Section.FILTERING,
        None,
        "no-bios",
        ("Filter out BIOSes",))
    NO_PROGRAM = _Flag(
        _Section.FILTERING,
        None,
        "no-program",
        ("Filter out Programs and Test Programs",))
    NO_ENHANCEMENT_CHIP = _Flag(
        _Section.FILTERING,
        None,
        "no-enhancement-chip",
        ("Filter out Ehancement Chips",))
    NO_PROTO = _Flag(
        _Section.FILTERING,
        None,
        "no-proto",
        ("Filter out prototype ROMs",))
    NO_BETA = _Flag(
        _Section.FILTERING,
        None,
        "no-beta",
        ("Filter out beta ROMs",))
    NO_DEMO = _Flag(
        _Section.FILTERING,
        None,
        "no-demo",
        ("Filter out demo ROMs",))
    NO_SAMPLE = _Flag(
        _Section.FILTERING,
        None,
        "no-sample",
        ("Filter out sample ROMs",))
    NO_PIRATE = _Flag(
        _Section.FILTERING,
        None,
        "no-pirate",
        ("Filter out pirate ROMs",))
    NO_PROMO = _Flag(
        _Section.FILTERING,
        None,
        "no-promo",
        ("Filter out promotion ROMs",))
    NO_ALL = _Flag(
        _Section.FILTERING,
        None,
        "no-all",
        ("Apply all filters ABOVE",))
    NO_UNLICENSED = _Flag(
        _Section.FILTERING,
        None,
        "no-unlicensed",
        ("Filter out unlicensed ROMs",))
    ALL_REGIONS = _Flag(
        _Section.FILTERING,
        None,
        "all-regions",
        ("Includes files of unselected regions as a last resource",))
    ALL_REGIONS_WITH_LANG = _Flag(
        _Section.FILTERING,
        None,
        "all-regions-with-lang",
        ("Same as above, but only if the ROM has some selected language",))
    ONLY_SELECTED_LANG = _Flag(
        _Section.FILTERING,
        None,
        "only-selected-lang",
        ("Filter out ROMs without any selected languages",))
    PRIORITIZE_LANGUAGES = _Flag(
        _Section.ADJUSTMENT,
        None,
        "prioritize-languages",
        ("If set, matching by language will precede matching by region",))
    EARLY_REVISIONS = _Flag(
        _Section.ADJUSTMENT,
        None,
        "early-revisions",
        ("ROMs of earlier revisions will be prioritized",))
    EARLY_VERSIONS = _Flag(
        _Section.ADJUSTMENT,
        None,
        "early-versions",
        ("ROMs of earlier versions will be prioritized",))
    PREFER_PARENTS = _Flag(
        _Section.ADJUSTMENT,
        None,
        "prefer-parents",
        ("Parent ROMs will be prioritized over clones",))
    IGNORE_CASE = _Flag(
        _Section.ADJUSTMENT,
        None,
        "ignore-case",
        ("If set, the avoid and exclude lists will be case-insensitive",))
    REGEX = _Flag(
        _Section.ADJUSTMENT,
        None,
        "regex",
        (
        "If set, the avoid and exclude lists are used as regular expressions",))
    HELP = _Flag(
        _Section.HELP,
        "h",
        "help",
        ("Print this message",))
    VERSION = _Flag(
        _Section.HELP,
        "v",
        "version",
        ("Print the version",))
    DEBUG = _Flag(
        _Section.HELP,
        None,
        "debug",
        ("Log more messages (useful when troubleshooting)",))


class _Options(Enum):
    REGIONS = _RegionsOption(
        _Section.ROM_SELECTION,
        "r",
        "regions",
        ("A list of regions separated by commas",
         "Ex.: -r USA,EUR,JPN"))


# -l,--languages=LANGS    An optional list of languages separated by commas
# This is a secondary prioritization criteria, not a filter
# Ex.: -l en,es,ru
# -d,--dat=DAT_FILE       The DAT file to be used
# Ex.: -d snes.dat
# -i,--input-dir=PATH     Provides an input directory (i.e.: where your ROMs are)
# Ex.: -i "C:\Users\John\Downloads\Emulators\SNES\ROMs"
# -o,--output-dir=PATH    If provided, ROMs will be copied to an output directory
# Ex.: -o "C:\Users\John\Downloads\Emulators\SNES\ROMs\1G1R"


def parse_opts(argv: List[str]):
    try:
        opts, args = getopt.getopt(argv, 'hd:r:e:i:Vo:l:w:v', [
            'help',
            'dat=',
            'regions=',
            'no-bios',
            'no-program',
            'no-enhancement-chip',
            'no-beta',
            'no-demo',
            'no-sample',
            'no-proto',
            'no-pirate',
            'no-promo',
            'no-all',
            'no-unlicensed',
            'all-regions',
            'early-revisions',
            'early-versions',
            'input-order',
            'extension=',
            'no-scan',
            'input-dir=',
            'prefer=',
            'avoid=',
            'exclude=',
            'exclude-after=',
            'separator=',
            'ignore-case',
            'regex',
            'verbose',
            'output-dir=',
            'languages=',
            'prioritize-languages',
            'language-weight=',
            'prefer-parents',
            'prefer-prereleases',
            'all-regions-with-lang',
            'debug',
            'move',
            'chunk-size=',
            'threads=',
            'header-file=',
            'max-file-size=',
            'version',
            'only-selected-lang'
        ])
    except getopt.GetoptError as e:
        sys.exit(help_msg(e))

    dat_file = ""
    filter_bios = False
    filter_program = False
    filter_enhancement_chip = False
    filter_unlicensed = False
    filter_pirate = False
    filter_promo = False
    filter_proto = False
    filter_beta = False
    filter_demo = False
    filter_sample = False
    all_regions = False
    all_regions_with_lang = False
    only_selected_lang = False
    revision_asc = False
    version_asc = False
    verbose = False
    no_scan = False
    input_order = False
    selected_regions: List[str] = []
    file_extension = ""
    input_dir = ""
    prefer_str = ""
    exclude_str = ""
    avoid_str = ""
    exclude_after_str = ""
    sep = ','
    ignore_case = False
    regex = False
    output_dir = ""
    selected_languages: List[str] = []
    prioritize_languages = False
    prefer_parents = False
    prefer_prereleases = False
    language_weight = 3
    move = False
    global THREADS
    global RULES
    global MAX_FILE_SIZE
    global CHUNK_SIZE
    global DEBUG
    for opt, arg in opts:
        if opt in ('-h', '--help'):
            print(help_msg())
            sys.exit()
        if opt in ('-v', '--version'):
            print('1G1R ROM set generator v%s' % __version__)
            sys.exit()
        if opt in ('-r', '--regions'):
            selected_regions = [x.strip().upper() for x in arg.split(',')
                                if is_valid(x)]
        if opt in ('-l', '--languages'):
            selected_languages = [x.strip().lower()
                                  for x in reversed(arg.split(','))
                                  if is_valid(x)]
        if opt in ('-w', '--language-weight'):
            try:
                language_weight = int(arg.strip())
                if language_weight <= 0:
                    sys.exit(help_msg(
                        'language-weight must be a positive integer'))
            except ValueError:
                sys.exit(help_msg('invalid value for language-weight'))
        prioritize_languages |= opt == '--prioritize-languages'
        filter_bios |= opt in ('--no-bios', '--no-all')
        filter_program |= opt in ('--no-program', '--no-all')
        filter_enhancement_chip |= opt in ('--no-enhancement-chip', '--no-all')
        filter_proto |= opt in ('--no-proto', '--no-all')
        filter_beta |= opt in ('--no-beta', '--no-all')
        filter_demo |= opt in ('--no-demo', '--no-all')
        filter_sample |= opt in ('--no-sample', '--no-all')
        filter_pirate |= opt in ('--no-pirate', '--no-all')
        filter_promo |= opt in ('--no-promo', '--no-all')
        filter_unlicensed |= opt == '--no-unlicensed'
        all_regions |= opt == '--all-regions'
        all_regions_with_lang |= opt == '--all-regions-with-lang'
        only_selected_lang |= opt == '--only-selected-lang'
        revision_asc |= opt == '--early-revisions'
        version_asc |= opt == '--early-versions'
        DEBUG |= opt == '--debug'
        verbose |= DEBUG or opt in ('-V', '--verbose')
        ignore_case |= opt == '--ignore-case'
        regex |= opt == '--regex'
        if opt == '--separator':
            sep = arg.strip()
        input_order |= opt == '--input-order'
        prefer_parents |= opt == '--prefer-parents'
        prefer_prereleases |= opt == '--prefer-prereleases'
        if opt in ('-d', '--dat'):
            dat_file = os.path.expanduser(arg.strip())
            if not os.path.isfile(dat_file):
                sys.exit(help_msg('invalid DAT file: %s' % dat_file))
        if opt in ('-e', '--extension'):
            file_extension = arg.strip().lstrip(os.path.extsep)
        no_scan |= opt == '--no-scan'
        if opt == '--prefer':
            prefer_str = arg
        if opt == '--avoid':
            avoid_str = arg
        if opt == '--exclude':
            exclude_str = arg
        if opt == '--exclude-after':
            exclude_after_str = arg
        if opt in ('-i', '--input-dir'):
            input_dir = os.path.expanduser(arg.strip())
            if not os.path.isdir(input_dir):
                sys.exit(help_msg('invalid input directory: %s' % input_dir))
        if opt in ('-o', '--output-dir'):
            output_dir = os.path.expanduser(arg.strip())
            if not os.path.isdir(output_dir):
                try:
                    os.makedirs(output_dir)
                except OSError:
                    sys.exit(help_msg('invalid output DIR: %s' % output_dir))
        move |= opt == '--move'
        if opt == '--chunk-size':
            CHUNK_SIZE = int(arg)
        if opt == '--threads':
            THREADS = int(arg)
        if opt == '--header-file':
            header_file = os.path.expanduser(arg.strip())
            if not os.path.isfile(header_file):
                sys.exit(help_msg('invalid header file: %s' % header_file))
            RULES = header.parse_rules(header_file)
        if opt == '--max-file-size':
            MAX_FILE_SIZE = int(arg)

    if not no_scan and not input_dir:
        print(
            'No input directory was provided. File scanning is disabled!',
            file=sys.stderr)
        print('Do you want to continue anyway? (y/n)', file=sys.stderr)
        answer = input()
        if answer.strip() not in ('y', 'Y'):
            sys.exit()
    use_hashes = bool(not no_scan and input_dir)
    if file_extension and use_hashes:
        sys.exit(help_msg('extensions cannot be used when scanning'))
    if not dat_file:
        sys.exit(help_msg('DAT file is required'))
    if not selected_regions:
        sys.exit(help_msg('invalid region selection'))
    if (revision_asc or version_asc) and input_order:
        sys.exit(help_msg(
            'early-revisions and early-versions are mutually exclusive '
            'with input-order'))
    if (revision_asc or version_asc) and prefer_parents:
        sys.exit(help_msg(
            'early-revisions and early-versions are mutually exclusive '
            'with prefer-parents'))
    if prefer_parents and input_order:
        sys.exit(help_msg(
            'prefer-parents is mutually exclusive with input-order'))
    if output_dir and not input_dir:
        sys.exit(help_msg('output-dir requires an input-dir'))
    if ignore_case and not prefer_str and not avoid_str and not exclude_str:
        sys.exit(help_msg(
            "ignore-case only works if there's a prefer, "
            "avoid or exclude list too"))
    if regex and not prefer_str and not avoid_str and not exclude_str:
        sys.exit(help_msg(
            "regex only works if there's a prefer, avoid or exclude list too"))
    if all_regions and all_regions_with_lang:
        sys.exit(help_msg(
            'all-regions is mutually exclusive with all-regions-with-lang'))
    if THREADS <= 0:
        sys.exit(help_msg('Number of threads should be > 0'))
    if MAX_FILE_SIZE <= 0:
        sys.exit(help_msg('Maximum file size should be > 0'))
    try:
        prefer = parse_list(prefer_str, ignore_case, regex, sep)
    except (re.error, OSError) as e:
        sys.exit(help_msg('invalid prefer list: %s' % e))
    try:
        avoid = parse_list(avoid_str, ignore_case, regex, sep)
    except (re.error, OSError) as e:
        sys.exit(help_msg('invalid avoid list: %s' % e))
    try:
        exclude = parse_list(exclude_str, ignore_case, regex, sep)
    except (re.error, OSError) as e:
        sys.exit(help_msg('invalid exclude list: %s' % e))
    try:
        exclude_after = parse_list(exclude_after_str, ignore_case, regex, sep)
    except (re.error, OSError) as e:
        sys.exit(help_msg('invalid exclude-after list: %s' % e))


def help_msg(s: Optional[Union[str, Exception]] = None) -> str:
    help_str = '\n'.join([
        'Usage: python3 %s [options] -d input_file.dat' % sys.argv[0],

        'Options:',

        '\n# ROM selection and file manipulation:',

        '\t-r,--regions=REGIONS\t'
        'A list of regions separated by commas'
        '\n\t\t\t\t'
        'Ex.: -r USA,EUR,JPN',

        '\t-l,--languages=LANGS\t'
        'An optional list of languages separated by commas'
        '\n\t\t\t\t'
        'This is a secondary prioritization criteria, not a filter'
        '\n\t\t\t\t'
        'Ex.: -l en,es,ru',

        '\t-d,--dat=DAT_FILE\t'
        'The DAT file to be used'
        '\n\t\t\t\t'
        'Ex.: -d snes.dat',

        '\t-i,--input-dir=PATH\t'
        'Provides an input directory (i.e.: where your ROMs are)'
        '\n\t\t\t\t'
        'Ex.: -i "C:\\Users\\John\\Downloads\\Emulators\\SNES\\ROMs"',

        '\t-o,--output-dir=PATH\t'
        'If provided, ROMs will be copied to an output directory'
        '\n\t\t\t\t'
        'Ex.: -o "C:\\Users\\John\\Downloads\\Emulators\\SNES\\ROMs\\1G1R"',

        '\t--move\t\t\t'
        'If set, ROMs will be moved, instead of copied, '
        'to the output directory',

        '\n# File scanning:',

        '\t--header-file=PATH\t'
        'Sets the header file to be used when scanning headered ROMs'
        '\n\t\t\t\t'
        'You can also just add the file to the headers directory',

        '\t--threads=THREADS\t'
        'Sets the number of I/O threads to be used to read files'
        '\n\t\t\t\t'
        'Default: 4',

        '\t--chunk-size=BYTES\t'
        'Sets the chunk size for buffered I/O operations (bytes)'
        '\n\t\t\t\t'
        'Default: 33554432 (32 MiB)',

        '\t--max-file-size=BYTES\t'
        'Sets the maximum file size for header information processing (bytes)'
        '\n\t\t\t\t'
        'Default: 268435456 (256 MiB)',

        '\t--no-scan\t\t'
        'If set, ROMs are not scanned and only file names are used to identify '
        'candidates',

        '\t-e,--extension=EXT\t'
        'When not scanning, ROM file names will use this extension'
        '\n\t\t\t\t'
        'Ex.: -e zip',

        '\n# Filtering:',

        '\t--no-bios\t\t'
        'Filter out BIOSes',

        '\t--no-program\t\t'
        'Filter out Programs and Test Programs',

        '\t--no-enhancement-chip\t'
        'Filter out Ehancement Chips',

        '\t--no-proto\t\t'
        'Filter out prototype ROMs',

        '\t--no-beta\t\t'
        'Filter out beta ROMs',

        '\t--no-demo\t\t'
        'Filter out demo ROMs',

        '\t--no-sample\t\t'
        'Filter out sample ROMs',

        '\t--no-pirate\t\t'
        'Filter out pirate ROMs',

        '\t--no-promo\t\t'
        'Filter out promotion ROMs',

        '\t--no-all\t\t'
        'Apply all filters above (WILL STILL ALLOW UNLICENSED ROMs)',

        '\t--no-unlicensed\t\t'
        'Filter out unlicensed ROMs',

        '\t--all-regions\t\t'
        'Includes files of unselected regions, if a selected one is not '
        'available',

        '\t--all-regions-with-lang\t'
        'Same as --all-regions, but only if a ROM has at least one selected '
        'language',

        '\t--only-selected-lang\t'
        'Filter out ROMs without any selected languages',

        '\n# Adjustment and customization:',

        '\t-w,--language-weight=N\t'
        'The degree of priority the first selected languages receive over the '
        'latter ones'
        '\n\t\t\t\t'
        'Default: 3',

        '\t--prioritize-languages\t'
        'If set, ROMs matching more languages will be prioritized over ROMs '
        'matching regions',

        '\t--early-revisions\t'
        'ROMs of earlier revisions will be prioritized',

        '\t--early-versions\t'
        'ROMs of earlier versions will be prioritized',

        '\t--input-order\t\t'
        'ROMs will be prioritized by the order they '
        'appear in the DAT file',

        '\t--prefer-parents\t'
        'Parent ROMs will be prioritized over clones',

        '\t--prefer-prereleases\t'
        'Prerelease (Beta, Proto, etc.) ROMs will be prioritized',

        '\t--prefer=WORDS\t\t'
        'ROMs containing these words will be preferred'
        '\n\t\t\t\t'
        'Ex.: --prefer "Virtual Console,GameCube"'
        '\n\t\t\t\t'
        'Ex.: --prefer "file:prefer.txt" ',

        '\t--avoid=WORDS\t\t'
        'ROMs containing these words will be avoided (but not excluded).'
        '\n\t\t\t\t'
        'Ex.: --avoid "Virtual Console,GameCube"'
        '\n\t\t\t\t'
        'Ex.: --avoid "file:avoid.txt" ',

        '\t--exclude=WORDS\t\t'
        'ROMs containing these words will be excluded.'
        '\n\t\t\t\t'
        'Ex.: --exclude "Virtual Console,GameCube"'
        '\n\t\t\t\t'
        'Ex.: --exclude "file:exclude.txt"',

        '\t--exclude-after=WORDS\t'
        'If the best candidate contains these words, skip all candidates.'
        '\n\t\t\t\t'
        'Ex.: --exclude-after "Virtual Console,GameCube"'
        '\n\t\t\t\t'
        'Ex.: --exclude-after "file:exclude-after.txt"',

        '\t--ignore-case\t\t'
        'If set, the avoid and exclude lists will be case-insensitive',

        '\t--regex\t\t\t'
        'If set, the avoid and exclude lists are used as regular expressions',

        '\t--separator=SEP\t\t'
        'Provides a separator for the avoid, exclude & exclude-after options.'
        '\n\t\t\t\t'
        'Default: ","',

        '\n# Help and debugging:',

        '\t-h,--help\t\t'
        'Prints this usage message',

        '\t-v,--version\t\t'
        'Prints the version',

        '\t-V,--verbose\t\t'
        'Logs more messages (useful when troubleshooting)',

        '\t--debug\t\t\t'
        'Logs even more messages (useful when troubleshooting)',

        '\n# See https://github.com/andrebrait/1g1r-romset-generator/wiki '
        'for more details'])
    if s:
        return '%s\n%s' % (s, help_str)
    else:
        return help_str


_Parameters(1, y='2')
