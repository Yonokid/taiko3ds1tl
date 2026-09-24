import sys, os, struct

RECORD_SIZE = 100
NAME_SIZE = RECORD_SIZE - 16
RECORDS_START = 228


def parse_packedlist(listdata: bytes):
    root_path = listdata[0:128]
    count, resv1, total_size, resv2, total_size2 = struct.unpack_from('<5I', listdata, 208)
    records = []
    for i in range(count):
        off = RECORDS_START + i * RECORD_SIZE
        rec = listdata[off:off + RECORD_SIZE]
        name = rec[:NAME_SIZE].split(b'\x00')[0].decode('latin1')
        offset, size, offset2, size2 = struct.unpack_from('<4I', rec, NAME_SIZE)
        records.append({'name': name, 'offset': offset, 'size': size})
    return root_path, records


def align128(x):
    return (x + 127) // 128 * 128


def extract(packed_path, packedlist_path, out_dir):
    os.makedirs(out_dir, exist_ok=True)

    with open(packedlist_path, 'rb') as f:
        listdata = f.read()
    with open(packed_path, 'rb') as f:
        packed = f.read()

    root_path, records = parse_packedlist(listdata)
    print(f"root_path={root_path.split(chr(0).encode())[0].decode('latin1')!r} "
          f"count={len(records)} (packed file is {len(packed)} bytes)")

    n_ok = 0
    n_dir = 0
    for rec in records:
        name = rec['name']
        if not name:
            continue

        dest = os.path.join(out_dir, name)
        if name.endswith('/'):
            os.makedirs(dest, exist_ok=True)
            n_dir += 1
            continue

        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, 'wb') as fo:
            fo.write(packed[rec['offset']:rec['offset'] + rec['size']])
        n_ok += 1

    print(f"extracted {n_ok} files, {n_dir} directories -> {out_dir}")


def repack(orig_packed_path, orig_packedlist_path, orig_tree_dir, override_dir, out_packed_path, out_packedlist_path):
    with open(orig_packedlist_path, 'rb') as f:
        listdata = f.read()
    with open(orig_packed_path, 'rb') as f:
        orig_packed = f.read()

    root_path, records = parse_packedlist(listdata)

    new_blob = bytearray()
    new_records = []

    for rec in records:
        name = rec['name']
        if name.endswith('/'):
            # directory marker: keep original offset/size fields verbatim (semantics unconfirmed)
            new_records.append({'name': name, 'offset': rec['offset'], 'size': rec['size']})
            continue

        # override_dir mirrors "story/msg/" subtree specifically (relative to that prefix)
        rel_for_override = name[len('story/msg/'):] if name.startswith('story/msg/') else name
        override_path = os.path.join(override_dir, rel_for_override)
        if os.path.isfile(override_path):
            data = open(override_path, 'rb').read()
        else:
            data = orig_packed[rec['offset']:rec['offset'] + rec['size']]

        cur = align128(len(new_blob))
        new_blob.extend(b'\x00' * (cur - len(new_blob)))
        new_offset = len(new_blob)
        new_blob.extend(data)
        new_records.append({'name': name, 'offset': new_offset, 'size': len(data)})

    # final padding: whole blob is aligned to 128 bytes, not just each file's start
    final = align128(len(new_blob))
    new_blob.extend(b'\x00' * (final - len(new_blob)))
    total_size = len(new_blob)

    # rebuild packedlist
    out = bytearray()
    out.extend(root_path)  # 128 bytes
    out.extend(b'\x00' * (208 - len(out)))
    out.extend(struct.pack('<5I', len(records), 0, total_size, 0, total_size))
    for rec in new_records:
        name_bytes = rec['name'].encode('latin1')
        if len(name_bytes) >= NAME_SIZE:
            raise ValueError(f"name too long: {rec['name']}")
        out.extend(name_bytes)
        out.extend(b'\x00' * (NAME_SIZE - len(name_bytes)))
        out.extend(struct.pack('<4I', rec['offset'], rec['size'], rec['offset'], rec['size']))

    with open(out_packed_path, 'wb') as f:
        f.write(new_blob)
    with open(out_packedlist_path, 'wb') as f:
        f.write(out)

    print(f"records={len(records)} blob_size={total_size} (orig {len(orig_packed)})")
    return bytes(new_blob), bytes(out)


if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] not in ('-x', '-r'):
        print(f"usage: {sys.argv[0]} -x <packed> <packedlist> <out_dir>", file=sys.stderr)
        print(f"       {sys.argv[0]} -r <orig_packed> <orig_packedlist> <orig_tree_dir> <override_dir> <out_packed> <out_packedlist>", file=sys.stderr)
        sys.exit(1)

    mode = sys.argv[1]
    if mode == '-x':
        packed_path, packedlist_path, out_dir = sys.argv[2:5]
        extract(packed_path, packedlist_path, out_dir)
    else:
        orig_packed, orig_packedlist, orig_tree, override_dir, out_packed, out_packedlist = sys.argv[2:8]
        repack(orig_packed, orig_packedlist, orig_tree, override_dir, out_packed, out_packedlist)
