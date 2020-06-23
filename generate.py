#!/usr/bin/python3

import getopt
import hashlib
import re
import shutil
import sys
from io import BufferedIOBase
from pathlib import Path
from threading import current_thread
from typing import Optional, Match, List, Dict, Pattern, Callable, Union, \
    BinaryIO, TextIO
from zipfile import ZipFile, BadZipFile, ZipInfo, is_zipfile

from modules import datafile, header
from modules.classes import GameEntry, Score, RegionData, \
    GameEntryKeyGenerator, FileData, MultiThreadedProgressBar, IndexedThread, \
    CustomJsonEncoder
from modules.header import Rule
from modules.utils import get_index, check_in_pattern_list, to_int_list, \
    add_padding, get_or_default, available_columns, trim_to, is_valid

__version__ = '1.9.6'

PROGRESSBAR: Optional[MultiThreadedProgressBar] = None

FOUND_PREFIX = 'Found: '

THREADS: int = 4

CHUNK_SIZE = 33554432  # 32 MiB

MAX_FILE_SIZE = 268435456  # 256 MiB

FILE_PREFIX = 'file:'

UNSELECTED = 10000
NOT_PRERELEASE = "Z"

AVOIDED_ROM_BASE = 1000

RULES: List[Rule] = []

LOG_FILE: Optional[TextIO] = None

JSON_ENCODER = CustomJsonEncoder()

DEBUG = False

COUNTRY_REGION_CORRELATION = [
    # Language needs checking
    RegionData('ASI', re.compile(r'(Asia)', re.IGNORECASE), ['zh']),
    RegionData('ARG', re.compile(r'(Argentina)', re.IGNORECASE), ['es']),
    RegionData('AUS', re.compile(r'(Australia)', re.IGNORECASE), ['en']),
    RegionData('BRA', re.compile(r'(Brazil)', re.IGNORECASE), ['pt']),
    # Language needs checking
    RegionData('CAN', re.compile(r'(Canada)', re.IGNORECASE), ['en', 'fr']),
    RegionData(
        'CHN',
        re.compile(r'((China)|(Hong Kong))', re.IGNORECASE),
        ['zh']),
    RegionData('DAN', re.compile(r'(Denmark)', re.IGNORECASE), ['da']),
    RegionData('EUR', re.compile(r'((Europe)|(World))', re.IGNORECASE), ['en']),
    RegionData('FRA', re.compile(r'(France)', re.IGNORECASE), ['fr']),
    RegionData('FYN', re.compile(r'(Finland)', re.IGNORECASE), ['fi']),
    RegionData('GER', re.compile(r'(Germany)', re.IGNORECASE), ['de']),
    RegionData('GRE', re.compile(r'(Greece)', re.IGNORECASE), ['el']),
    RegionData('ITA', re.compile(r'(Italy)', re.IGNORECASE), ['it']),
    RegionData('JPN', re.compile(r'((Japan)|(World))', re.IGNORECASE), ['ja']),
    RegionData('HOL', re.compile(r'(Netherlands)', re.IGNORECASE), ['nl']),
    RegionData('KOR', re.compile(r'(Korea)', re.IGNORECASE), ['ko']),
    RegionData('MEX', re.compile(r'(Mexico)', re.IGNORECASE), ['es']),
    RegionData('NOR', re.compile(r'(Norway)', re.IGNORECASE), ['no']),
    RegionData('RUS', re.compile(r'(Russia)', re.IGNORECASE), ['ru']),
    RegionData('SPA', re.compile(r'(Spain)', re.IGNORECASE), ['es']),
    RegionData('SWE', re.compile(r'(Sweden)', re.IGNORECASE), ['sv']),
    RegionData('USA', re.compile(r'((USA)|(World))', re.IGNORECASE), ['en']),
    # Language needs checking
    RegionData('TAI', re.compile(r'(Taiwan)', re.IGNORECASE), ['zh'])
]

SECTIONS_REGEX = re.compile(r'\(([^()]+)\)')
BIOS_REGEX = re.compile(re.escape('[BIOS]'), re.IGNORECASE)
PROGRAM_REGEX = re.compile(r'\((?:Test\s*)?Program\)', re.IGNORECASE)
ENHANCEMENT_CHIP_REGEX = re.compile(r'\(Enhancement\s*Chip\)', re.IGNORECASE)
UNL_REGEX = re.compile(re.escape('(Unl)'), re.IGNORECASE)
PIRATE_REGEX = re.compile(re.escape('(Pirate)'), re.IGNORECASE)
PROMO_REGEX = re.compile(re.escape('(Promo)'), re.IGNORECASE)
BETA_REGEX = re.compile(r'\(Beta(?:\s*([a-z0-9.]+))?\)', re.IGNORECASE)
PROTO_REGEX = re.compile(r'\(Proto(?:\s*([a-z0-9.]+))?\)', re.IGNORECASE)
SAMPLE_REGEX = re.compile(r'\(Sample(?:\s*([a-z0-9.]+))?\)', re.IGNORECASE)
DEMO_REGEX = re.compile(r'\(Demo(?:\s*([a-z0-9.]+))?\)', re.IGNORECASE)
REV_REGEX = re.compile(r'\(Rev\s*([a-z0-9.]+)\)', re.IGNORECASE)
VERSION_REGEX = re.compile(r'\(v\s*([a-z0-9.]+)\)', re.IGNORECASE)
LANGUAGES_REGEX = re.compile(r'\(([a-z]{2}(?:[,+][a-z]{2})*)\)', re.IGNORECASE)
BAD_REGEX = re.compile(re.escape('[b]'), re.IGNORECASE)
ZIP_REGEX = re.compile(r'\.zip$', re.IGNORECASE)


def parse_revision(name: str) -> str:
    return get_or_default(REV_REGEX.search(name), '0')


def parse_version(name: str) -> str:
    return get_or_default(VERSION_REGEX.search(name), '0')


def parse_prerelease(match: Optional[Match]) -> str:
    return get_or_default(match, NOT_PRERELEASE)


def parse_region_data(name: str) -> List[RegionData]:
    parsed = []
    for section in SECTIONS_REGEX.finditer(name):
        elements = [element.strip() for element in section.group(1).split(',')]
        for element in elements:
            for region_data in COUNTRY_REGION_CORRELATION:
                if region_data.pattern \
                        and region_data.pattern.fullmatch(element):
                    parsed.append(region_data)
    return parsed


def parse_languages(name: str) -> List[str]:
    lang_matcher = LANGUAGES_REGEX.search(name)
    languages = []
    if lang_matcher:
        for entry in lang_matcher.group(1).split(','):
            for lang in entry.split('+'):
                languages.append(lang.lower())
    return languages


def get_region_data(code: str) -> Optional[RegionData]:
    code = code.upper() if code else code
    region_data = None
    for r in COUNTRY_REGION_CORRELATION:
        if r.code == code:
            region_data = r
            break
    if not region_data:
        # We don't know which region this is, but we should filter/classify it
        log('WARNING: unrecognized region (%s)' % code)
        region_data = RegionData(code, None, [])
        COUNTRY_REGION_CORRELATION.append(region_data)
    return region_data


def get_languages(region_data_list: List[RegionData]) -> List[str]:
    languages = []
    for region_data in region_data_list:
        for language in region_data.languages:
            if language not in languages:
                languages.append(language)
    return languages


def is_present(code: str, region_data: List[RegionData]) -> bool:
    for r in region_data:
        if r.code == code:
            return True
    return False


def validate_dat(file: Path, use_hashes: bool) -> None:
    root = datafile.parse(file, silence=True)
    has_cloneof = False
    lacks_sha1 = False
    offending_entry = ''
    for game in root.game:
        if game.cloneof:
            has_cloneof = True
            break
    for game in root.game:
        for game_rom in game.rom:
            if not game_rom.sha1:
                lacks_sha1 = True
                offending_entry = game.name
                break
    if use_hashes and lacks_sha1:
        sys.exit(
            'ERROR: Cannot use hash information because DAT lacks SHA1 digests '
            'for [%s].' % offending_entry)
    if not has_cloneof:
        print('This DAT *seems* to be a Standard DAT', file=sys.stderr)
        print(
            'A Parent/Clone XML DAT is required to generate a 1G1R ROM set',
            file=sys.stderr)
        if use_hashes:
            print(
                'If you are using this to rename files based on their hashes, '
                'a Standard DAT is enough',
                file=sys.stderr)
        print('Do you want to continue anyway? (y/n)', file=sys.stderr)
        answer = input()
        if answer.strip() not in ('y', 'Y'):
            sys.exit()


def parse_games(
        file: Path,
        filter_bios: bool,
        filter_program: bool,
        filter_enhancement_chip: bool,
        filter_pirate: bool,
        filter_promo: bool,
        filter_unlicensed: bool,
        filter_proto: bool,
        filter_beta: bool,
        filter_demo: bool,
        filter_sample: bool,
        exclude: List[Pattern]) -> Dict[str, List[GameEntry]]:
    games = {}
    root = datafile.parse(file, silence=True)
    for input_index in range(0, len(root.game)):
        game = root.game[input_index]
        beta_match = BETA_REGEX.search(game.name)
        demo_match = DEMO_REGEX.search(game.name)
        sample_match = SAMPLE_REGEX.search(game.name)
        proto_match = PROTO_REGEX.search(game.name)
        if filter_bios and BIOS_REGEX.search(game.name):
            continue
        if filter_unlicensed and UNL_REGEX.search(game.name):
            continue
        if filter_pirate and PIRATE_REGEX.search(game.name):
            continue
        if filter_promo and PROMO_REGEX.search(game.name):
            continue
        if filter_program and PROGRAM_REGEX.search(game.name):
            continue
        if filter_enhancement_chip and ENHANCEMENT_CHIP_REGEX.search(game.name):
            continue
        if filter_beta and beta_match:
            continue
        if filter_demo and demo_match:
            continue
        if filter_sample and sample_match:
            continue
        if filter_proto and proto_match:
            continue
        if check_in_pattern_list(game.name, exclude):
            continue
        is_parent = not game.cloneof
        is_bad = bool(BAD_REGEX.search(game.name))
        beta = parse_prerelease(beta_match)
        demo = parse_prerelease(demo_match)
        sample = parse_prerelease(sample_match)
        proto = parse_prerelease(proto_match)
        is_prerelease = bool(
            beta_match
            or demo_match
            or sample_match
            or proto_match)
        revision = parse_revision(game.name)
        version = parse_version(game.name)
        region_data = parse_region_data(game.name)
        for release in game.release:
            if release.region and not is_present(release.region, region_data):
                region_data.append(get_region_data(release.region))
        languages = parse_languages(game.name)
        if not languages:
            languages = get_languages(region_data)
        parent_name = game.cloneof if game.cloneof else game.name
        region_codes = [rd.code for rd in region_data]
        game_entries: List[GameEntry] = []
        for region in region_codes:
            game_entries.append(
                GameEntry(
                    is_bad,
                    is_prerelease,
                    region,
                    languages,
                    input_index,
                    revision,
                    version,
                    sample,
                    demo,
                    beta,
                    proto,
                    is_parent,
                    game.name,
                    game.rom if game.rom else []))
        if game_entries:
            if parent_name not in games:
                games[parent_name] = game_entries
            else:
                games[parent_name].extend(game_entries)
        else:
            log('WARNING [%s]: no recognizable regions found' % game.name)
        if not game.rom:
            log('WARNING [%s]: no ROMs found in the DAT file' % game.name)
    return games


def pad_values(
        games: List[GameEntry],
        get_function: Callable[[GameEntry], str],
        set_function: Callable[[GameEntry, str], None]) -> None:
    padded = add_padding([get_function(g) for g in games])
    for i in range(0, len(padded)):
        set_function(games[i], padded[i])


def language_value(
        languages: List[str],
        weight: int,
        selected_languages: List[str]) -> int:
    return sum([
        (get_index(selected_languages, lang, -1) + 1) * weight * -1
        for lang in languages])


def index_files(
        input_dir: Path,
        dat_file: Path) -> Dict[str, Optional[Path]]:
    result: Dict[str, Optional[Path]] = {}
    also_check_archive: bool = False
    root = datafile.parse(dat_file, silence=True)
    global RULES
    if not RULES:
        RULES = get_header_rules(root)
    for game in root.game:
        for rom_entry in game.rom:
            result[rom_entry.sha1.lower()] = None
            also_check_archive |= bool(ZIP_REGEX.search(rom_entry.name))
    print('Scanning directory: %s\033[K' % input_dir, file=sys.stderr)
    files_data = []
    for full_path in input_dir.rglob('*'):
        if not full_path.is_file():
            continue
        try:
            print(
                '%s%s\033[K' % (
                    FOUND_PREFIX,
                    trim_to(
                        full_path.relative_to(input_dir),
                        available_columns(FOUND_PREFIX) - 2)),
                end='\r',
                file=sys.stderr)
            file_size = full_path.stat().st_size
            files_data.append(FileData(file_size, full_path))
        except OSError as e:
            print(
                'Error while reading file: %s\033[K' % e,
                file=sys.stderr)
    files_data.sort(key=FileData.get_size, reverse=True)
    print('%s%i files\033[K' % (FOUND_PREFIX, len(files_data)), file=sys.stderr)

    if files_data:
        global PROGRESSBAR
        PROGRESSBAR = MultiThreadedProgressBar(
            len(files_data),
            THREADS,
            prefix='Calculating hashes')
        PROGRESSBAR.init()

        def process_thread_with_progress(
                shared_files_data: List[FileData],
                shared_result_data: List[Dict[str, Path]]) -> None:
            curr_thread = current_thread()
            if not isinstance(curr_thread, IndexedThread):
                sys.exit('Bad thread type. Expected %s' % IndexedThread)
            while True:
                try:
                    next_file = shared_files_data.pop(0)
                    PROGRESSBAR.print_thread(
                        curr_thread.index,
                        next_file.path.relative_to(input_dir))
                    shared_result_data.append(process_file(
                        next_file,
                        also_check_archive))
                    PROGRESSBAR.print_bar()
                except IndexError:
                    PROGRESSBAR.print_thread(curr_thread.index, "DONE")
                    break

        threads = []
        intermediate_results = []
        for i in range(0, THREADS):
            t = IndexedThread(
                index=i,
                target=process_thread_with_progress,
                args=[files_data, intermediate_results],
                daemon=True)
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        print('\n', file=sys.stderr)

        for intermediate_result in intermediate_results:
            for key, value in intermediate_result.items():
                if key in result and not \
                        (result[key] and is_zipfile(result[key])):
                    result[key] = value
    return result


def get_header_rules(root: datafile) -> List[Rule]:
    if root.header.clrmamepro:
        if root.header.clrmamepro.header:
            header_file = Path('headers', root.header.clrmamepro.header)
            if header_file.is_file():
                return header.parse_rules(header_file)
            else:
                log(
                    'WARNING: could not find header file %s. '
                    'This may cause hashes to be calculated wrong'
                    % header_file)
                return []


def process_file(
        file_data: FileData,
        also_check_archive: bool) -> Dict[str, Path]:
    full_path = file_data.path
    result: Dict[str, Path] = {}
    is_zip = is_zipfile(full_path)
    if is_zip:
        try:
            with ZipFile(full_path) as compressed_file:
                infos: List[ZipInfo] = compressed_file.infolist()
                for file_info in infos:
                    if file_info.is_dir():
                        continue
                    file_size = file_info.file_size
                    with compressed_file.open(file_info) as internal_file:
                        digest = compute_hash(file_size, internal_file)
                        result[digest] = full_path
                        if DEBUG:
                            log("DEBUG: Scan result for file [%s]: %s"
                                % (
                                    "%s:%s" % (full_path, file_info.filename),
                                    digest))
        except BadZipFile as e:
            print(
                'Error while reading file [%s]: %s\033[K' % (full_path, e),
                file=sys.stderr)
    if not is_zip or also_check_archive:
        try:
            file_size: int = full_path.stat().st_size
            with full_path.open('rb') as uncompressed_file:
                digest = compute_hash(file_size, uncompressed_file)
                if DEBUG:
                    log("DEBUG: Scan result for file [%s]: %s"
                        % (full_path, digest))
                if digest not in result or \
                        (result[digest] and is_zipfile(result[digest])):
                    result[digest] = full_path
        except IOError as e:
            print(
                'Error while reading file: %s\033[K' % e,
                file=sys.stderr)
    return result


def compute_hash(
        file_size: int,
        internal_file: Union[BufferedIOBase, BinaryIO]) -> str:
    hasher = hashlib.sha1()
    if RULES and file_size <= MAX_FILE_SIZE:
        file_bytes = internal_file.read()
        for rule in RULES:
            if rule.test(file_bytes):
                file_bytes = rule.apply(file_bytes)
        hasher.update(file_bytes)
    else:
        while True:
            chunk = internal_file.read(CHUNK_SIZE)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest().lower()


def main(argv: List[str]):
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

    dat_file: Optional[Path] = None
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
    input_dir: Optional[Path] = None
    prefer_str = ""
    exclude_str = ""
    avoid_str = ""
    exclude_after_str = ""
    sep = ','
    ignore_case = False
    regex = False
    output_dir: Optional[Path] = None
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
            dat_file = Path(arg.strip()).expanduser()
            if not dat_file.is_file():
                sys.exit(help_msg('invalid DAT file: %s' % dat_file))
        if opt in ('-e', '--extension'):
            file_extension = arg.strip().lstrip('.')
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
            input_dir = Path(arg.strip()).expanduser()
            if not input_dir.is_dir():
                sys.exit(help_msg('invalid input directory: %s' % input_dir))
        if opt in ('-o', '--output-dir'):
            output_dir = Path(arg.strip()).expanduser()
            if not output_dir.is_dir():
                try:
                    output_dir.mkdir(parents=True, exist_ok=True)
                except OSError:
                    sys.exit(help_msg('invalid output DIR: %s' % output_dir))
        move |= opt == '--move'
        if opt == '--chunk-size':
            CHUNK_SIZE = int(arg)
        if opt == '--threads':
            THREADS = int(arg)
        if opt == '--header-file':
            header_file = Path(arg.strip()).expanduser()
            if not header_file.is_file():
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

    validate_dat(dat_file, use_hashes)

    hash_index: Dict[str, Optional[Path]] = {}
    if use_hashes and input_dir:
        hash_index = index_files(input_dir, dat_file)
        if DEBUG:
            log('DEBUG: Scanned files: %s' % JSON_ENCODER.encode(hash_index))

    parsed_games = parse_games(
        dat_file,
        filter_bios,
        filter_program,
        filter_enhancement_chip,
        filter_pirate,
        filter_promo,
        filter_unlicensed,
        filter_proto,
        filter_beta,
        filter_demo,
        filter_sample,
        exclude)

    if verbose:
        region_text = 'Best region match'
        lang_text = 'Best language match'
        parents_text = 'Parent ROMs'
        index_text = 'Input order'
        filters = [
            (filter_bios, 'BIOSes'),
            (filter_program, 'Programs'),
            (filter_enhancement_chip, 'Enhancement Chips'),
            (filter_proto, 'Prototypes'),
            (filter_beta, 'Betas'),
            (filter_demo, 'Demos'),
            (filter_sample, 'Samples'),
            (filter_unlicensed, 'Unlicensed ROMs'),
            (filter_pirate, 'Pirate ROMs'),
            (filter_promo, 'Promo ROMs'),
            (only_selected_lang, 'ROMs not matching selected languages'),
            (bool(exclude_str), 'Excluded ROMs by name'),
            (bool(exclude_after_str), 'Excluded ROMs by name (after selection)')
        ]
        active_filters = [f[1] for f in filters if f[0]]
        if active_filters:
            print(
                'Filtering out:\n%s'
                % "".join(
                    ['\t%d. %s\n' % (i[0] + 1, i[1])
                     for i in enumerate(active_filters)]),
                file=sys.stderr)
        print(
            'Sorting with the following criteria:\n'
            '\t1. Good dumps\n'
            '\t2. %s\n'
            '\t3. Non-avoided items%s\n'
            '\t4. %s\n'
            '\t5. %s\n'
            '\t6. %s\n'
            '\t7. %s\n'
            '\t8. Preferred items%s\n'
            '\t9. %s revision\n'
            '\t10. %s version\n'
            '\t11. Latest sample\n'
            '\t12. Latest demo\n'
            '\t13. Latest beta\n'
            '\t14. Latest prototype\n'
            '\t15. Most languages supported\n'
            '\t16. Parent ROMs\n' %
            ('Prelease ROMs' if prefer_prereleases else 'Released ROMs',
             '' if avoid else ' (Ignored)',
             lang_text if prioritize_languages else region_text,
             region_text if prioritize_languages else lang_text,
             parents_text if prefer_parents else parents_text + ' (Ignored)',
             index_text if input_order else index_text + ' (Ignored)',
             '' if prefer else ' (Ignored)',
             'Earliest' if revision_asc else 'Latest',
             'Earliest' if version_asc else 'Latest'),
            file=sys.stderr)

    key_generator = GameEntryKeyGenerator(
        prioritize_languages,
        prefer_prereleases,
        prefer_parents,
        input_order,
        prefer,
        avoid)
    for key in parsed_games:
        games = parsed_games[key]
        pad_values(
            games,
            GameEntry.get_version,
            GameEntry.set_version)
        pad_values(
            games,
            GameEntry.get_revision,
            GameEntry.set_revision)
        pad_values(
            games,
            GameEntry.get_sample,
            GameEntry.set_sample)
        pad_values(
            games,
            GameEntry.get_demo,
            GameEntry.set_demo)
        pad_values(
            games,
            GameEntry.get_beta,
            GameEntry.set_beta)
        pad_values(
            games,
            GameEntry.get_proto,
            GameEntry.set_proto)
        set_scores(
            games,
            selected_regions,
            selected_languages,
            language_weight,
            revision_asc,
            version_asc)
        games.sort(key=key_generator.generate)
        if verbose:
            log(
                'INFO: Candidate order for [%s]: %s'
                % (key, [g.name for g in games]))

    printed_items: List[str] = []

    def include_candidate(x: GameEntry) -> bool:
        if only_selected_lang and x.score.languages >= 0:
            return False
        if all_regions_with_lang and x.score.languages < 0:
            return True
        if all_regions:
            return True
        return x.score.region != UNSELECTED

    for game in sorted(parsed_games.keys()):
        entries = parsed_games[game]
        if DEBUG:
            log(
                'DEBUG: Candidates for game [%s] before filtering: %s'
                % (game, JSON_ENCODER.encode(entries)))
        if not all_regions:
            entries = [x for x in entries if include_candidate(x)]
        if DEBUG:
            log(
                'DEBUG: Candidates for game [%s] after filtering: %s'
                % (game, JSON_ENCODER.encode(entries)))
        size = len(entries)
        for i in range(0, size):
            entry = entries[i]
            if check_in_pattern_list(entry.name, exclude_after):
                break
            if use_hashes:
                copied_files = set()
                num_roms = len(entry.roms)
                for entry_rom in entry.roms:
                    digest = entry_rom.sha1.lower()
                    rom_input_path = hash_index[digest]
                    if rom_input_path:
                        is_zip = is_zipfile(rom_input_path)
                        file = rom_input_path.relative_to(input_dir)
                        if not output_dir:
                            if rom_input_path not in copied_files:
                                printed_items.append(file)
                                copied_files.add(rom_input_path)
                        elif rom_input_path not in copied_files:
                            if not is_zip and (num_roms > 1
                                               or file.parent != file):
                                rom_output_dir = output_dir / entry.name
                                rom_output_dir.mkdir(
                                    parents=True,
                                    exist_ok=True)
                            else:
                                rom_output_dir = output_dir
                            if is_zip:
                                zip_name = add_extension(entry.name, 'zip')
                                rom_output_path = rom_output_dir / zip_name
                            else:
                                rom_output_path = \
                                    rom_output_dir / entry_rom.name
                            transfer_file(
                                rom_input_path,
                                rom_output_path,
                                move)
                            copied_files.add(rom_input_path)
                    else:
                        log(
                            'WARNING: ROM file [%s] for candidate [%s] '
                            'not found' % (entry_rom.name, entry.name))
                if copied_files:
                    break
                else:
                    log(
                        'WARNING: candidate [%s] not found, trying next one'
                        % entry.name)
                    if i == size - 1:
                        log(
                            'WARNING: no eligible candidates for [%s] '
                            'have been found!' % game)
            elif input_dir:
                file_name = add_extension(entry.name, file_extension)
                full_path = input_dir / file_name
                if full_path.is_file():
                    if output_dir:
                        transfer_file(full_path, output_dir, move)
                    else:
                        printed_items.append(file_name)
                    break
                elif full_path.is_dir():
                    for entry_rom in entry.roms:
                        rom_input_path = full_path / entry_rom.name
                        if rom_input_path.is_file():
                            if output_dir:
                                rom_output_dir = output_dir / file_name
                                rom_output_dir.mkdir(
                                    parents=True,
                                    exist_ok=True)
                                transfer_file(
                                    rom_input_path,
                                    rom_output_dir,
                                    move)
                                shutil.copystat(
                                    str(full_path),
                                    str(rom_output_dir))
                            else:
                                printed_items.append(
                                    file_name + '/' + entry_rom.name)
                        else:
                            log(
                                'WARNING: ROM file [%s] for candidate [%s] '
                                'not found' % (entry_rom.name, file_name))
                    break
                else:
                    log(
                        'WARNING: candidate [%s] not found, trying next one'
                        % file_name)
                    if i == size - 1:
                        log(
                            'WARNING: no eligible candidates for [%s] '
                            'have been found!' % game)
            else:
                printed_items.append(add_extension(entry.name, file_extension))
                break
    printed_items.sort()
    for item in printed_items:
        print(item)


def add_extension(file_name: str, file_extension: str) -> str:
    if file_extension:
        return file_name + '.' + file_extension
    return file_name


def parse_list(
        arg_str: str,
        ignore_case: bool,
        regex: bool,
        separator: str) -> List[Pattern]:
    if arg_str:
        if arg_str.startswith(FILE_PREFIX):
            file = Path((arg_str[len(FILE_PREFIX):]).strip()).expanduser()
            if not file.is_file():
                raise OSError('invalid file: %s' % file)
            arg_list = [x.strip() for x in open(file) if is_valid(x)]
        else:
            arg_list = [x.strip() for x in arg_str.split(separator)
                        if is_valid(x)]
        if ignore_case:
            return [re.compile(x if regex else re.escape(x), re.IGNORECASE)
                    for x in arg_list if is_valid(x)]
        else:
            return [re.compile(x if regex else re.escape(x))
                    for x in arg_list if is_valid(x)]
    return []


def set_scores(
        games: List[GameEntry],
        selected_regions: List[str],
        selected_languages: List[str],
        language_weight: int,
        revision_asc: bool,
        version_asc: bool) -> None:
    for game in games:
        region_score = get_index(selected_regions, game.region, UNSELECTED)
        languages_score = sum([
            (get_index(selected_languages, lang, -1) + 1) * -language_weight
            for lang in game.languages])
        revision_int = to_int_list(
            game.revision,
            1 if revision_asc else -1)
        version_int = to_int_list(game.version, 1 if version_asc else -1)
        sample_int = to_int_list(game.sample, -1)
        demo_int = to_int_list(game.demo, -1)
        beta_int = to_int_list(game.beta, -1)
        proto_int = to_int_list(game.proto, -1)
        game.score = Score(
            region_score,
            languages_score,
            revision_int,
            version_int,
            sample_int,
            demo_int,
            beta_int,
            proto_int)


def transfer_file(
        input_path: Path,
        output_path: Path,
        move: bool) -> None:
    try:
        if move:
            print('Moving [%s] to [%s]' % (input_path, output_path))
            shutil.move(str(input_path), str(output_path))
        else:
            print('Copying [%s] to [%s]' % (input_path, output_path))
            shutil.copy2(str(input_path), str(output_path))
    except OSError as e:
        print(
            'Error while transferring file: %s\033[K' % e,
            file=sys.stderr)


def log(s: str) -> None:
    print(s, file=LOG_FILE if LOG_FILE else sys.stderr)


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


if __name__ == '__main__':
    script_file = sys.argv[0]
    if '.' in script_file:
        script_file = script_file[:script_file.rindex('.')]
    log_file = add_extension(script_file, 'log')
    final_message = '\nExecution %s. Check the %s file for logs.' \
                    % ('%s', log_file)
    try:
        try:
            LOG_FILE = open(log_file, 'w')
        except OSError as w_e:
            print(
                'ERROR: could not open %s file for writing: %s'
                % (log_file, w_e),
                file=sys.stderr)
        main(sys.argv[1:])
        print(final_message % 'finished', file=sys.stderr)
    except KeyboardInterrupt:
        final_message = final_message % 'interrupted'
        if PROGRESSBAR:
            with PROGRESSBAR.lock:
                sys.exit('\n%s' % final_message)
        else:
            sys.exit('\n%s' % final_message)
