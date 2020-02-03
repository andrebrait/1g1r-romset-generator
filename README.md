### 1G1R ROM set generator

A small python utility that uses No-Intro DATs to generate 1G1R sets

```
Usage: python3 generate.py [options] -d input_file.dat
Options:
        -h,--help       Prints this usage message
        -r,--regions=REGIONS    A list of regions separated by commas. Ex.: -r USA,EUR,JPN
        -d,--dat=DAT_FILE       The DAT file to be used
        --no-bios       Filter out BIOSes
        --no-unlicensed Filter out unlicensed ROMs
        --no-beta       Filter out beta ROMs
        --no-demo       Filter out demo ROMs
        --no-sample     Filter out sample ROMs
        --no-proto      Filter out prototype ROMs
        --no-all        Apply all filters above
        --all-regions   Includes files of unselected regions, if a selected one if not available
        --early-revisions       ROMs of earlier revisions will be prioritized
        --early-versions        ROMs of earlier versions will be prioritized
        --input-order   ROMs will be prioritized by the order they appear in the DAT file
        -e,--extension=EXTENSION        ROM names will use this extension. Ex.: -e zip
        -b,--blacklist=WORDS    ROMs containing these strings will be avoided. Ex.: -b "Virtual Console,GameCube"
        -v,--verbose    Prints more messages (useful when troubleshooting)
        -i,--input-dir=PATH     Provides an input directory (i.e.: where your ROMs are)
        -o,--output-dir=PATH    If provided, ROMs will be copied to an an output directory
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

If a user selects the regions 'USA,EUR' and languages 'en,es', the generated set will contain:

1. Non-prerelease ROMs for 'USA' *and* language 'en';
2. Non-prerelease ROMs for 'USA' *and* language 'es';
3. Non-prerelease ROMs for 'EUR' *and* language 'en';
4. Non-prerelease ROMs for 'EUR' *and* language 'es';
5. Sample ROMs for 'USA' *and* language 'en';
6. Sample ROMs for 'USA' *and* language 'es';
7. Sample ROMs for 'EUR' *and* language 'en';
8. Sample ROMs for 'EUR' *and* language 'es';
9. Demo ROMs for 'USA' *and* language 'en';
10. Demo ROMs for 'USA' *and* language 'es';
11. Demo ROMs for 'EUR' *and* language 'en';
12. Demo ROMs for 'EUR' *and* language 'es';
13. Beta ROMs for 'USA' *and* language 'en';
14. Beta ROMs for 'USA' *and* language 'es';
15. Beta ROMs for 'EUR' *and* language 'en';
16. Beta ROMs for 'EUR' *and* language 'es';
17. Proto ROMs for 'USA' *and* language 'en';
18. Proto ROMs for 'USA' *and* language 'es';
19. Proto ROMs for 'EUR' *and* language 'en';
20. Proto ROMs for 'EUR' *and* language 'es';