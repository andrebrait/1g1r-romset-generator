import getopt
import re
import sys

import datafile

UNSELECTED_REGION = 9999
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
    ('World', 'USA'),
    ('World', 'JPN')
]


beta_regex = re.compile('\\(Beta(?:\\s*[0-9]+)?\\)', re.IGNORECASE)
proto_regex = re.compile('\\(Proto(?:\\s*[0-9]+)?\\)', re.IGNORECASE)
sample_regex = re.compile('\\(Sample(?:\\s*[0-9]+)?\\)', re.IGNORECASE)
demo_regex = re.compile('\\(Demo(?:\\s*[0-9]+)?\\)', re.IGNORECASE)
rev_regex = re.compile('\\(Rev\\s*([0-9]+)\\)', re.IGNORECASE)
version_regex = re.compile('\\(v\\s*([0-9]+(?:\\.[0-9]+))?\\)', re.IGNORECASE)
sections_regex = re.compile('\\(([^()]+)\\)')


def parse_revision(name):
    rev_matcher = rev_regex.search(name)
    if rev_matcher:
        return int(rev_matcher.group(1))
    else:
        return 0


def parse_version(name):
    version_matcher = version_regex.search(name)
    if version_matcher:
        return float(version_matcher.group(1))
    else:
        return 0


def parse_regions(name):
    parsed = []
    for section in sections_regex.finditer(name):
        elements = [element.strip() for element in section.group(1).split(',')]
        for element in elements:
            for country, region in country_region_translation:
                if country == element:
                    parsed.append(region)
    return parsed


def get_region_index(region, selected_regions):
    try:
        return selected_regions.index(region)
    except ValueError:
        return UNSELECTED_REGION


def parse_games(
        file,
        selected_regions,
        filter_bios,
        filter_unlicensed,
        filter_beta,
        filter_demo,
        filter_sample,
        filter_proto,
        all_regions):
    games = {}
    root = datafile.parse(file, silence=True)
    for game in root.game:
        parent_name = game.cloneof if game.cloneof else game.name
        if parent_name not in games:
            games[parent_name] = []
        if filter_bios and '[BIOS]' in game.name:
            continue
        if filter_unlicensed and '(Unl)' in game.name:
            continue
        if filter_beta and beta_regex.search(game.name) is not None:
            continue
        if filter_demo and demo_regex.search(game.name) is not None:
            continue
        if filter_sample and sample_regex.search(game.name) is not None:
            continue
        if filter_proto and proto_regex.search(game.name) is not None:
            continue
        revision = parse_revision(game.name)
        version = parse_version(game.name)
        region_indexes = []
        if game.release:
            for release in game.release:
                region_indexes.append(get_region_index(release.region, selected_regions))
        else:
            region_indexes.append(UNSELECTED_REGION)
        for region in parse_regions(game.name):
            region_index = get_region_index(region, selected_regions)
            if region_index not in region_indexes:
                region_indexes.append(region_index)
        for rom in game.rom:
            for region_index in region_indexes:
                if all_regions or region_index < UNSELECTED_REGION:
                    games[parent_name].append((region_index, revision, version, rom))
    return games


def main(argv):
    try:
        opts, args = getopt.getopt(argv, 'hr:', [
            'help',
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
            'early-versions'
        ])
    except getopt.GetoptError as e:
        print(e, file=sys.stderr)
        print_help()
        sys.exit(2)

    filter_bios = False
    filter_unlicensed = False
    filter_beta = False
    filter_demo = False
    filter_sample = False
    filter_proto = False
    all_regions = False
    rev_multiplier = -1
    version_multiplier = -1
    selected_regions = None
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
        if opt == '--early-revisions':
            rev_multiplier = 1
        if opt == '--early-versions':
            version_multiplier = 1
    if not selected_regions:
        print_help()
        exit(2)

    games = parse_games(
        args[0],
        selected_regions,
        filter_bios,
        filter_unlicensed,
        filter_beta,
        filter_demo,
        filter_sample,
        filter_proto,
        all_regions)

    for game in games:
        games[game].sort(key=lambda x: (x[0], rev_multiplier * x[1], version_multiplier * x[2]))

    for game, entries in games.items():
        if entries:
            print(entries[0][3].name)


def print_help():
    print('Usage: python3 generate.py [options] input_file.dat', file=sys.stderr)
    print('Options:', file=sys.stderr)
    print('\t-r,--regions=REGIONS\tA list of regions separated by commas. Ex.: -r USA,EUR,JPN', file=sys.stderr)
    print('\t--no-bios\tFilter out BIOSes', file=sys.stderr)
    print('\t--no-unlicensed\tFilter out unlicensed ROMs', file=sys.stderr)
    print('\t--no-beta\tFilter out beta ROMs', file=sys.stderr)
    print('\t--no-demo\tFilter out demo ROMs', file=sys.stderr)
    print('\t--no-sample\tFilter out sample ROMs', file=sys.stderr)
    print('\t--no-proto\tFilter out prototype ROMs', file=sys.stderr)
    print('\t--no-all\tApply all filters above', file=sys.stderr)
    print('\t--all-regions\tIncludes files of unselected regions, if a selected one if not available', file=sys.stderr)
    print('\t--early-revisions\tIf present, ROMs of earlier revisions will be prioritized', file=sys.stderr)
    print('\t--early-versions\tIf present, ROMs of earlier versions will be prioritized', file=sys.stderr)


if __name__ == '__main__':
    main(sys.argv[1:])
