### 1G1R ROM set generator

A small python utility that uses NO-INTRO DATs to generate 1G1R sets

```
Usage: python3 generate.py [options] input_file.dat
Options:
        -h,--help       Prints this usage message
        -r,--regions=REGIONS    A list of regions separated by commas. Ex.: -r USA,EUR,JPN
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
        -i,--input-dir=PATH     Provides an input directory (i.e.: where your ROMs are)
```
