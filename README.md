### 1G1R ROM set generator

A small utility written in Python that uses No-Intro DATs to generate 1G1R ROM sets

#### Requirements

* Python 3 (tested with versions 3.6+, but probably works on earlier versions)
* That's it! This project has no external dependencies! :sunglasses:

#### Usage

For a comprehensive guide on how to use this tool, check out the [wiki page](https://github.com/andrebrait/1g1r-romset-generator/wiki) for this repository.

```
Usage: python3 generate.py [options] -d input_file.dat
Options:

# ROM selection and file manipulation:
        -r,--regions=REGIONS    A list of regions separated by commas. Ex.: -r USA,EUR,JPN
        -l,--languages=LANGS    An optional list of languages separated by commas. Ex.: -l en,es,ru
        -d,--dat=DAT_FILE       The DAT file to be used
        -i,--input-dir=PATH     Provides an input directory (i.e.: where your ROMs are)
        -e,--extension=EXT      ROM names will use this extension. Ex.: -e zip
        -o,--output-dir=PATH    If provided, ROMs will be copied to an output directory
        --move                  If set, ROMs will be moved, instead of copied, to the output directory

# Filtering:
        --no-bios               Filter out BIOSes
        --no-program            Filter out Programs and Test Programs
        --no-enhancement-chip   Filter out Ehancement Chips
        --no-proto              Filter out prototype ROMs
        --no-beta               Filter out beta ROMs
        --no-demo               Filter out demo ROMs
        --no-sample             Filter out sample ROMs
        --no-pirate             Filter out pirate ROMs
        --no-all                Apply all filters above (WILL STILL ALLOW UNLICENSED ROMs)
        --no-unlicensed         Filter out unlicensed ROMs
        --all-regions           Includes files of unselected regions, if a selected one if not available
        --all-regions-with-lang Same as --all-regions, but only if a ROM has at least one selected language

# Adjustment and customization:
        -w,--language-weight=N  The degree of priority the first selected languages receive over the latter ones. Default: 3
        --prioritize-languages  If set, ROMs matching more languages will be prioritized over ROMs matching regions
        --early-revisions       ROMs of earlier revisions will be prioritized
        --early-versions        ROMs of earlier versions will be prioritized
        --input-order           ROMs will be prioritized by the order they appear in the DAT file
        --prefer-parents        Parent ROMs will be prioritized over clones
        --prefer-prereleases    Prerelease (Beta, Proto, etc.) ROMs will be prioritized
        --avoid=WORDS           ROMs containing these words will be avoided (but not excluded). Ex.: --avoid "Virtual Console,GameCube"
        --exclude=WORDS         ROMs containing these words will be excluded. Ex.: --exclude "Virtual Console,GameCube"
        --ignore-case           If set, the avoid and exclude lists will be case-insensitive
        --regex                 If set, the avoid and exclude lists are used as regular expressions

# Help and debugging:
        -h,--help               Prints this usage message
        -v,--verbose            Prints more messages (useful when troubleshooting)
        --debug                 Prints even more messages (useful when troubleshooting)
```

#### Motivation

1. Parent/Clone XML DATs (the ones used to generate 1G1R ROM sets) sometimes lack data such as the *Region* or *Languages* of a game, even though the of data is often present in a ROM's name (thanks to No-Intro's naming convention).
2. Parent/Clone XML DATs often conflate retail versions of a game and its many _Prototype_, _Beta_, _Demo_ and _Sample_ versions in the same chain of parent and clone ROMs of a given game.
3. ClrMamePro, while an awesome tool, has a not-so-great way of picking ROMs based on the data provided by these DAT files:
    1. Its scoring system is capable of electing **one** best candidate for a ROM, and if you happen to not have that one candidate in your set, the game is not included in your resulting 1G1R set at all, even though you have alternatives to it.
    2. It has no concept of _pre-release_ and _retail_ ROMs.
    3. It has no concept of _revision_ or _versions_ of a game.
4. ClrMamePro is not the most cross-platform-friendly tool out there, and is often too complex for someone who just wants to generate a 1G1R ROM set from an existing ROM set.
5. Automated batch scripts are easy and practical, but inflexible. What if I prefer European ROMs over North-American ones? What if I prefer ROMs in Spanish? 

As fixing all these shortcomings would involve a lot of effort, I decided to:

1. Propose a new scoring system to achieve a better ROM selection for the 1G1R sets, relative to the scoring system used in popular ROM organization tools such as ClrMamePro.
2. Implement the scoring system in a small, cross-platform tool, able to work with a pre-existing ROM collection without requiring a full-fledged ROM organization tool.

#### Scoring strategy

The scoring system implemented here uses additional information provided by the 
DAT file and/or the ROM names (following the No-Intro naming convention) to 
better select the ROMs that should be part of the generated set, according to the user's preferences.

Sorting happens with the following criteria:
1. Good dumps
2. Released ROMs (unless `--prefer-prereleases` is used)
3. Non-blacklisted items
4. Best region match (this can be switched with item #5 by using `--prioritize-languages`)
5. Best language match (this can be switched with item #4 by using `--prioritize-languages`)
6. Parent ROMs (if `--prefer-parents` is used)
7. Input order (if `--input-order` is used)
8. Latest revision (unless `--early-revisions` is used)
9. Latest version (unless `--early-versions` is used)
10. Latest sample
11. Latest demo
12. Latest beta
13. Latest prototype
14. Most languages supported
15. Parent ROMs
