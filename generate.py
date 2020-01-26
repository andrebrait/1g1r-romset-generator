import getopt
import os
import re
import sys
from typing import Optional, Match, List, Dict

import datafile

NOT_PRERELEASE = "ZZZZZZZZZZ"
UNSELECTED_REGION = 1000
BLACKLISTED_ROM_BASE = 500
country_region_translation = [
    ('Australia', 'AUS'),
    ('Brazil', 'BRA'),
    ('Canada', 'CAN'),
    ('China', 'CHN'),
    ('Denmark', 'DAN'),
    ('France', 'FRA'),
    ('Finland', 'FYN'),
    ('Germany', 'GER'),
    ('Greece', 'GRE'),
    ('Hong Kong', 'CHN'),  # Needs checking
    ('Hong Kong', 'HON'),  # Needs checking
    ('Italy', 'ITA'),
    ('Japan', 'JPN'),
    ('Netherlands', 'HOL'),
    ('Korea', 'KOR'),
    ('Norway', 'NOR'),
    ('Russia', 'RUS'),
    ('Spain', 'SPA'),
    ('Sweden', 'SWE'),
    ('USA', 'USA'),
    ('Taiwan', 'TAI'),
    ('Asia', 'ASI'),
    ('Asia', 'JPN'),
    ('Europe', 'EUR'),
    ('World', 'EUR'),
    ('World', 'JPN'),
    ('World', 'USA')
]


class GameEntry:
    def __init__(
            self,
            is_bad: bool,
            region_index: int,
            input_index: int,
            revision: str,
            version: str,
            sample: str,
            demo: str,
            beta: str,
            proto: str,
            rom: datafile.rom):
        self.is_bad = is_bad
        self.region_index = region_index
        self.input_index = input_index
        self.revision = revision
        self.version = version
        self.sample = sample
        self.demo = demo
        self.beta = beta
        self.proto = proto
        self.rom = rom


beta_regex = re.compile('\\(Beta(?:\\s*([a-z0-9.]+))?\\)', re.IGNORECASE)
proto_regex = re.compile('\\(Proto(?:\\s*([a-z0-9.]+))?\\)', re.IGNORECASE)
sample_regex = re.compile('\\(Sample(?:\\s*([a-z0-9.]+))?\\)', re.IGNORECASE)
demo_regex = re.compile('\\(Demo(?:\\s*([a-z0-9.]+))?\\)', re.IGNORECASE)
rev_regex = re.compile('\\(Rev\\s*([a-z0-9.]+)\\)', re.IGNORECASE)
version_regex = re.compile('\\(v\\s*([a-z0-9.]+)?\\)', re.IGNORECASE)
sections_regex = re.compile('\\(([^()]+)\\)')


def parse_revision(name: str) -> str:
    rev_matcher = rev_regex.search(name)
    if rev_matcher:
        return rev_matcher.group(1)
    return '0'


def parse_version(name: str) -> str:
    version_matcher = version_regex.search(name)
    if version_matcher:
        return version_matcher.group(1)
    return '0'


def parse_regions(name: str) -> List[str]:
    parsed = []
    for section in sections_regex.finditer(name):
        elements = [element.strip() for element in section.group(1).split(',')]
        for element in elements:
            for country, region in country_region_translation:
                if country == element:
                    parsed.append(region)
    return parsed


def get_region_index(region: str, selected_regions: List[str]) -> int:
    try:
        return selected_regions.index(region)
    except ValueError:
        return UNSELECTED_REGION


def parse_prerelease(match: Optional[Match]) -> str:
    return match.group(1) if match else NOT_PRERELEASE


def parse_games(
        file: str,
        selected_regions: List[str],
        filter_bios: bool,
        filter_unlicensed: bool,
        filter_beta: bool,
        filter_demo: bool,
        filter_sample: bool,
        filter_proto: bool,
        all_regions: bool,
        blacklist: List[str],
        verbose: bool) -> Dict[str, List[GameEntry]]:
    games = {}
    root = datafile.parse(file, silence=True)
    for input_index in range(0, len(root.game)):
        game = root.game[input_index]
        parent_name = game.cloneof if game.cloneof else game.name
        beta_match = beta_regex.search(game.name)
        demo_match = demo_regex.search(game.name)
        sample_match = sample_regex.search(game.name)
        proto_match = proto_regex.search(game.name)
        if parent_name not in games:
            games[parent_name] = []
        if filter_bios and '[BIOS]' in game.name:
            continue
        if filter_unlicensed and '(Unl)' in game.name:
            continue
        if filter_beta and beta_match is not None:
            continue
        if filter_demo and demo_match is not None:
            continue
        if filter_sample and sample_match is not None:
            continue
        if filter_proto and proto_match is not None:
            continue
        is_bad = '[b]' in game.name
        beta = parse_prerelease(beta_match)
        demo = parse_prerelease(demo_match)
        sample = parse_prerelease(sample_match)
        proto = parse_prerelease(proto_match)
        revision = parse_revision(game.name)
        version = parse_version(game.name)
        region_indexes = []
        for release in game.release:
            region_index = get_region_index(release.region, selected_regions)
            if region_index not in region_indexes:
                region_indexes.append(region_index)
        for region in parse_regions(game.name):
            region_index = get_region_index(region, selected_regions)
            if region_index not in region_indexes:
                region_indexes.append(region_index)
        if not region_indexes:
            region_indexes.append(UNSELECTED_REGION)
        if blacklist:
            for string in blacklist:
                if string in game.name:
                    if verbose:
                        print(
                            'Penalizing candidate [' + game.name + ']. ' +
                            'Reason: contains blacklisted string [' + string + ']',
                            file=sys.stderr)
                    region_indexes = [BLACKLISTED_ROM_BASE + x for x in region_indexes]
                    break
        for rom in game.rom:
            for region_index in region_indexes:
                if all_regions or region_index < UNSELECTED_REGION:
                    games[parent_name].append(
                        GameEntry(
                            is_bad,
                            region_index,
                            input_index,
                            revision,
                            version,
                            sample,
                            demo,
                            beta,
                            proto,
                            rom))
    return games


def replace_extension(file_extension, file_name):
    try:
        return file_name[:file_name.rindex(os.extsep)] + os.extsep + file_extension
    except ValueError:
        return file_name + os.extsep + file_extension


def main(argv: List[str]):
    try:
        opts, args = getopt.getopt(argv, 'hd:r:e:i:b:v', [
            'help',
            'dat=',
            'regions=',
            'no-bios',
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
            'verbose'
        ])
    except getopt.GetoptError as e:
        print(e, file=sys.stderr)
        print_help()
        sys.exit(2)

    dat_file = None
    filter_bios = False
    filter_unlicensed = False
    filter_beta = False
    filter_demo = False
    filter_sample = False
    filter_proto = False
    all_regions = False
    revision_asc = False
    version_asc = False
    verbose = False
    index_multiplier = 0
    selected_regions = None
    file_extension = None
    input_dir = None
    blacklist = None
    for opt, arg in opts:
        if opt in ('-h', '--help'):
            print_help()
            sys.exit()
        if opt in ('-r', '--regions'):
            selected_regions = arg.split(',')
        filter_bios |= opt == '--no-bios' or opt == '--no-all'
        filter_unlicensed |= opt == '--no-unlicensed' or opt == '--no-all'
        filter_beta |= opt == '--no-beta' or opt == '--no-all'
        filter_demo |= opt == '--no-demo' or opt == '--no-all'
        filter_sample |= opt == '--no-sample' or opt == '--no-all'
        filter_proto |= opt == '--no-proto' or opt == '--no-all'
        all_regions |= opt == '--all-regions'
        revision_asc |= opt == '--early-revisions'
        version_asc |= opt == '--early-versions'
        verbose |= opt in ('-v', '--verbose')
        if opt in ('-d', '--dat'):
            dat_file = os.path.expanduser(arg)
            if not os.path.isfile(dat_file):
                print('invalid DAT file: ' + dat_file, file=sys.stderr)
                print_help()
                sys.exit(2)
        if opt in ('-e', '--extension'):
            file_extension = arg.lstrip(os.extsep)
        if opt == '--input-order':
            index_multiplier = 1
        if opt in ('-b', '--blacklist'):
            blacklist = arg.split(',')
        if opt in ('-i', '--input-dir'):
            input_dir = os.path.expanduser(arg)
            if not os.path.isdir(input_dir):
                print('invalid input directory: ' + input_dir, file=sys.stderr)
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
    if (revision_asc or version_asc) and index_multiplier > 0:
        print('early-revisions and early-versions are mutually exclusive with input-order', file=sys.stderr)
        print_help()
        sys.exit(2)

    games = parse_games(
        dat_file,
        selected_regions,
        filter_bios,
        filter_unlicensed,
        filter_beta,
        filter_demo,
        filter_sample,
        filter_proto,
        all_regions,
        blacklist,
        verbose)

    for key in games:
        game_entries = games[key]
        game_entries.sort(key=lambda x: len(x.rom.name))
        game_entries.sort(key=lambda x: (x.sample, x.demo, x.beta, x.proto), reverse=True)
        game_entries.sort(key=lambda x: x.version, reverse=not version_asc)
        game_entries.sort(key=lambda x: x.revision, reverse=not revision_asc)
        game_entries.sort(key=lambda x: (x.is_bad, x.region_index, index_multiplier * x.input_index))
        if verbose:
            print('Candidate order for [' + key + ']: ' + str([x.rom.name for x in game_entries]), file=sys.stderr)

    for game, entries in games.items():
        for entry in entries:
            file_name = entry.rom.name
            if file_extension:
                file_name = replace_extension(file_extension, file_name)
            if input_dir:
                full_path = os.path.join(input_dir, file_name)
                if os.path.isfile(full_path):
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
    print('Usage: python3 generate.py [options] input_file.dat', file=sys.stderr)
    print('Options:', file=sys.stderr)
    print('\t-h,--help\tPrints this usage message', file=sys.stderr)
    print('\t-r,--regions=REGIONS\tA list of regions separated by commas. Ex.: -r USA,EUR,JPN', file=sys.stderr)
    print('\t-d,--dat=DAT_FILE\tThe DAT file to be used', file=sys.stderr)
    print('\t--no-bios\tFilter out BIOSes', file=sys.stderr)
    print('\t--no-unlicensed\tFilter out unlicensed ROMs', file=sys.stderr)
    print('\t--no-beta\tFilter out beta ROMs', file=sys.stderr)
    print('\t--no-demo\tFilter out demo ROMs', file=sys.stderr)
    print('\t--no-sample\tFilter out sample ROMs', file=sys.stderr)
    print('\t--no-proto\tFilter out prototype ROMs', file=sys.stderr)
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


if __name__ == '__main__':
    main(sys.argv[1:])
