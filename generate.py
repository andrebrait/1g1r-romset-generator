import getopt
import os
import re
import shutil
import sys
from math import copysign
from typing import Optional, Match, List, Dict, Pattern, Any, Callable

import datafile

UNSELECTED = 10000
NOT_PRERELEASE = "Z"

BLACKLISTED_ROM_BASE = 1000


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
    RegionData('ASI', re.compile(r'(Asia)', re.IGNORECASE), ['zh']),  # Language needs checking
    RegionData('AUS', re.compile(r'(Australia)', re.IGNORECASE), ['en']),
    RegionData('BRA', re.compile(r'(Brazil)', re.IGNORECASE), ['pt']),
    RegionData('CAN', re.compile(r'(Canada)', re.IGNORECASE), ['en', 'fr']),  # Language needs checking
    RegionData('CHN', re.compile(r'((China)|(Hong Kong))', re.IGNORECASE), ['zh']),
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
    RegionData('NOR', re.compile(r'(Norway)', re.IGNORECASE), ['no']),
    RegionData('RUS', re.compile(r'(Russia)', re.IGNORECASE), ['ru']),
    RegionData('SPA', re.compile(r'(Spain)', re.IGNORECASE), ['es']),
    RegionData('SWE', re.compile(r'(Sweden)', re.IGNORECASE), ['sv']),
    RegionData('USA', re.compile(r'((USA)|(World))', re.IGNORECASE), ['en']),
    RegionData('TAI', re.compile(r'(Taiwan)', re.IGNORECASE), ['zh'])  # Language needs checking
]


class GameEntry:
    def __init__(
            self,
            is_bad: bool,
            is_prerelease: bool,
            regions: List[str],
            languages: List[str],
            input_index: int,
            revision: str,
            version: str,
            sample: str,
            demo: str,
            beta: str,
            proto: str,
            is_parent: bool,
            rom: datafile.rom):
        self.is_bad = is_bad
        self.is_prerelease = is_prerelease
        self.regions = regions
        self.languages = languages
        self.input_index = input_index
        self.revision = revision
        self.version = version
        self.sample = sample
        self.demo = demo
        self.beta = beta
        self.proto = proto
        self.is_parent = is_parent
        self.rom = rom

    def set_revision(self, revision):
        self.revision = revision

    def set_version(self, version):
        self.version = version

    def set_sample(self, sample):
        self.sample = sample

    def set_demo(self, demo):
        self.demo = demo

    def set_beta(self, beta):
        self.beta = beta

    def set_proto(self, proto):
        self.proto = proto


sections_regex = re.compile(r'\\(([^()]+)\\)')
bios_regex = re.compile(re.escape('[BIOS]'), re.IGNORECASE)
program_regex = re.compile(re.escape('(Program)'), re.IGNORECASE)
unl_regex = re.compile(re.escape('(Unl)'), re.IGNORECASE)
beta_regex = re.compile(r'\(Beta(?:\s*([a-z0-9.]+))?\)', re.IGNORECASE)
proto_regex = re.compile(r'\(Proto(?:\s*([a-z0-9.]+))?\)', re.IGNORECASE)
sample_regex = re.compile(r'\(Sample(?:\s*([a-z0-9.]+))?\)', re.IGNORECASE)
demo_regex = re.compile(r'\(Demo(?:\s*([a-z0-9.]+))?\)', re.IGNORECASE)
rev_regex = re.compile(r'\(Rev\\s*([a-z0-9.]+)\)', re.IGNORECASE)
version_regex = re.compile(r'\(v\s*([a-z0-9.]+)\)', re.IGNORECASE)
languages_regex = re.compile(r'\(([a-z]{2}(?:[,+][a-z]{2})*)\)', re.IGNORECASE)
bad_regex = re.compile(re.escape('[b]'), re.IGNORECASE)


def to_int_list(string: str, multiplier: int) -> List[int]:
    return [multiplier * ord(x) for x in string]


def get(ls: List[int], i: int) -> int:
    return ls[i] if i < len(ls) else 0


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
        print('WARNING: unrecognized region (' + code + ')', file=sys.stderr)
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
        filter_unlicensed: bool,
        filter_proto: bool,
        filter_beta: bool,
        filter_demo: bool,
        filter_sample: bool) -> Dict[str, List[GameEntry]]:
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
        if filter_program and program_regex.search(game.name):
            continue
        if filter_beta and beta_match:
            continue
        if filter_demo and demo_match:
            continue
        if filter_sample and sample_match:
            continue
        if filter_proto and proto_match:
            continue
        is_parent = game.cloneof is None
        is_bad = bad_regex.search(game.name) is not None
        beta = parse_prerelease(beta_match)
        demo = parse_prerelease(demo_match)
        sample = parse_prerelease(sample_match)
        proto = parse_prerelease(proto_match)
        is_prerelease = beta_match is not None \
            or demo_match is not None \
            or sample_match is not None \
            or proto_match is not None
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
        if parent_name not in games:
            games[parent_name] = []
        for rom in game.rom:
            games[parent_name].append(
                GameEntry(
                    is_bad,
                    is_prerelease,
                    [rd.code for rd in region_data],
                    languages,
                    input_index,
                    revision,
                    version,
                    sample,
                    demo,
                    beta,
                    proto,
                    is_parent,
                    rom))
    return games


def get_index(ls: List, i: Any, default: int) -> int:
    try:
        return ls.index(i)
    except ValueError:
        return default


def replace_extension(extension, file_name):
    try:
        return file_name[:file_name.rindex(os.extsep)] + os.extsep + extension
    except ValueError:
        return file_name + os.extsep + extension


def check_blacklist(
        ls: List[int],
        name: str,
        blacklist: Optional[List[Pattern]]) -> List[int]:
    if blacklist:
        for pattern in blacklist:
            if pattern.search(name):
                return [int(copysign(abs(x) + BLACKLISTED_ROM_BASE, x))
                        for x in ls]
    return ls


def pad_values(
        ls: List[GameEntry],
        fg: Callable[[GameEntry], str],
        fs: Callable[[GameEntry, str], None]) -> None:
    padded = add_padding([fg(g) for g in ls])
    for i in range(0, len(padded)):
        fs(ls[i], padded[i])


def language_value(
        game: GameEntry,
        weight: int,
        selected_languages: List[str]) -> int:
    return sum([
        (get_index(selected_languages, lang, -1) + 1) * weight
        for lang in game.languages])


def region_indexes(
        game: GameEntry,
        selected_regions: List[str],
        blacklist: Optional[List[Pattern]]) -> List[int]:
    indexes = \
        [get_index(selected_regions, r, UNSELECTED) for r in game.regions]
    indexes = check_blacklist(indexes, game.rom.name, blacklist)
    indexes.sort()
    return indexes


def main(argv: List[str]):
    try:
        opts, args = getopt.getopt(argv, 'hd:r:e:i:b:vo:l:w:', [
            'help',
            'dat=',
            'regions=',
            'no-bios',
            'no-program',
            'no-unlicensed',
            'no-beta',
            'no-demo',
            'no-sample',
            'no-proto',
            'no-all',
            'all-regions',
            'early-revisions',
            'early-versions',
            'input-order',
            'extension=',
            'input-dir=',
            'blacklist=',
            'case-insensitive',
            'verbose',
            'output-dir=',
            'languages=',
            'prioritize-languages',
            'language-weight='
        ])
    except getopt.GetoptError as e:
        print(e, file=sys.stderr)
        print_help()
        sys.exit(2)

    dat_file = None
    filter_bios = False
    filter_program = False
    filter_unlicensed = False
    filter_proto = False
    filter_beta = False
    filter_demo = False
    filter_sample = False
    all_regions = False
    revision_asc = False
    version_asc = False
    verbose = False
    input_order = False
    selected_regions = None
    file_extension = None
    input_dir = None
    blacklist = None
    ignore_case = False
    output_dir = None
    selected_languages = None
    prioritize_languages = False
    prefer_parents = False
    language_weight = 1
    for opt, arg in opts:
        if opt in ('-h', '--help'):
            print_help()
            sys.exit()
        if opt in ('-r', '--regions'):
            selected_regions = [x.strip().upper() for x in arg.split(',')]
        if opt in ('-l', '--languages'):
            selected_languages = [x.strip().lower() for x in arg.split(',')]
        if opt in ('-w', '--language-weight'):
            try:
                language_weight = int(arg.strip())
            except ValueError:
                print('invalid value for language-weight', file=sys.stderr)
                print_help()
                sys.exit(2)
        prioritize_languages |= opt == '--prioritize-languages'
        filter_bios |= opt == '--no-bios' or opt == '--no-all'
        filter_program |= opt == '--no-program' or opt == '--no-all'
        filter_unlicensed |= opt == '--no-unlicensed' or opt == '--no-all'
        filter_proto |= opt == '--no-proto' or opt == '--no-all'
        filter_beta |= opt == '--no-beta' or opt == '--no-all'
        filter_demo |= opt == '--no-demo' or opt == '--no-all'
        filter_sample |= opt == '--no-sample' or opt == '--no-all'
        all_regions |= opt == '--all-regions'
        revision_asc |= opt == '--early-revisions'
        version_asc |= opt == '--early-versions'
        verbose |= opt in ('-v', '--verbose')
        ignore_case |= opt == '--ignore-case'
        input_order |= opt == '--input-order'
        if opt in ('-d', '--dat'):
            dat_file = os.path.expanduser(arg.strip())
            if not os.path.isfile(dat_file):
                print('invalid DAT file: ' + dat_file, file=sys.stderr)
                print_help()
                sys.exit(2)
        if opt in ('-e', '--extension'):
            file_extension = arg.strip().lstrip(os.extsep)
        if opt in ('-b', '--blacklist'):
            blacklist = arg.split(',')
        if opt in ('-i', '--input-dir'):
            input_dir = os.path.expanduser(arg.strip())
            if not os.path.isdir(input_dir):
                print('invalid input directory: ' + input_dir, file=sys.stderr)
                print_help()
                sys.exit(2)
        if opt in ('-o', '--output-dir'):
            output_dir = os.path.expanduser(arg.strip())
            if not os.path.isdir(output_dir):
                try:
                    os.makedirs(output_dir)
                except OSError:
                    print('invalid output DIR: ' + output_dir, file=sys.stderr)
                    print_help()
                    sys.exit(2)
    if not dat_file:
        print('DAT file is required', file=sys.stderr)
        print_help()
        sys.exit(2)
    if not selected_regions:
        print('invalid region selection', file=sys.stderr)
        print_help()
        sys.exit(2)
    if (revision_asc or version_asc) and input_order:
        print('early-revisions and early-versions are mutually exclusive with input-order', file=sys.stderr)
        print_help()
        sys.exit(2)
    if output_dir and not input_dir:
        print('output-dir requires an input-dir', file=sys.stderr)
        print_help()
        sys.exit(2)
    if ignore_case and not blacklist:
        print("ignore-case only works if there's a blacklist too", file=sys.stderr)
        print_help()
        sys.exit(2)
    if ignore_case:
        blacklist = [re.compile(re.escape(x), re.IGNORECASE) for x in blacklist]
    else:
        blacklist = [re.compile(re.escape(x)) for x in blacklist]

    parsed_games = parse_games(
        dat_file,
        filter_bios,
        filter_program,
        filter_unlicensed,
        filter_proto,
        filter_beta,
        filter_demo,
        filter_sample)

    for key in parsed_games:
        games = parsed_games[key]
        pad_values(games, lambda g: g.version, lambda g, s: g.set_version(s))
        pad_values(games, lambda g: g.revision, lambda g, s: g.set_revision(s))
        pad_values(games, lambda g: g.sample, lambda g, s: g.set_sample(s))
        pad_values(games, lambda g: g.demo, lambda g, s: g.set_demo(s))
        pad_values(games, lambda g: g.beta, lambda g, s: g.set_beta(s))
        pad_values(games, lambda g: g.proto, lambda g, s: g.set_proto(s))
        games.sort(key=lambda g: (
            g.is_bad,
            g.is_prerelease,
            language_value(g, language_weight, selected_languages)
            if prioritize_languages
            else region_indexes(g, selected_regions, blacklist),
            region_indexes(g, selected_regions, blacklist)
            if prioritize_languages
            else language_value(g, language_weight, selected_languages),
            prefer_parents and not g.is_parent,
            g.input_index if input_order else 0,
            to_int_list(g.revision, 1 if revision_asc else -1),
            to_int_list(g.version, 1 if version_asc else -1),
            to_int_list(g.sample, -1),
            to_int_list(g.demo, -1),
            to_int_list(g.beta, -1),
            to_int_list(g.proto, -1),
            not g.is_parent,
            len(g.rom.name)))
        if verbose:
            print('Candidate order for [' + key + ']: '
                  + str([g.rom.name for g in games]), file=sys.stderr)

    for game, entries in parsed_games.items():
        for entry in entries:
            file_name = entry.rom.name
            if file_extension:
                file_name = replace_extension(file_extension, file_name)
            if input_dir:
                full_path = os.path.join(input_dir, file_name)
                if os.path.isfile(full_path):
                    if output_dir:
                        print('Copying [' + file_name + '] to [' + output_dir + ']')
                        shutil.copy2(full_path, output_dir)
                    else:
                        print(file_name)
                    break
                else:
                    if verbose:
                        print(
                            "WARNING [" + game + "]: candidate [" + file_name + "] not found, trying next one",
                            file=sys.stderr)
                    else:
                        print("WARNING: candidate [" + file_name + "] not found, trying next one", file=sys.stderr)
            else:
                print(file_name)
                break


def print_help():
    print('Usage: python3 generate.py [options] -d input_file.dat', file=sys.stderr)
    print('Options:', file=sys.stderr)
    print('\t-h,--help\tPrints this usage message', file=sys.stderr)
    print('\t-r,--regions=REGIONS\tA list of regions separated by commas. Ex.: -r USA,EUR,JPN', file=sys.stderr)
    print('\t-l,--languages=LANGUAGES\tA list of languages separated by commas. Ex.: -l en,es,ru', file=sys.stderr)
    print('\t-d,--dat=DAT_FILE\tThe DAT file to be used', file=sys.stderr)
    print('\t--no-bios\tFilter out BIOSes', file=sys.stderr)
    print('\t--no-proto\tFilter out prototype ROMs', file=sys.stderr)
    print('\t--no-unlicensed\tFilter out unlicensed ROMs', file=sys.stderr)
    print('\t--no-beta\tFilter out beta ROMs', file=sys.stderr)
    print('\t--no-demo\tFilter out demo ROMs', file=sys.stderr)
    print('\t--no-sample\tFilter out sample ROMs', file=sys.stderr)
    print('\t--no-all\tApply all filters above', file=sys.stderr)
    print('\t--all-regions\tIncludes files of unselected regions, if a selected one if not available', file=sys.stderr)
    print('\t--early-revisions\tROMs of earlier revisions will be prioritized', file=sys.stderr)
    print('\t--early-versions\tROMs of earlier versions will be prioritized', file=sys.stderr)
    print('\t--input-order\tROMs will be prioritized by the order they appear in the DAT file', file=sys.stderr)
    print('\t-e,--extension=EXTENSION\tROM names will use this extension. Ex.: -e zip', file=sys.stderr)
    print(
        '\t-b,--blacklist=WORDS\tROMs containing these strings will be avoided. Ex.: -b "Virtual Console,GameCube"',
        file=sys.stderr)
    print('\t-v,--verbose\tPrints more messages (useful when troubleshooting)',file=sys.stderr)
    print('\t-i,--input-dir=PATH\tProvides an input directory (i.e.: where your ROMs are)', file=sys.stderr)
    print('\t-o,--output-dir=PATH\tIf provided, ROMs will be copied to an an output directory', file=sys.stderr)


if __name__ == '__main__':
    main(sys.argv[1:])
