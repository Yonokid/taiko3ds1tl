# Taiko3DS1TL

Tools for extracting, translating, and repacking Taiko 3DS1 story scripts

# GUI

A GUI is available:
1. install uv
2. run `uv run scripts/edit_gui.py`

## Scripts

| Script | Purpose |
|---|---|
| `scripts/unpack_cia.py` | Extract exefs/romfs/exheader from a `.cia` |
| `scripts/archive.py` | Extract (`-x`) / rebuild (`-r`) the `packed`/`packedlist` archive |
| `scripts/msg.py` | Dump (`-d`) / repack (`-r`) Huffman-compressed `.msb` dialogue files to/from JSON |
| `scripts/huff.py` | Standalone Huffman compress (`-c`) / decompress (`-d`) for a single file; also imported by `msg.py` |
