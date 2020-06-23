import re

from modules.classes import RegionData

__version__ = "2.0.0-SNAPSHOT"

GITHUB_URL = "https://github.com/andrebrait/1g1r-romset-generator"

COUNTRY_REGION_CORRELATION = [
    # Language needs checking
    RegionData("ASI", re.compile(r"(Asia)", re.I), ["zh"]),
    RegionData("ARG", re.compile(r"(Argentina)", re.I), ["es"]),
    RegionData("AUS", re.compile(r"(Australia)", re.I), ["en"]),
    RegionData("BRA", re.compile(r"(Brazil)", re.I), ["pt"]),
    # Language needs checking
    RegionData("CAN", re.compile(r"(Canada)", re.I), ["en", "fr"]),
    RegionData("CHN", re.compile(r"((China)|(Hong Kong))", re.I), ["zh"]),
    RegionData("DAN", re.compile(r"(Denmark)", re.I), ["da"]),
    RegionData("EUR", re.compile(r"((Europe)|(World))", re.I), ["en"]),
    RegionData("FRA", re.compile(r"(France)", re.I), ["fr"]),
    RegionData("FYN", re.compile(r"(Finland)", re.I), ["fi"]),
    RegionData("GER", re.compile(r"(Germany)", re.I), ["de"]),
    RegionData("GRE", re.compile(r"(Greece)", re.I), ["el"]),
    RegionData("ITA", re.compile(r"(Italy)", re.I), ["it"]),
    RegionData("JPN", re.compile(r"((Japan)|(World))", re.I), ["ja"]),
    RegionData("HOL", re.compile(r"(Netherlands)", re.I), ["nl"]),
    RegionData("KOR", re.compile(r"(Korea)", re.I), ["ko"]),
    RegionData("MEX", re.compile(r"(Mexico)", re.I), ["es"]),
    RegionData("NOR", re.compile(r"(Norway)", re.I), ["no"]),
    RegionData("RUS", re.compile(r"(Russia)", re.I), ["ru"]),
    RegionData("SPA", re.compile(r"(Spain)", re.I), ["es"]),
    RegionData("SWE", re.compile(r"(Sweden)", re.I), ["sv"]),
    RegionData("USA", re.compile(r"((USA)|(World))", re.I), ["en"]),
    # Language needs checking
    RegionData("TAI", re.compile(r"(Taiwan)", re.I), ["zh"])
]

SECTIONS_REGEX = re.compile(r"\(([^()]+)\)")
BIOS_REGEX = re.compile(re.escape("[BIOS]"), re.I)
PROGRAM_REGEX = re.compile(r"\((?:Test\s*)?Program\)", re.I)
ENHANCEMENT_CHIP_REGEX = re.compile(r"\(Enhancement\s*Chip\)", re.I)
UNL_REGEX = re.compile(re.escape("(Unl)"), re.I)
PIRATE_REGEX = re.compile(re.escape("(Pirate)"), re.I)
PROMO_REGEX = re.compile(re.escape("(Promo)"), re.I)
BETA_REGEX = re.compile(r"\(Beta(?:\s*([a-z0-9.]+))?\)", re.I)
PROTO_REGEX = re.compile(r"\(Proto(?:\s*([a-z0-9.]+))?\)", re.I)
SAMPLE_REGEX = re.compile(r"\(Sample(?:\s*([a-z0-9.]+))?\)", re.I)
DEMO_REGEX = re.compile(r"\(Demo(?:\s*([a-z0-9.]+))?\)", re.I)
REV_REGEX = re.compile(r"\(Rev\s*([a-z0-9.]+)\)", re.I)
VERSION_REGEX = re.compile(r"\(v\s*([a-z0-9.]+)\)", re.I)
LANGUAGES_REGEX = re.compile(r"\(([a-z]{2}(?:[,+][a-z]{2})*)\)", re.I)
BAD_REGEX = re.compile(re.escape("[b]"), re.I)
ZIP_REGEX = re.compile(r"\.zip$", re.I)
