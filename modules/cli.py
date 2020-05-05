import getopt
import os
import string
import sys
from abc import ABC, abstractmethod
from collections import defaultdict
from enum import Enum
from pathlib import Path
from typing import NamedTuple, Callable, TypeVar, Generic, Tuple, \
    Optional, Dict, Union, List, Iterable

__version__ = "1.9.4-SNAPSHOT"

from modules.classes import Score

_FILE_PREFIX = "file:"

_D = TypeVar("_D")


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


class _Section(Enum):
    MODE = "Output mode"
    ROM_SELECTION = "ROM selection and file manipulation"
    FILE_SCANNING = "File scanning"
    FILTERING = "Filtering"
    ADJUSTMENT = "Adjustment and customization"
    HELP = "Help and debugging"


class _Flag(NamedTuple):
    section: _Section
    short_name: Optional[str]
    long_name: str
    description: Tuple[str, ...]


class _Option(ABC, Generic[_D]):

    def __init__(
            self,
            section: _Section,
            arity: Tuple[int, Optional[int]],
            short_name: Optional[str],
            long_name: str,
            description_var_name: str,
            description: Tuple[str, ...]) -> None:
        self.__section = section
        self.__arity = arity
        self.__short_name = short_name
        self.__long_name = long_name
        self.__description_var_name = description_var_name
        self.__description = description
        self.__invocations = 0

    @property
    def section(self) -> _Section:
        return self.__section

    @property
    def arity(self) -> Tuple[int, Optional[int]]:
        return self.__arity

    @property
    def short_name(self) -> Optional[str]:
        return self.__short_name

    @property
    def long_name(self) -> str:
        return self.__long_name

    @property
    def description_var_name(self) -> str:
        return self.__description_var_name

    @property
    def description(self) -> Tuple[str, ...]:
        return self.__description

    @abstractmethod
    def _parse(self, arg: str) -> _D:
        pass

    @abstractmethod
    def _validate(self, result: _D) -> None:
        pass

    def parse(self, arg: str) -> _D:
        self.__invocations += 1
        return self._parse(arg)

    def validate(self, result: _D) -> None:
        if self.__invocations < self.arity[0]:
            raise ValueError(
                "Option '%s' has to be used at least %i time(s)"
                % (self.long_name, self.arity[0]))
        if self.arity[1] or self.__invocations > self.arity[1]:
            raise ValueError(
                "Option '%s' can be used at most %i time(s)"
                % (self.long_name, self.arity[1]))
        self._validate(result)


def _not_blank(x: str) -> bool:
    return bool(x and not x.isspace())


class _Flags(Enum):
    MOVE = _Flag(
        _Section.ROM_SELECTION,
        None,
        "move",
        ("Move files instead of copying",))
    USE_NAMES = _Flag(
        _Section.FILE_SCANNING,
        None,
        "use-names",
        ("Use matching by file name as fallback when match by checksum fails",))
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
        ("Matching by language will precede matching by region",))
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
        ("Make 'prefer', 'avoid' and 'exclude' lists case-insensitive",))
    REGEX = _Flag(
        _Section.ADJUSTMENT,
        None,
        "regex",
        ("Parse 'prefer', 'avoid' and 'exclude' lists as regular expressions",))
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


class _ModeOption(_Option[OutputMode]):

    def _parse(self, arg: str) -> OutputMode:
        try:
            index = int(arg)
            return [o for o in OutputMode][index - 1]
        except (ValueError, IndexError):
            try:
                return OutputMode[arg]
            except KeyError:
                raise ValueError(
                    "Invalid value for '%s': %s" %
                    (self.long_name, arg))

    def _validate(self, result: OutputMode) -> None:
        if not result:
            raise ValueError("'%s' must not be blank" % self.long_name)


class _RegionsOption(_Option[Tuple[str, ...]]):

    def _parse(self, arg: str) -> Tuple[str, ...]:
        return tuple(s.strip().upper() for s in arg.split(",") if _not_blank(s))

    def _validate(self, result: Tuple[str, ...]) -> None:
        if not result:
            raise ValueError("'%s' must not be blank" % self.long_name)
        invalid_values = tuple(r for r in result if len(r) != 3)
        if invalid_values:
            raise ValueError(
                "Invalid values for '%s': %s"
                % (self.long_name, invalid_values))


class _LanguagesOption(_Option[Tuple[str, ...]]):

    def _parse(self, arg: str) -> Tuple[str, ...]:
        return tuple(s.strip().lower() for s in arg.split(",") if _not_blank(s))

    def _validate(self, result: Tuple[str, ...]) -> None:
        if not result:
            raise ValueError("'%s' must not be blank" % self.long_name)
        invalid_values = tuple(r for r in result if len(r) != 2)
        if invalid_values:
            raise ValueError(
                "Invalid values for '%s': %s"
                % (self.long_name, invalid_values))


class _InputDatOption(_Option[Path]):

    def _parse(self, arg: str) -> Path:
        return Path(arg).expanduser()

    def _validate(self, result: Path) -> None:
        if not result:
            raise ValueError("'%s' must not be blank" % self.long_name)
        if not result.exists():
            raise ValueError(
                "Invalid value for '%s': file '%s' not found"
                % (self.long_name, result))
        if not result.is_file():
            raise ValueError(
                "Invalid value for '%s': '%s' is not a file"
                % (self.long_name, result))


class _OutputDirOption(_Option[Path]):

    def _parse(self, arg: str) -> Path:
        return Path(arg).expanduser()

    def _validate(self, result: Path) -> None:
        if not result:
            raise ValueError("'%s' must not be blank" % self.long_name)
        if not result.exists():
            raise ValueError(
                "Invalid value for '%s': directory '%s' not found"
                % (self.long_name, result))
        if not result.is_dir():
            raise ValueError(
                "Invalid value for '%s': '%s' is not a directory"
                % (self.long_name, result))


class _ExtensionOption(_Option[str]):

    def _parse(self, arg: str) -> str:
        return arg.strip("%s%s" % (os.path.extsep, string.whitespace))

    def _validate(self, result: int) -> None:
        pass


class _SimpleNumericOption(_Option[int]):

    def _parse(self, arg: str) -> int:
        try:
            return int(arg)
        except ValueError:
            raise ValueError(
                "Invalid value for '%s': %s"
                % (self.long_name, arg))

    def _validate(self, result: int) -> None:
        if result <= 0:
            raise ValueError("'%s' must be greater than 0" % self.long_name)


class _StringOrFileOption(_Option[Tuple[str, ...]]):

    def _parse(self, arg: str) -> Tuple[str, ...]:
        if arg.startswith(_FILE_PREFIX):
            file = Path(arg[len(_FILE_PREFIX):]).expanduser()
            if not file.exists():
                raise ValueError(
                    "Invalid value for '%s': file '%s' not found"
                    % (self.long_name, file))
            if not file.is_file():
                raise ValueError(
                    "Invalid value for '%s': '%s' is not a file"
                    % (self.long_name, file))
            with file.open() as f:
                return tuple(line.rstrip() for line in f)
        return (arg,)

    def _validate(self, result: Tuple[str, ...]) -> None:
        pass


class _SeparatorOption(_Option[str]):

    def _parse(self, arg: str) -> str:
        return arg or ","

    def _validate(self, result: str) -> None:
        pass


class _Options(Enum):
    MODE = _ModeOption(
        _Section.MODE,
        (1, 1),
        "m",
        "mode",
        "MODE",
        ("The desired output mode",
         "Ex.: -m 1"))
    REGIONS = _RegionsOption(
        _Section.ROM_SELECTION,
        (1, None),
        "r",
        "regions",
        "REGIONS",
        ("Regions, from most preferred to least preferred",
         "By default, acts as a filter and the primary prioritization criteria",
         "Ex.: -r USA,EUR,JPN"))
    LANGUAGES = _LanguagesOption(
        _Section.ROM_SELECTION,
        (0, None),
        "l",
        "languages",
        "LANGS",
        ("Optional list of languages, from most preferred to least preferred",
         "By default, this acts only as a secondary prioritization criteria",
         "Ex.: -l en,es,ru"))
    DAT = _InputDatOption(
        _Section.ROM_SELECTION,
        (1, 1),
        "d",
        "dat",
        "DAT_FILE",
        ("The DAT file to be used",
         "Ex.: -d \"C:\\Users\\John\\Downloads\\DATs\\snes.dat\""))
    OUTPUT_DIR = _OutputDirOption(
        _Section.ROM_SELECTION,
        (0, 1),
        "o",
        "output-dir",
        "PATH",
        ("The output directory for modes which create or copy files",
         "Ex.: -o \"C:\\Users\\John\\Downloads\\Emulators\\SNES\\ROMs\\1G1R\""))
    THREADS = _SimpleNumericOption(
        _Section.FILE_SCANNING,
        (0, 1),
        "t",
        "threads",
        "THREADS",
        ("The number of I/O threads to be used to read files",
         "Default: 4"))
    EXTENSION = _ExtensionOption(
        _Section.FILE_SCANNING,
        (0, 1),
        "e",
        "extension",
        "EXT",
        ("When matching ROMs by name, search for files using this extension",
         "If not set, the default ROM extension in the DAT is used",
         "Ex.: -e zip"))
    PREFER = _StringOrFileOption(
        _Section.ADJUSTMENT,
        (0, None),
        None,
        "prefer",
        "WORDS",
        ("ROMs containing these words will be preferred",
         "Ex.: --prefer \"Virtual Console,GameCube\"",
         "Ex.: --prefer \"file:prefer.txt\""))
    AVOID = _StringOrFileOption(
        _Section.ADJUSTMENT,
        (0, None),
        None,
        "avoid",
        "WORDS",
        ("ROMs containing these words will be avoided (but not excluded)",
         "Ex.: --avoid \"Virtual Console,GameCube\"",
         "Ex.: --avoid \"file:avoid.txt\""))
    EXCLUDE = _StringOrFileOption(
        _Section.ADJUSTMENT,
        (0, None),
        None,
        "exclude",
        "WORDS",
        ("ROMs containing these words will be excluded",
         "Ex.: --exclude \"Virtual Console,GameCube\"",
         "Ex.: --exclude \"file:exclude.txt\""))
    EXCLUDE_AFTER = _StringOrFileOption(
        _Section.ADJUSTMENT,
        (0, None),
        None,
        "exclude-after",
        "WORDS",
        ("If the best candidate contains these words, skip all candidates",
         "Ex.: --exclude-after \"Virtual Console,GameCube\"",
         "Ex.: --exclude-after \"file:exclude-after.txt\""))
    SEPARATOR = _SeparatorOption(
        _Section.ADJUSTMENT,
        (0, 1),
        None,
        "separator",
        "SEP",
        ("Set a separator for the options above",
         "Default: \",\"",))


class _Parameters(NamedTuple):
    mode: OutputMode
    move: bool
    dat_file: Path
    input_dirs: Tuple[Path, ...]
    output_dir: Path
    regions: Tuple[str, ...]
    languages: Tuple[str, ...]
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
    threads: int
    debug: bool


_options: Tuple[_Option, ...] = tuple(o.value for o in _Options)
_flags: Tuple[_Flag, ...] = tuple(f.value for f in _Flags)
_options_by_section: Dict[_Section, Tuple[_Option, ...]] = defaultdict(tuple)
_flags_by_section: Dict[_Section, Tuple[_Flag, ...]] = defaultdict(tuple)

for o in _options:
    _options_by_section[o.section] += (o,)
for f in _flags:
    _flags_by_section[f.section] += (f,)


def _is_present(f: _Flag, opts: Iterable[Tuple[str, str]]) -> bool:
    for o in opts:
        if o[0].lstrip("-") in (f.short_name, f.long_name):
            return True
    return False


def parse_opts(argv: List[str]):
    try:
        short_names = \
            tuple("%s:" % o.short_name for o in _options if o.short_name) \
            + tuple(f.short_name for f in _flags if f.short_name)
        long_names = \
            tuple("%s=" % o.long_name for o in _options) \
            + tuple(f.long_name for f in _flags)
        opts, args = getopt.getopt(argv, "".join(short_names), long_names)
    except getopt.GetoptError as e:
        sys.exit(_help_msg(e))

    if _is_present(_Flags.HELP.value, opts):
        print(_help_msg())
        sys.exit()

    if _is_present(_Flags.VERSION.value, opts):
        print(_version_info())
        sys.exit()

    no_all = _is_present(_Flags.NO_ALL.value, opts)
    filter_bios = no_all or _is_present(_Flags.NO_BIOS.value, opts)
    filter_program = no_all or _is_present(_Flags.NO_PROGRAM.value, opts)
    filter_enhancement_chip = \
        no_all or _is_present(_Flags.NO_ENHANCEMENT_CHIP.value, opts)
    filter_pirate = no_all or _is_present(_Flags.NO_PIRATE.value, opts)
    filter_promo = no_all or _is_present(_Flags.NO_PROMO.value, opts)
    filter_proto = no_all or _is_present(_Flags.NO_PROTO.value, opts)
    filter_beta = no_all or _is_present(_Flags.NO_BETA.value, opts)
    filter_demo = no_all or _is_present(_Flags.NO_DEMO.value, opts)
    filter_sample = no_all or _is_present(_Flags.NO_SAMPLE.value, opts)
    filter_unlicensed = _is_present(_Flags.NO_UNLICENSED.value, opts)



#     dat_file = ""
#     filter_bios = False
#     filter_program = False
#     filter_enhancement_chip = False
#     filter_unlicensed = False
#     filter_pirate = False
#     filter_promo = False
#     filter_proto = False
#     filter_beta = False
#     filter_demo = False
#     filter_sample = False
#     all_regions = False
#     all_regions_with_lang = False
#     only_selected_lang = False
#     revision_asc = False
#     version_asc = False
#     verbose = False
#     no_scan = False
#     input_order = False
#     selected_regions: List[str] = []
#     file_extension = ""
#     input_dir = ""
#     prefer_str = ""
#     exclude_str = ""
#     avoid_str = ""
#     exclude_after_str = ""
#     sep = ','
#     ignore_case = False
#     regex = False
#     output_dir = ""
#     selected_languages: List[str] = []
#     prioritize_languages = False
#     prefer_parents = False
#     prefer_prereleases = False
#     language_weight = 3
#     move = False
#     global THREADS
#     global RULES
#     global MAX_FILE_SIZE
#     global CHUNK_SIZE
#     global DEBUG
#     for opt, arg in opts:
#         if opt in ('-h', '--help'):
#             print(help_msg())
#             sys.exit()
#         if opt in ('-v', '--version'):
#             print('1G1R ROM set generator v%s' % __version__)
#             sys.exit()
#         if opt in ('-r', '--regions'):
#             selected_regions = [x.strip().upper() for x in arg.split(',')
#                                 if _not_blank(x)]
#         if opt in ('-l', '--languages'):
#             selected_languages = [x.strip().lower()
#                                   for x in reversed(arg.split(','))
#                                   if _not_blank(x)]
#         if opt in ('-w', '--language-weight'):
#             try:
#                 language_weight = int(arg.strip())
#                 if language_weight <= 0:
#                     sys.exit(help_msg(
#                         'language-weight must be a positive integer'))
#             except ValueError:
#                 sys.exit(help_msg('invalid value for language-weight'))
#         prioritize_languages |= opt == '--prioritize-languages'
#         filter_bios |= opt in ('--no-bios', '--no-all')
#         filter_program |= opt in ('--no-program', '--no-all')
#         filter_enhancement_chip |= opt in ('--no-enhancement-chip', '--no-all')
#         filter_proto |= opt in ('--no-proto', '--no-all')
#         filter_beta |= opt in ('--no-beta', '--no-all')
#         filter_demo |= opt in ('--no-demo', '--no-all')
#         filter_sample |= opt in ('--no-sample', '--no-all')
#         filter_pirate |= opt in ('--no-pirate', '--no-all')
#         filter_promo |= opt in ('--no-promo', '--no-all')
#         filter_unlicensed |= opt == '--no-unlicensed'
#         all_regions |= opt == '--all-regions'
#         all_regions_with_lang |= opt == '--all-regions-with-lang'
#         only_selected_lang |= opt == '--only-selected-lang'
#         revision_asc |= opt == '--early-revisions'
#         version_asc |= opt == '--early-versions'
#         DEBUG |= opt == '--debug'
#         verbose |= DEBUG or opt in ('-V', '--verbose')
#         ignore_case |= opt == '--ignore-case'
#         regex |= opt == '--regex'
#         if opt == '--separator':
#             sep = arg.strip()
#         input_order |= opt == '--input-order'
#         prefer_parents |= opt == '--prefer-parents'
#         prefer_prereleases |= opt == '--prefer-prereleases'
#         if opt in ('-d', '--dat'):
#             dat_file = os.path.expanduser(arg.strip())
#             if not os.path.isfile(dat_file):
#                 sys.exit(help_msg('invalid DAT file: %s' % dat_file))
#         if opt in ('-e', '--extension'):
#             file_extension = arg.strip().lstrip(os.path.extsep)
#         no_scan |= opt == '--no-scan'
#         if opt == '--prefer':
#             prefer_str = arg
#         if opt == '--avoid':
#             avoid_str = arg
#         if opt == '--exclude':
#             exclude_str = arg
#         if opt == '--exclude-after':
#             exclude_after_str = arg
#         if opt in ('-i', '--input-dir'):
#             input_dir = os.path.expanduser(arg.strip())
#             if not os.path.isdir(input_dir):
#                 sys.exit(help_msg('invalid input directory: %s' % input_dir))
#         if opt in ('-o', '--output-dir'):
#             output_dir = os.path.expanduser(arg.strip())
#             if not os.path.isdir(output_dir):
#                 try:
#                     os.makedirs(output_dir)
#                 except OSError:
#                     sys.exit(help_msg('invalid output DIR: %s' % output_dir))
#         move |= opt == '--move'
#         if opt == '--chunk-size':
#             CHUNK_SIZE = int(arg)
#         if opt == '--threads':
#             THREADS = int(arg)
#         if opt == '--header-file':
#             header_file = os.path.expanduser(arg.strip())
#             if not os.path.isfile(header_file):
#                 sys.exit(help_msg('invalid header file: %s' % header_file))
#             RULES = header.parse_rules(header_file)
#         if opt == '--max-file-size':
#             MAX_FILE_SIZE = int(arg)
#
#     if not no_scan and not input_dir:
#         print(
#             'No input directory was provided. File scanning is disabled!',
#             file=sys.stderr)
#         print('Do you want to continue anyway? (y/n)', file=sys.stderr)
#         answer = input()
#         if answer.strip() not in ('y', 'Y'):
#             sys.exit()
#     use_hashes = bool(not no_scan and input_dir)
#     if file_extension and use_hashes:
#         sys.exit(help_msg('extensions cannot be used when scanning'))
#     if not dat_file:
#         sys.exit(help_msg('DAT file is required'))
#     if not selected_regions:
#         sys.exit(help_msg('invalid region selection'))
#     if (revision_asc or version_asc) and input_order:
#         sys.exit(help_msg(
#             'early-revisions and early-versions are mutually exclusive '
#             'with input-order'))
#     if (revision_asc or version_asc) and prefer_parents:
#         sys.exit(help_msg(
#             'early-revisions and early-versions are mutually exclusive '
#             'with prefer-parents'))
#     if prefer_parents and input_order:
#         sys.exit(help_msg(
#             'prefer-parents is mutually exclusive with input-order'))
#     if output_dir and not input_dir:
#         sys.exit(help_msg('output-dir requires an input-dir'))
#     if ignore_case and not prefer_str and not avoid_str and not exclude_str:
#         sys.exit(help_msg(
#             "ignore-case only works if there's a prefer, "
#             "avoid or exclude list too"))
#     if regex and not prefer_str and not avoid_str and not exclude_str:
#         sys.exit(help_msg(
#             "regex only works if there's a prefer, avoid or exclude list too"))
#     if all_regions and all_regions_with_lang:
#         sys.exit(help_msg(
#             'all-regions is mutually exclusive with all-regions-with-lang'))
#     if THREADS <= 0:
#         sys.exit(help_msg('Number of threads should be > 0'))
#     if MAX_FILE_SIZE <= 0:
#         sys.exit(help_msg('Maximum file size should be > 0'))
#     try:
#         prefer = parse_list(prefer_str, ignore_case, regex, sep)
#     except (re.error, OSError) as e:
#         sys.exit(help_msg('invalid prefer list: %s' % e))
#     try:
#         avoid = parse_list(avoid_str, ignore_case, regex, sep)
#     except (re.error, OSError) as e:
#         sys.exit(help_msg('invalid avoid list: %s' % e))
#     try:
#         exclude = parse_list(exclude_str, ignore_case, regex, sep)
#     except (re.error, OSError) as e:
#         sys.exit(help_msg('invalid exclude list: %s' % e))
#     try:
#         exclude_after = parse_list(exclude_after_str, ignore_case, regex, sep)
#     except (re.error, OSError) as e:
#         sys.exit(help_msg('invalid exclude-after list: %s' % e))
#
#
def _help_msg(s: Optional[Union[str, Exception]] = None) -> str:
    modes = tuple((i, m) for i, m in enumerate((o for o in OutputMode), 1))
    max_len = max(len("%i" % i[0]) for i in modes)
    mode_desc_indent = "%s%s- " % (os.linesep, " " * (max_len + 2))
    max_first_column = max(
        max(((len(o.short_name) + 2) if o.short_name else 0)
            + len(o.long_name) + 2 + len(o.description_var_name)
            for o in _options),
        max(((len(f.short_name) + 2) if f.short_name else 0)
            + len(f.long_name) + 2
            for f in _flags))
    option_desc_indent = "%s%s" % (os.linesep, (max_first_column + 2) * " ")

    usage = [
        _version_info(),
        "Usage: python3 %s [options]" % os.path.basename(sys.argv[0]),
        "",
        "Modes:",
        ""
    ]
    usage.extend(("%*i. %s" % (max_len, i, mode_desc_indent.join(m.value))
                  for i, m in modes))
    usage.extend((
        "",
        "Options:",
        ""
    ))
    for sec in _Section:
        usage.append("# %s" % sec.value)
        for o in _options_by_section[sec]:
            first_column = ("-%s," % o.short_name if o.short_name else "") \
                           + "--%s=%s" % (o.long_name, o.description_var_name)
            num_spaces = max_first_column - len(first_column) + 2
            first_column += num_spaces * " "
            second_column = option_desc_indent.join(o.description)
            usage.append("%s%s" % (first_column, second_column))
        for f in _flags_by_section[sec]:
            first_column = ("-%s," % f.short_name if f.short_name else "") \
                           + "--%s" % f.long_name
            num_spaces = max_first_column - len(first_column) + 2
            first_column += num_spaces * " "
            second_column = option_desc_indent.join(f.description)
            usage.append("%s%s" % (first_column, second_column))
        usage.append("")
    usage.append("# See the README file for more details")
    usage.append("# For updates, check %s"
                 % "https://github.com/andrebrait/1g1r-romset-generator")
    if s:
        return '%s%s' % (s, os.linesep.join(usage))
    else:
        return os.linesep.join(usage)


def _version_info():
    return "1G1R ROM set generator v%s" % __version__
