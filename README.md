### 1G1R ROM set generator

A small utility written in Python that uses No-Intro DATs to generate 1G1R ROM sets

#### Requirements

* Python 3 (tested with versions 3.6+, but probably works on earlier versions)
* That's it! This project has no external dependencies! :sunglasses:

#### Usage

For a comprehensive guide on how to use this tool, check out the 
[wiki page](https://github.com/andrebrait/1g1r-romset-generator/wiki) for this repository.

```
Usage: python3 generate.py [options] -d input_file.dat
Options:

# ROM selection and file manipulation:
        -r,--regions=REGIONS    A list of regions separated by commas
                                Ex.: -r USA,EUR,JPN
        -l,--languages=LANGS    An optional list of languages separated by commas
                                This is a secondary prioritization criteria, not a filter
                                Ex.: -l en,es,ru
        -d,--dat=DAT_FILE       The DAT file to be used
                                Ex.: -d snes.dat
        -i,--input-dir=PATH     Provides an input directory (i.e.: where your ROMs are)
                                Ex.: -i "C:\Users\John\Downloads\Emulators\SNES\ROMs"
        -o,--output-dir=PATH    If provided, ROMs will be copied to an output directory
                                Ex.: -o "C:\Users\John\Downloads\Emulators\SNES\ROMs\1G1R"
        --move                  If set, ROMs will be moved, instead of copied, to the output directory
        --symlink               If set, ROMs will be symlinked (soft linked) to the output directory
                                Please note newer versions of Windows 10 require elevated privileges to create symlinks
        --group-by-first-letter If set, groups ROMs on the output directory in subfolders according to the first letter in their name

# File scanning:
        --header-file=PATH      Sets the header file to be used when scanning headered ROMs
                                You can also just add the file to the headers directory
        --threads=THREADS       Sets the number of I/O threads to be used to read files
                                Default: 4
        --chunk-size=BYTES      Sets the chunk size for buffered I/O operations (bytes)
                                Default: 33554432 (32 MiB)
        --max-file-size=BYTES   Sets the maximum file size for header information processing (bytes)
                                Default: 268435456 (256 MiB)
        --no-scan               If set, ROMs are not scanned and only file names are used to identify candidates
        -e,--extension=EXT      When not scanning, ROM file names will use this extension
                                Ex.: -e zip

# Filtering:
        --no-bios               Filter out BIOSes
        --no-program            Filter out Programs and Test Programs
        --no-enhancement-chip   Filter out Ehancement Chips
        --no-proto              Filter out prototype ROMs
        --no-beta               Filter out beta ROMs
        --no-demo               Filter out demo ROMs
        --no-sample             Filter out sample ROMs
        --no-pirate             Filter out pirate ROMs
        --no-promo              Filter out promotion ROMs
        --no-all                Apply all filters above (WILL STILL ALLOW UNLICENSED ROMs)
        --no-unlicensed         Filter out unlicensed ROMs
        --all-regions           Includes files of unselected regions, if a selected one is not available
        --all-regions-with-lang Same as --all-regions, but only if a ROM has at least one selected language
        --only-selected-lang    Filter out ROMs without any selected languages

# Adjustment and customization:
        -w,--language-weight=N  The degree of priority the first selected languages receive over the latter ones
                                Default: 3
        --prioritize-languages  If set, ROMs matching more languages will be prioritized over ROMs matching regions
        --early-revisions       ROMs of earlier revisions will be prioritized
        --early-versions        ROMs of earlier versions will be prioritized
        --input-order           ROMs will be prioritized by the order they appear in the DAT file
        --prefer-parents        Parent ROMs will be prioritized over clones
        --prefer-prereleases    Prerelease (Beta, Proto, etc.) ROMs will be prioritized
        --prefer=WORDS          ROMs containing these words will be preferred
                                Ex.: --prefer "Virtual Console,GameCube"
                                Ex.: --prefer "file:prefer.txt" 
        --avoid=WORDS           ROMs containing these words will be avoided (but not excluded).
                                Ex.: --avoid "Virtual Console,GameCube"
                                Ex.: --avoid "file:avoid.txt" 
        --exclude=WORDS         ROMs containing these words will be excluded.
                                Ex.: --exclude "Virtual Console,GameCube"
                                Ex.: --exclude "file:exclude.txt"
        --exclude-after=WORDS   If the best candidate contains these words, skip all candidates.
                                Ex.: --exclude-after "Virtual Console,GameCube"
                                Ex.: --exclude-after "file:exclude-after.txt"
        --ignore-case           If set, the avoid and exclude lists will be case-insensitive
        --regex                 If set, the avoid and exclude lists are used as regular expressions
        --separator=SEP         Provides a separator for the avoid, exclude & exclude-after options.
                                Default: ","

# Help and debugging:
        -h,--help               Prints this usage message
        -v,--version            Prints the version
        -V,--verbose            Logs more messages (useful when troubleshooting)
        --debug                 Logs even more messages (useful when troubleshooting)
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
3. Non-avoided items (if `--avoid` is used)
4. Best region match (this can be switched with item #5 by using `--prioritize-languages`)
5. Best language match (this can be switched with item #4 by using `--prioritize-languages`)
6. Parent ROMs (if `--prefer-parents` is used)
7. Input order (if `--input-order` is used)
8. Preferred items (if `--prefer` is used)
9. Latest revision (unless `--early-revisions` is used)
10. Latest version (unless `--early-versions` is used)
11. Latest sample
12. Latest demo
13. Latest beta
14. Latest prototype
15. Most languages supported
16. Parent ROMs