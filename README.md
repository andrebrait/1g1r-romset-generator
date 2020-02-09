### 1G1R ROM set generator

A small Python utility that uses No-Intro DATs to generate 1G1R sets

#### Requirements

* Python 3 (tested with versions 3.6+, but probably works on earlier versions)
* The `six` Python compatibility library
  * `apt install python3-six` will do, in most Debian-based Linux distributions
  * `pip3 install six` is an alternative

#### Usage

```
Usage: python3 generate.py [options] -d input_file.dat
Options:
        -h,--help       Prints this usage message
        -r,--regions=REGIONS    A list of regions separated by commas. Ex.: -r USA,EUR,JPN
        -l,--languages=LANGUAGES        A list of languages separated by commas. Ex.: -l en,es,ru
        -d,--dat=DAT_FILE       The DAT file to be used
        --no-bios       Filter out BIOSes
        --no-program    Filter out Programs and Test Programs
        --no-proto      Filter out prototype ROMs
        --no-unlicensed Filter out unlicensed ROMs
        --no-beta       Filter out beta ROMs
        --no-demo       Filter out demo ROMs
        --no-sample     Filter out sample ROMs
        --no-all        Apply all filters above
        --all-regions   Includes files of unselected regions, if a selected one if not available
        --all-regions-with-lang Same as --all-regions, but only if a ROM has at least one selected language
        --prioritize-languages  If set, ROMs matching languages will be prioritized over ROMs matching regions
        --early-revisions       ROMs of earlier revisions will be prioritized
        --early-versions        ROMs of earlier versions will be prioritized
        --input-order   ROMs will be prioritized by the order they appear in the DAT file
        --prefer-parents        Parent ROMs will be prioritized over clones
        --prefer-prereleases    Prerelease (Beta, Proto, etc.) ROMs will be prioritized
        -e,--extension=EXTENSION        ROM names will use this extension. Ex.: -e zip
        -b,--blacklist=WORDS    ROMs containing these words will be avoided. Ex.: -b "Virtual Console,GameCube"
        --ignore-case   If set, the blacklist will be case-insensitive 
        -i,--input-dir=PATH     Provides an input directory (i.e.: where your ROMs are)
        -o,--output-dir=PATH    If provided, ROMs will be copied to an output directory
        --move  If set, ROMs will be moved, intead of copied, to the output directory
        -v,--verbose    Prints more messages (useful when troubleshooting)
        --debug Prints even more messages (useful when troubleshooting)
```

#### Goals

* Propose a new scoring system to achieve a better ROM selection for the 1G1R sets, 
relative to the scoring system used in popular ROM organization tools
* Implement the scoring system in a small, cross-platform tool, able to work with a 
pre-existing ROM collection without requiring a full-fledged ROM organization tool

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
