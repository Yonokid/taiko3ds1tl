import sys, os, glob, json
sys.path.insert(0, os.path.dirname(__file__))
from huff import huff_compress, huff_decompress


def dump(src_dir, out_path):
    result = {}
    for p in sorted(glob.glob(os.path.join(src_dir, '**', '*.msb'), recursive=True)):
        rel = os.path.relpath(p, src_dir)
        data = open(p, 'rb').read()
        dec = huff_decompress(data)

        if os.path.basename(p) == 'MSG_Info.msb':
            result[rel] = {'type': 'info_table', 'raw_hex': dec.hex()}
            continue

        control_id = dec[0]
        text = dec[1:-1].decode('utf-8', errors='replace') if dec[-1:] == b'\x00' else dec[1:].decode('utf-8', errors='replace')
        result[rel] = {'type': 'dialogue', 'control_id': control_id, 'text': text}

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"wrote {len(result)} entries -> {out_path}")


def repack(json_path, src_dir, out_dir):
    with open(json_path, encoding='utf-8') as f:
        entries = json.load(f)

    n_translated = 0
    n_unchanged = 0

    for rel, entry in entries.items():
        dst = os.path.join(out_dir, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)

        if entry['type'] == 'info_table':
            # not translated, not re-derived here -> copy original bytes through unchanged
            src = os.path.join(src_dir, rel)
            with open(src, 'rb') as f:
                raw = f.read()
            with open(dst, 'wb') as f:
                f.write(raw)
            n_unchanged += 1
            continue

        text_en = entry.get('text_en')
        if text_en is None:
            src = os.path.join(src_dir, rel)
            with open(src, 'rb') as f:
                raw = f.read()
            with open(dst, 'wb') as f:
                f.write(raw)
            n_unchanged += 1
            continue

        control_id = entry['control_id']
        payload = bytes([control_id]) + text_en.encode('utf-8') + b'\x00'
        comp = huff_compress(payload)
        # sanity check before writing
        assert huff_decompress(comp) == payload
        with open(dst, 'wb') as f:
            f.write(comp)
        n_translated += 1

    print(f"translated={n_translated} unchanged(copied)={n_unchanged} -> {out_dir}")


if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] not in ('-d', '-r'):
        print(f"usage: {sys.argv[0]} -d <src_dir> <out.json>", file=sys.stderr)
        print(f"       {sys.argv[0]} -r <json_path> <src_dir> <out_dir>", file=sys.stderr)
        sys.exit(1)

    mode = sys.argv[1]
    if mode == '-d':
        src_dir, out_path = sys.argv[2:4]
        dump(src_dir, out_path)
    else:
        json_path, src_dir, out_dir = sys.argv[2:5]
        repack(json_path, src_dir, out_dir)
