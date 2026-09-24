import heapq
from itertools import count


class Node:
    __slots__ = ('freq', 'value', 'left', 'right')

    def __init__(self, freq, value=None, left=None, right=None):
        self.freq = freq
        self.value = value
        self.left = left
        self.right = right

    @property
    def is_leaf(self):
        return self.left is None and self.right is None


def build_tree(payload: bytes) -> Node:
    freqs = {}
    for b in payload:
        freqs[b] = freqs.get(b, 0) + 1
    if not freqs:
        freqs[0] = 1

    tie = count()
    heap = [(f, next(tie), Node(f, value=v)) for v, f in freqs.items()]
    heapq.heapify(heap)

    if len(heap) == 1:
        # need at least a 1-bit decision; duplicate the sole symbol into both children
        f, _, only = heap[0]
        return Node(f, left=Node(f, value=only.value), right=Node(f, value=only.value))

    while len(heap) > 1:
        f1, _, n1 = heapq.heappop(heap)
        f2, _, n2 = heapq.heappop(heap)
        merged = Node(f1 + f2, left=n1, right=n2)
        heapq.heappush(heap, (merged.freq, next(tie), merged))

    return heap[0][2]


def build_codes(root: Node):
    codes = {}

    def walk(node, bits):
        if node.is_leaf:
            codes[node.value] = bits or '0'
            return
        walk(node.left, bits + '0')
        walk(node.right, bits + '1')

    walk(root, '')
    return codes


def serialize_tree(root: Node) -> bytes:
    """Lay out the tree using the same child-pair addressing the decoder expects:
    child0/child1 of the node at relative address A live at
    ((A & ~1) + offset*2 + 2, +1). BFS allocation keeps addresses increasing."""
    table = bytearray([0, 0])  # index 0 = size-byte slot (filled later), index 1 = root
    queue = [(1, root)]
    qi = 0
    while qi < len(queue):
        idx, node = queue[qi]
        qi += 1
        if node.is_leaf:
            table[idx] = node.value
            continue
        base = len(table)
        aligned = idx & ~1
        offset = (base - aligned - 2) // 2
        if not (0 <= offset <= 0x3F):
            raise ValueError(f"tree too large/unbalanced for 6-bit offset (offset={offset})")
        flag0 = 0x80 if node.left.is_leaf else 0
        flag1 = 0x40 if node.right.is_leaf else 0
        table[idx] = offset | flag0 | flag1
        table.extend([0, 0])
        queue.append((base, node.left))
        queue.append((base + 1, node.right))

    if len(table) % 2:
        table.append(0)
    tree_size = len(table)  # includes index-0 slot
    size_byte = tree_size // 2 - 1
    if not (0 <= size_byte <= 0xFF):
        raise ValueError("tree too large for 8-bit size byte")
    table[0] = size_byte
    return bytes(table)


def pack_bits(bitstring: str) -> bytes:
    # pad to multiple of 32 bits
    pad = (-len(bitstring)) % 32
    bitstring += '0' * pad
    out = bytearray()
    for i in range(0, len(bitstring), 32):
        word_bits = bitstring[i:i + 32]
        word = int(word_bits, 2)
        out += word.to_bytes(4, 'little')
    return bytes(out)


def huff_compress(payload: bytes) -> bytes:
    decompressed_size = len(payload)
    if decompressed_size > 0xFFFFFF:
        raise ValueError("payload too large for 24-bit size field")

    root = build_tree(payload)
    codes = build_codes(root)
    tree_bytes = serialize_tree(root)

    bitstring = ''.join(codes[b] for b in payload)
    bitstream = pack_bits(bitstring)

    header = bytes([0x28]) + decompressed_size.to_bytes(3, 'little')
    return header + tree_bytes + bitstream


def huff_decompress(data: bytes) -> bytes:
    header = int.from_bytes(data[0:4], 'little')
    comp_type = (header >> 4) & 0xF
    data_size_bits = header & 0xF
    decompressed_size = header >> 8
    if comp_type != 2:
        raise ValueError(f"not huffman (type nibble={comp_type:#x})")

    tree_size_byte = data[4]
    tree_size = (tree_size_byte + 1) * 2
    bitstream_start = 4 + tree_size

    # addresses are relative to tree_base = position of the "tree size" byte
    # itself (data offset 4); the root node lives at relative address 1.
    tree_base = 4

    def get_child_addr(node_addr, node_val):
        offset = node_val & 0x3F
        base = (node_addr & ~1) + offset * 2 + 2
        return base, base + 1

    out = bytearray()
    root_addr = 1
    root_val = data[tree_base + root_addr]

    # bitstream: sequence of 32-bit LE words, bits consumed MSB first
    word_pos = bitstream_start
    cur_word = 0
    bits_left = 0

    def next_bit():
        nonlocal word_pos, cur_word, bits_left
        if bits_left == 0:
            cur_word = int.from_bytes(data[word_pos:word_pos+4], 'little')
            word_pos += 4
            bits_left = 32
        bit = (cur_word >> 31) & 1
        cur_word = (cur_word << 1) & 0xFFFFFFFF
        bits_left -= 1
        return bit

    out_units = 0
    total_units = decompressed_size if data_size_bits == 8 else decompressed_size * 2

    node_addr = root_addr
    node_val = root_val
    cur_byte = 0
    nibble_state = 0  # for 4-bit mode

    while out_units < total_units:
        # start traversal from root each symbol
        node_addr = root_addr
        node_val = data[tree_base + node_addr]
        while True:
            bit = next_bit()
            child0, child1 = get_child_addr(node_addr, node_val)
            if bit == 0:
                next_addr = child0
                is_leaf = bool(node_val & 0x80)
            else:
                next_addr = child1
                is_leaf = bool(node_val & 0x40)
            node_addr = next_addr
            node_val = data[tree_base + node_addr]
            if is_leaf:
                break
        symbol = node_val
        if data_size_bits == 8:
            out.append(symbol)
            out_units += 1
        else:
            # 4-bit nibble packing into output bytes, low nibble first
            if nibble_state == 0:
                cur_byte = symbol & 0xF
                nibble_state = 1
            else:
                cur_byte |= (symbol & 0xF) << 4
                out.append(cur_byte)
                nibble_state = 0
            out_units += 1

    return bytes(out[:decompressed_size])


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 3 or sys.argv[1] not in ('-c', '-d'):
        print(f"usage: {sys.argv[0]} -c|-d <in> [out]", file=sys.stderr)
        sys.exit(1)

    mode, p = sys.argv[1], sys.argv[2]
    payload = open(p, 'rb').read()

    if mode == '-c':
        comp = huff_compress(payload)
        check = huff_decompress(comp)
        assert check == payload, "round-trip mismatch"
        print(f"{len(payload)} bytes -> compressed {len(comp)} bytes, round-trip OK")
        if len(sys.argv) > 3:
            open(sys.argv[3], 'wb').write(comp)
    else:
        dec = huff_decompress(payload)
        print(f"input {len(payload)} bytes -> output {len(dec)} bytes")
        print(dec[:200])
        if len(sys.argv) > 3:
            open(sys.argv[3], 'wb').write(dec)
