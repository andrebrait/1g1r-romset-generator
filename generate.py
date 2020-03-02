import getopt
import os
import re
import shutil
import sys
from typing import Optional, Match, List, Dict, Pattern, Any, Callable

import datafile
from datafile import rom

FILE_PREFIX = 'file:'

UNSELECTED = 10000
NOT_PRERELEASE = "Z"

AVOIDED_ROM_BASE = 1000

NO_WARNING: bool = False


class RegionData:
    def __init__(
            self,
            code: str,
            pattern: Optional[Pattern[str]],
            languages: List[str]):
        self.code = code
        self.pattern = pattern
        self.languages = languages


COUNTRY_REGION_CORRELATION = [
    # Language needs checking
    RegionData('ASI', re.compile(r'(Asia)', re.IGNORECASE), ['zh']),
    RegionData('AUS', re.compile(r'(Australia)', re.IGNORECASE), ['en']),
    RegionData('ARG', re.compile(r'(Argentina)', re.IGNORECASE), ['es']),
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
    RegionData('MEX', re.compile(r'(Mexico)', re.IGNORECASE), ['es']),
    RegionData('HOL', re.compile(r'(Netherlands)', re.IGNORECASE), ['nl']),
    RegionData('KOR', re.compile(r'(Korea)', re.IGNORECASE), ['ko']),
    RegionData('NOR', re.compile(r'(Norway)', re.IGNORECASE), ['no']),
    RegionData('RUS', re.compile(r'(Russia)', re.IGNORECASE), ['ru']),
    RegionData('SPA', re.compile(r'(Spain)', re.IGNORECASE), ['es']),
    RegionData('SWE', re.compile(r'(Sweden)', re.IGNORECASE), ['sv']),
    RegionData('USA', re.compile(r'((USA)|(World))', re.IGNORECASE), ['en']),
    # Language needs checking
    RegionData('TAI', re.compile(r'(Taiwan)', re.IGNORECASE), ['zh'])
]


class Score:
    def __init__(
            self,
            region: int,
            languages: int,
            revision: List[int],
            version: List[int],
            sample: List[int],
            demo: List[int],
            beta: List[int],
            proto: List[int]):
        self.region = region
        self.languages = languages
        self.revision = revision
        self.version = version
        self.sample = sample
        self.demo = demo
        self.beta = beta
        self.proto = proto

    def __repr__(self):
        return str(self.__dict__)


class GameEntry:
    def __init__(
            self,
            is_bad: bool,
            is_prerelease: bool,
            region: str,
            languages: List[str],
            input_index: int,
            revision: str,
            version: str,
            sample: str,
            demo: str,
            beta: str,
            proto: str,
            is_parent: bool,
            name: str,
            roms: List[rom]):
        self.is_bad = is_bad
        self.is_prerelease = is_prerelease
        self.region = region
        self.languages = languages
        self.input_index = input_index
        self.revision = revision
        self.version = version
        self.sample = sample
        self.demo = demo
        self.beta = beta
        self.proto = proto
        self.is_parent = is_parent
        self.name = name
        self.roms = roms
        self.score: Optional[Score] = None

    def __repr__(self):
        return str(self.__dict__)

    def set_revision(self, revision: str) -> None:
        self.revision = revision

    def set_version(self, version: str) -> None:
        self.version = version

    def set_sample(self, sample: str) -> None:
        self.sample = sample

    def set_demo(self, demo: str) -> None:
        self.demo = demo

    def set_beta(self, beta: str) -> None:
        self.beta = beta

    def set_proto(self, proto: str) -> None:
        self.proto = proto


sections_regex = re.compile(r'\(([^()]+)\)')
bios_regex = re.compile(re.escape('[BIOS]'), re.IGNORECASE)
program_regex = re.compile(r'\((?:Test\s*)?Program\)', re.IGNORECASE)
enhancement_chip_regex = re.compile(r'\(Enhancement\s*Chip\)', re.IGNORECASE)
unl_regex = re.compile(re.escape('(Unl)'), re.IGNORECASE)
pirate_regex = re.compile(re.escape('(Pirate)'), re.IGNORECASE)
promo_regex = re.compile(re.escape('(Promo)'), re.IGNORECASE)
beta_regex = re.compile(r'\(Beta(?:\s*([a-z0-9.]+))?\)', re.IGNORECASE)
proto_regex = re.compile(r'\(Proto(?:\s*([a-z0-9.]+))?\)', re.IGNORECASE)
sample_regex = re.compile(r'\(Sample(?:\s*([a-z0-9.]+))?\)', re.IGNORECASE)
demo_regex = re.compile(r'\(Demo(?:\s*([a-z0-9.]+))?\)', re.IGNORECASE)
rev_regex = re.compile(r'\(Rev\s*([a-z0-9.]+)\)', re.IGNORECASE)
version_regex = re.compile(r'\(v\s*([a-z0-9.]+)\)', re.IGNORECASE)
languages_regex = re.compile(r'\(([a-z]{2}(?:[,+][a-z]{2})*)\)', re.IGNORECASE)
bad_regex = re.compile(re.escape('[b]'), re.IGNORECASE)


def to_int_list(string: str, multiplier: int) -> List[int]:
    return [multiplier * ord(x) for x in string]


def get(ls: List[int], index: int) -> int:
    return ls[index] if index < len(ls) else 0


def add_padding(strings: List[str]) -> List[str]:
    parts_list = [s.split('.') for s in strings]
    lengths = [[len(part) for part in parts] for parts in parts_list]
    max_parts = max([len(parts) for parts in parts_list])
    max_lengths = [max([get(lenght, i) for lenght in lengths])
                   for i in range(0, max_parts)]
    for parts in parts_list:
        for i in range(0, len(parts)):
            parts[i] = ('0' * (max_lengths[i] - len(parts[i]))) + parts[i]
    return ['.'.join(parts) for parts in parts_list]


def get_or_default(match: Optional[Match], default: str) -> str:
    version = match.group(1) if match else None
    return version if version else default


def parse_revision(name: str) -> str:
    return get_or_default(rev_regex.search(name), '0')


def parse_version(name: str) -> str:
    return get_or_default(version_regex.search(name), '0')


def parse_prerelease(match: Optional[Match]) -> str:
    return get_or_default(match, NOT_PRERELEASE)


def parse_region_data(name: str) -> List[RegionData]:
    parsed = []
    for section in sections_regex.finditer(name):
        elements = [element.strip() for element in section.group(1).split(',')]
        for element in elements:
            for region_data in COUNTRY_REGION_CORRELATION:
                if region_data.pattern \
                        and region_data.pattern.fullmatch(element):
                    parsed.append(region_data)
    return parsed


def parse_languages(name: str) -> List[str]:
    lang_matcher = languages_regex.search(name)
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
        if not NO_WARNING:
            print(
                'WARNING: unrecognized region (%s)' % code,
                file=sys.stderr)
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


def parse_games(
        file: str,
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
        beta_match = beta_regex.search(game.name)
        demo_match = demo_regex.search(game.name)
        sample_match = sample_regex.search(game.name)
        proto_match = proto_regex.search(game.name)
        if filter_bios and bios_regex.search(game.name):
            continue
        if filter_unlicensed and unl_regex.search(game.name):
            continue
        if filter_pirate and pirate_regex.search(game.name):
            continue
        if filter_promo and promo_regex.search(game.name):
            continue
        if filter_program and program_regex.search(game.name):
            continue
        if filter_enhancement_chip and enhancement_chip_regex.search(game.name):
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
        is_bad = bool(bad_regex.search(game.name))
        beta = parse_prerelease(beta_match)
        demo = parse_prerelease(demo_match)
        sample = parse_prerelease(sample_match)
        proto = parse_prerelease(proto_match)
        is_prerelease = bool(beta_match
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
        elif not NO_WARNING:
            print(
                'WARNING [%s]: no recognizable regions found' % game.name,
                file=sys.stderr)
        if not game.rom and not NO_WARNING:
            print(
                'WARNING [%s]: no ROMs found in the DAT file' % game.name,
                file=sys.stderr)
    return games


def get_index(ls: List[Any], item: Any, default: int) -> int:
    try:
        if ls:
            return ls.index(item)
        return default
    except ValueError:
        return default


def check_in_pattern_list(name: str, patterns: List[Pattern]) -> bool:
    if patterns:
        for pattern in patterns:
            if pattern.search(name):
                return True
    return False


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


def main(argv: List[str]):
    global NO_WARNING
    try:
        opts, args = getopt.getopt(argv, 'hd:r:e:i:vo:l:w:', [
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
            'input-dir=',
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
            'no-warning'
        ])
    except getopt.GetoptError as e:
        print(e, file=sys.stderr)
        print_help()
        sys.exit(2)

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
    revision_asc = False
    version_asc = False
    verbose = False
    input_order = False
    selected_regions: List[str] = []
    file_extension = ""
    input_dir = ""
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
    debug = False
    move = False
    for opt, arg in opts:
        if opt in ('-h', '--help'):
            print_help()
            sys.exit()
        if opt in ('-r', '--regions'):
            selected_regions = [x.strip().upper() for x in arg.split(',')]
        if opt in ('-l', '--languages'):
            selected_languages = [x.strip().lower()
                                  for x in reversed(arg.split(','))]
        if opt in ('-w', '--language-weight'):
            try:
                language_weight = int(arg.strip())
                if language_weight <= 0:
                    print(
                        'language-weight must be a positive integer',
                        file=sys.stderr)
                    print_help()
                    sys.exit(2)
            except ValueError:
                print('invalid value for language-weight', file=sys.stderr)
                print_help()
                sys.exit(2)
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
        revision_asc |= opt == '--early-revisions'
        version_asc |= opt == '--early-versions'
        verbose |= opt in ('-v', '--verbose')
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
                print('invalid DAT file: %s' % dat_file, file=sys.stderr)
                print_help()
                sys.exit(2)
        if opt in ('-e', '--extension'):
            file_extension = arg.strip().lstrip(os.path.extsep)
        if opt == '--avoid':
            avoid_str = arg
        if opt == '--exclude':
            exclude_str = arg
        if opt == '--exclude-after':
            exclude_after_str = arg
        if opt in ('-i', '--input-dir'):
            input_dir = os.path.expanduser(arg.strip())
            if not os.path.isdir(input_dir):
                print(
                    'invalid input directory: %s' % input_dir,
                    file=sys.stderr)
                print_help()
                sys.exit(2)
        if opt in ('-o', '--output-dir'):
            output_dir = os.path.expanduser(arg.strip())
            if not os.path.isdir(output_dir):
                try:
                    os.makedirs(output_dir)
                except OSError:
                    print(
                        'invalid output DIR: %s' % output_dir,
                        file=sys.stderr)
                    print_help()
                    sys.exit(2)
        debug |= opt == '--debug'
        NO_WARNING |= opt == '--no-warning'
        if debug:
            verbose = True
        move |= opt == '--move'
    if not dat_file:
        print('DAT file is required', file=sys.stderr)
        print_help()
        sys.exit(2)
    if not selected_regions:
        print('invalid region selection', file=sys.stderr)
        print_help()
        sys.exit(2)
    if (revision_asc or version_asc) and input_order:
        print(
            'early-revisions and early-versions are mutually exclusive '
            'with input-order',
            file=sys.stderr)
        print_help()
        sys.exit(2)
    if (revision_asc or version_asc) and prefer_parents:
        print(
            'early-revisions and early-versions are mutually exclusive '
            'with prefer-parents',
            file=sys.stderr)
        print_help()
        sys.exit(2)
    if prefer_parents and input_order:
        print(
            'prefer-parents is mutually exclusive with input-order',
            file=sys.stderr)
        print_help()
        sys.exit(2)
    if output_dir and not input_dir:
        print('output-dir requires an input-dir', file=sys.stderr)
        print_help()
        sys.exit(2)
    if ignore_case and not avoid_str and not exclude_str:
        print(
            "ignore-case only works if there's an avoid or exclude list too",
            file=sys.stderr)
        print_help()
        sys.exit(2)
    if regex and not avoid_str and not exclude_str:
        print(
            "regex only works if there's an avoid or exclude list too",
            file=sys.stderr)
        print_help()
        sys.exit(2)
    if all_regions and all_regions_with_lang:
        print(
            'all-regions is mutually exclusive with all-regions-with-lang',
            file=sys.stderr)
        print_help()
        sys.exit(2)
    try:
        avoid = parse_list(avoid_str, ignore_case, regex, sep)
    except (re.error, OSError) as e:
        print('invalid avoid list: %s' % e, file=sys.stderr)
        print_help()
        sys.exit(2)
    try:
        exclude = parse_list(exclude_str, ignore_case, regex, sep)
    except (re.error, OSError) as e:
        print('invalid exclude list: %s' % e, file=sys.stderr)
        print_help()
        sys.exit(2)
    try:
        exclude_after = parse_list(exclude_after_str, ignore_case, regex, sep)
    except (re.error, OSError) as e:
        print('invalid exclude-after list: %s' % e, file=sys.stderr)
        print_help()
        sys.exit(2)

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
            (bool(exclude_str), 'Excluded ROMs by name'),
            (bool(exclude_after_str), 'Excluded ROMs by name (after selection)')
        ]
        enabled_filters = ['\t%d. %s\n' % (i + 1, filters[i][1])
                           for i in range(0, len(filters)) if filters[i][0]]
        if enabled_filters:
            print(
                'Filtering out:\n'
                + "".join(enabled_filters),
                file=sys.stderr)
        print(
            'Sorting with the following criteria:\n'
            '\t1. Good dumps\n'
            '\t2. %s\n'
            '\t3. Non-avoided items\n'
            '\t4. %s\n'
            '\t5. %s\n'
            '\t6. %s\n'
            '\t7. %s\n'
            '\t8. %s revision\n'
            '\t9. %s version\n'
            '\t10. Latest sample\n'
            '\t11. Latest demo\n'
            '\t12. Latest beta\n'
            '\t13. Latest prototype\n'
            '\t14. Most languages supported\n'
            '\t15. Parent ROMs\n' %
            ('Prelease ROMs' if prefer_prereleases else 'Released ROMs',
             lang_text if prioritize_languages else region_text,
             region_text if prioritize_languages else lang_text,
             parents_text if prefer_parents else parents_text + ' (Ignored)',
             index_text if input_order else index_text + ' (Ignored)',
             'Earliest' if revision_asc else 'Latest',
             'Earliest' if version_asc else 'Latest'),
            file=sys.stderr)

    for key in parsed_games:
        games = parsed_games[key]
        pad_values(games, lambda g: g.version, lambda g, s: g.set_version(s))
        pad_values(games, lambda g: g.revision, lambda g, s: g.set_revision(s))
        pad_values(games, lambda g: g.sample, lambda g, s: g.set_sample(s))
        pad_values(games, lambda g: g.demo, lambda g, s: g.set_demo(s))
        pad_values(games, lambda g: g.beta, lambda g, s: g.set_beta(s))
        pad_values(games, lambda g: g.proto, lambda g, s: g.set_proto(s))
        set_scores(games,
                   selected_regions,
                   selected_languages,
                   language_weight,
                   revision_asc,
                   version_asc)
        games.sort(key=lambda g: (
            g.is_bad,
            prefer_prereleases ^ g.is_prerelease,
            check_in_pattern_list(g.name, avoid),
            g.score.languages if prioritize_languages else g.score.region,
            g.score.region if prioritize_languages else g.score.languages,
            prefer_parents and not g.is_parent,
            g.input_index if input_order else 0,
            g.score.revision,
            g.score.version,
            g.score.sample,
            g.score.demo,
            g.score.beta,
            g.score.proto,
            -len(g.languages),
            not g.is_parent))
        if verbose:
            print(
                'Candidate order for [%s]: %s' % (key, [g.name for g in games]),
                file=sys.stderr)

    for game, entries in parsed_games.items():
        if not all_regions:
            entries = [x for x in entries if x.score.region != UNSELECTED
                       or (all_regions_with_lang and x.score.languages < 0)]
        if debug:
            print(
                'Handling candidates for game [%s]: %s' % (game, entries),
                file=sys.stderr)
        size = len(entries)
        for i in range(0, size):
            entry = entries[i]
            if check_in_pattern_list(entry.name, exclude_after):
                break
            file_name = entry.name
            if file_extension:
                file_name = file_name + os.path.extsep + file_extension
            if input_dir:
                full_path = os.path.join(input_dir, file_name)
                if os.path.isfile(full_path):
                    if output_dir:
                        transfer_file(full_path, output_dir, move)
                    else:
                        print(file_name)
                    break
                elif os.path.isdir(full_path):
                    for entry_rom in entry.roms:
                        rom_full_path = os.path.join(full_path, entry_rom.name)
                        if os.path.isfile(rom_full_path):
                            if output_dir:
                                rom_output_dir = os.path.join(
                                    output_dir,
                                    file_name)
                                os.makedirs(rom_output_dir, exist_ok=True)
                                transfer_file(
                                    rom_full_path,
                                    rom_output_dir,
                                    move)
                                shutil.copystat(full_path, rom_output_dir)
                            else:
                                print(file_name + os.path.sep + entry_rom.name)
                        elif not NO_WARNING:
                            if verbose:
                                print(
                                    'WARNING [%s]: ROM file [%s] for candidate '
                                    '[%s] not found' %
                                    (game, entry_rom.name, file_name),
                                    file=sys.stderr)
                            else:
                                print(
                                    'WARNING: ROM file [%s] for candidate [%s] '
                                    'not found' % (entry_rom.name, file_name),
                                    file=sys.stderr)
                elif not NO_WARNING:
                    if verbose:
                        print(
                            'WARNING [%s]: candidate [%s] not found, '
                            'trying next one' % (game, file_name),
                            file=sys.stderr)
                    else:
                        print(
                            'WARNING: candidate [%s] not found, '
                            'trying next one' % file_name,
                            file=sys.stderr)
                    if i == size - 1:
                        print(
                            'WARNING: no eligible candidates for [%s] '
                            'have been found!' % game,
                            file=sys.stderr)
            else:
                print(file_name)
                break


def parse_list(
        arg_str: str,
        ignore_case: bool,
        regex: bool,
        separator: str) -> List[Pattern]:
    if arg_str:
        if arg_str.startswith(FILE_PREFIX):
            file = (arg_str[len(FILE_PREFIX):]).strip()
            file = os.path.expanduser(file)
            if not os.path.isfile(file):
                raise OSError('invalid file: %s' % file)
            arg_list = [x.strip() for x in open(file)]
        else:
            arg_list = [x.strip() for x in arg_str.split(separator)]
        if ignore_case:
            return [re.compile(x if regex else re.escape(x), re.IGNORECASE)
                    for x in arg_list]
        else:
            return [re.compile(x if regex else re.escape(x))
                    for x in arg_list]
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
        full_path: str,
        output_dir: str,
        move: bool) -> None:
    file_name = os.path.basename(full_path)
    if move:
        print('Moving [%s] to [%s]' % (file_name, output_dir))
        shutil.move(full_path, output_dir)
    else:
        print('Copying [%s] to [%s]' % (file_name, output_dir))
        shutil.copy2(full_path, output_dir)


def print_help():
    print(
        'Usage: python3 %s [options] -d input_file.dat' % sys.argv[0],
        file=sys.stderr)
    print('Options:', file=sys.stderr)
    print('\n# ROM selection and file manipulation:', file=sys.stderr)
    print(
        '\t-r,--regions=REGIONS\t'
        'A list of regions separated by commas.'
        '\n\t\t\t\t'
        'Ex.: -r USA,EUR,JPN',
        file=sys.stderr)
    print(
        '\t-l,--languages=LANGS\t'
        'An optional list of languages separated by commas.'
        '\n\t\t\t\t'
        'Ex.: -l en,es,ru',
        file=sys.stderr)
    print(
        '\t-d,--dat=DAT_FILE\t'
        'The DAT file to be used'
        '\n\t\t\t\t'
        'Ex.: -d snes.dat',
        file=sys.stderr)
    print(
        '\t-i,--input-dir=PATH\t'
        'Provides an input directory (i.e.: where your ROMs are)'
        '\n\t\t\t\t'
        'Ex.: -i "C:\\Users\\John\\Downloads\\Emulators\\SNES\\ROMs"',
        file=sys.stderr)
    print(
        '\t-e,--extension=EXT\t'
        'ROM names will use this extension.'
        '\n\t\t\t\t'
        'Ex.: -e zip',
        file=sys.stderr)
    print(
        '\t-o,--output-dir=PATH\t'
        'If provided, ROMs will be copied to an output directory'
        '\n\t\t\t\t'
        'Ex.: -o "C:\\Users\\John\\Downloads\\Emulators\\SNES\\ROMs\\1G1R"',
        file=sys.stderr)
    print(
        '\t--move\t\t\t'
        'If set, ROMs will be moved, instead of copied, '
        'to the output directory',
        file=sys.stderr)
    print('\n# Filtering:', file=sys.stderr)
    print(
        '\t--no-bios\t\t'
        'Filter out BIOSes',
        file=sys.stderr)
    print(
        '\t--no-program\t\t'
        'Filter out Programs and Test Programs',
        file=sys.stderr)
    print(
        '\t--no-enhancement-chip\t'
        'Filter out Ehancement Chips',
        file=sys.stderr)
    print(
        '\t--no-proto\t\t'
        'Filter out prototype ROMs',
        file=sys.stderr)
    print(
        '\t--no-beta\t\t'
        'Filter out beta ROMs',
        file=sys.stderr)
    print(
        '\t--no-demo\t\t'
        'Filter out demo ROMs',
        file=sys.stderr)
    print(
        '\t--no-sample\t\t'
        'Filter out sample ROMs',
        file=sys.stderr)
    print(
        '\t--no-pirate\t\t'
        'Filter out pirate ROMs',
        file=sys.stderr)
    print(
        '\t--no-promo\t\t'
        'Filter out promotion ROMs',
        file=sys.stderr)
    print(
        '\t--no-all\t\t'
        'Apply all filters above (WILL STILL ALLOW UNLICENSED ROMs)',
        file=sys.stderr)
    print(
        '\t--no-unlicensed\t\t'
        'Filter out unlicensed ROMs',
        file=sys.stderr)
    print(
        '\t--all-regions\t\t'
        'Includes files of unselected regions, if a selected one is not '
        'available',
        file=sys.stderr)
    print(
        '\t--all-regions-with-lang\t'
        'Same as --all-regions, but only if a ROM has at least one selected '
        'language',
        file=sys.stderr)
    print('\n# Adjustment and customization:', file=sys.stderr)
    print(
        '\t-w,--language-weight=N\t'
        'The degree of priority the first selected languages receive over the '
        'latter ones.'
        '\n\t\t\t\t'
        'Default: 3',
        file=sys.stderr)
    print(
        '\t--prioritize-languages\t'
        'If set, ROMs matching more languages will be prioritized over ROMs '
        'matching regions',
        file=sys.stderr)
    print(
        '\t--early-revisions\t'
        'ROMs of earlier revisions will be prioritized',
        file=sys.stderr)
    print(
        '\t--early-versions\t'
        'ROMs of earlier versions will be prioritized',
        file=sys.stderr)
    print(
        '\t--input-order\t\t'
        'ROMs will be prioritized by the order they '
        'appear in the DAT file',
        file=sys.stderr)
    print(
        '\t--prefer-parents\t'
        'Parent ROMs will be prioritized over clones',
        file=sys.stderr)
    print(
        '\t--prefer-prereleases\t'
        'Prerelease (Beta, Proto, etc.) ROMs will be prioritized',
        file=sys.stderr)
    print(
        '\t--avoid=WORDS\t\t'
        'ROMs containing these words will be avoided (but not excluded).'
        '\n\t\t\t\t'
        'Ex.: --avoid "Virtual Console,GameCube"'
        '\n\t\t\t\t'
        'Ex.: --avoid "file:avoid.txt" ',
        file=sys.stderr)
    print(
        '\t--exclude=WORDS\t\t'
        'ROMs containing these words will be excluded.'
        '\n\t\t\t\t'
        'Ex.: --exclude "Virtual Console,GameCube"'
        '\n\t\t\t\t'
        'Ex.: --exclude "file:exclude.txt"',
        file=sys.stderr)
    print(
        '\t--exclude-after=WORDS\t'
        'If the best candidate contains these words, skip all candidates.'
        '\n\t\t\t\t'
        'Ex.: --exclude-after "Virtual Console,GameCube"'
        '\n\t\t\t\t'
        'Ex.: --exclude-after "file:exclude-after.txt"',
        file=sys.stderr)
    print(
        '\t--ignore-case\t\t'
        'If set, the avoid and exclude lists will be case-insensitive',
        file=sys.stderr)
    print(
        '\t--regex\t\t\t'
        'If set, the avoid and exclude lists are used as regular expressions',
        file=sys.stderr)
    print(
        '\t--separator=SEP\t\t'
        'Provides a separator for the avoid, exclude & exclude-after options.'
        '\n\t\t\t\t'
        'Default: ","',
        file=sys.stderr)
    print('\n# Help and debugging:', file=sys.stderr)
    print(
        '\t-h,--help\t\t'
        'Prints this usage message',
        file=sys.stderr)
    print(
        '\t-v,--verbose\t\t'
        'Prints more messages (useful when troubleshooting)',
        file=sys.stderr)
    print(
        '\t--debug\t\t\t'
        'Prints even more messages (useful when troubleshooting)',
        file=sys.stderr)
    print(
        '\t--no-warning\t\t'
        'Supresses all warnings',
        file=sys.stderr)
    print(
        '\n# See https://github.com/andrebrait/1g1r-romset-generator/wiki '
        'for more details',
        file=sys.stderr)


if __name__ == '__main__':
    main(sys.argv[1:])
