#!/bin/sh
set -e
cd "$(dirname "$0")"

ROMFS=game_extracted/content_0000_CTR-P-ATDJ/romfs

python3 scripts/msg.py -r story_msg.json packed_extracted/story/msg story_msg_repacked
python3 scripts/archive.py -r "$ROMFS/packed" "$ROMFS/packedlist" packed_extracted story_msg_repacked packed_translated packedlist_translated

echo "Done. Output: packed_translated, packedlist_translated"
