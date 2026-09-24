#!/bin/sh
set -e
cd "$(dirname "$0")"

ROMFS=game_extracted/content_0000_CTR-P-ATDJ/romfs

python3 scripts/unpack_cia.py game.cia game_extracted
python3 scripts/archive.py -x "$ROMFS/packed" "$ROMFS/packedlist" packed_extracted
python3 scripts/msg.py -d packed_extracted/story/msg story_msg.json

echo "Done."
