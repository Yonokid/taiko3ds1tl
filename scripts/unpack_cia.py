import os
import sys

from pyctr.type.cia import CIAReader

cia_path = sys.argv[1]
out_dir = sys.argv[2]
os.makedirs(out_dir, exist_ok=True)

reader = CIAReader(cia_path)
print("Title ID:", reader.tmd.title_id)

def dump_romfs_tree(romfs, node, cur_out, cur_path):
    for child in node.get('contents', {}).values():
        name = child['name']
        if child.get('type') == 'dir' or 'contents' in child:
            sub_out = os.path.join(cur_out, name)
            os.makedirs(sub_out, exist_ok=True)
            dump_romfs_tree(romfs, child, sub_out, f"{cur_path}{name}/")
        else:
            fpath = f"{cur_path}{name}"
            with romfs.open(fpath) as fsrc, open(os.path.join(cur_out, name), 'wb') as fdst:
                fdst.write(fsrc.read())

for idx, ncch in reader.contents.items():
    print(f"\n== content {idx} == product_code={ncch.product_code} program_id={ncch.program_id}")
    content_out = os.path.join(out_dir, f"content_{idx:04}_{ncch.product_code or 'nodata'}")
    os.makedirs(content_out, exist_ok=True)

    if ncch.exefs is not None:
        exefs_out = os.path.join(content_out, "exefs")
        os.makedirs(exefs_out, exist_ok=True)
        for name, entry in ncch.exefs.entries.items():
            try:
                with ncch.exefs.open(name) as f:
                    data = f.read()
                with open(os.path.join(exefs_out, name), 'wb') as fo:
                    fo.write(data)
                print(f"  exefs: {name} ({entry.size} bytes)")
            except Exception as e:  # noqa: BLE001
                print(f"  exefs: {name} FAILED: {e}")

    if ncch.romfs is not None:
        romfs_out = os.path.join(content_out, "romfs")
        os.makedirs(romfs_out, exist_ok=True)
        try:
            dump_romfs_tree(ncch.romfs, ncch.romfs._tree_root, romfs_out, "/")
            print(f"  romfs extracted -> {romfs_out} (total {ncch.romfs.total_size} bytes)")
        except Exception as e:  # noqa: BLE001
            print(f"  romfs FAILED: {e}")

    if ncch.check_for_extheader():
        try:
            with ncch.open_raw_section('exheader') as f:
                data = f.read()
            with open(os.path.join(content_out, 'exheader.bin'), 'wb') as fo:
                fo.write(data)
            print(f"  exheader dumped ({len(data)} bytes)")
        except Exception as e:  # noqa: BLE001
            print(f"  exheader FAILED: {e}")

print("\nDone.")
