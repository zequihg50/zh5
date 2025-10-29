class BtreeV1:
    def __init__(self, file, offset):
        self._f = file
        self._o = offset

        self._f.seek(self._o)
        byts = self._f.read(8 + self._f.size_of_offsets * 2)
        assert byts[:4] == b"TREE"
        self._node_type = byts[4]  # 0 group, 1 dataset
        self._node_level = byts[5]  # 0 is root of the tree
        self._entries_used = int.from_bytes(byts[6:8], "little")
        self._entries_offset = file.tell()
        self._address_left_sibling = int.from_bytes(byts[8:8 + self._f.size_of_offsets], "little")
        self._address_right_sibling = int.from_bytes(
            byts[8 + self._f.size_of_offsets:8 + 2 * self._f.size_of_offsets], "little")

        # N entries = B-tree contains N child pointers and N+1 keys.
        # Each tree has 2K + 1 keys with 2K child pointers interleaved between
        # the keys.The number of keys and child pointers actually containing
        # valid values is determined by the node’s Entries Used field.If that
        # field is N, then the B-tree contains N child pointers and N+1 keys.
        n = self._entries_used + self._entries_used + 1
        bytsl = (
                self._entries_used * self._f.size_of_offsets +  # child entries
                self._entries_used * 24  # 1-4, 4-8, 1dim+64bit
        )
        byts = file.read(bytsl)
        # esto es donde está el chunk en bytes en el fichero
        # el tamanio se saca de la key
        # 24 es el tamanio de la primera key, de donde sale? 8+8*2, for type1 nodes
        # print(int.from_bytes(byts[24:24 + self._fh.size_of_offsets], "little"))

    @property
    def keysize(self):
        raise NotImplementedError

    @property
    def level(self):
        return self._node_level

    @property
    def type(self):
        return self._node_type

    @property
    def sibling_left(self):
        return self._address_left_sibling if self._address_left_sibling != self._f.undefined_address else None

    @property
    def sibling_right(self):
        return self._address_right_sibling if self._address_right_sibling != self._f.undefined_address else None

    def children(self):
        self._f.seek(self._entries_offset)
        for i in range(self._entries_used):
            self._f.read(self.keysize)  # read the key
            byts = self._f.read(self._f.size_of_offsets)  # read the child pointer


class BtreeV1Chunk(BtreeV1):
    def __init__(self, file, offset, dataset):
        super(BtreeV1Chunk, self).__init__(file, offset)
        self._dataset = dataset

    @property
    def keysize(self):
        return 8 + 8 * (self._dataset.ndim + 1)

    def inspect_nodes(self):
        keysize = self.keysize
        for i in range(self._entries_used):
            offset = self._entries_offset + ((keysize + self._f.size_of_offsets) * i)
            self._f.seek(offset)
            kbyts = self._f.read(keysize)  # read the key
            byts = self._f.read(self._f.size_of_offsets)  # read the child pointer

            yield {
                "level": self._node_level,
                "entry": i,
                "offset": offset,
                "dataset": self._dataset.name,
            }

            if self.level != 0:
                child = BtreeV1Chunk(self._f, int.from_bytes(byts, "little"), self._dataset)
                yield from child.inspect_nodes()

    def inspect_chunks(self):
        keysize = self.keysize
        for i in range(self._entries_used):
            offset = self._entries_offset + ((keysize + self._f.size_of_offsets) * i)
            self._f.seek(offset)
            kbyts = self._f.read(keysize)  # read the key
            byts = self._f.read(self._f.size_of_offsets)  # read the child pointer

            chunk_offset_list = []
            for j in range(self._dataset.ndim):
                frm = 8 + 8 * j
                to = frm + 8
                chunk_offset_list.append(int.from_bytes(kbyts[frm:to], "little"))

            if self.level != 0:
                child = BtreeV1Chunk(self._f, int.from_bytes(byts, "little"), self._dataset)
                yield from child.inspect_chunks()
            else:
                d = {"offset": int.from_bytes(byts, "little"),
                     "length": int.from_bytes(kbyts[:4], "little"),
                     "filter_mask": kbyts[4:8],
                     "chunk_offset": tuple(chunk_offset_list),
                     "type": "chunk",
                     "object": self._dataset.name}
                yield d


class BtreeV1Group(BtreeV1):
    def __init__(self, file, offset, group):
        super().__init__(file, offset)
        self._group = group

    @property
    def keysize(self):
        return self._f.size_of_lengths

    def symbol_table_entries(self):
        keysize = self.keysize
        for i in range(self._entries_used):
            offset = self._entries_offset + self._f.size_of_offsets + ((keysize + self._f.size_of_offsets) * i)
            self._f.seek(offset)
            byts = self._f.read(self._f.size_of_offsets)  # read the child pointer
            kbyts = self._f.read(keysize)  # read the key

            if self.level != 0:
                child = BtreeV1Group(self._f, int.from_bytes(byts, "little"), self._group)
                yield from child.symbol_table_entries()
            else:
                entry = {}
                entry["offset"] = int.from_bytes(kbyts, "little")
                entry["snod"] = int.from_bytes(byts, "little")
                yield entry


class BtreeV2Record:
    @property
    def size(self):
        raise NotImplementedError()


# Non-filtered Dataset Chunks
class BtreeV2RecordLayout10:
    def __init__(self, file, offset, ndim):
        self._f = file
        self._o = offset
        self._ndim = ndim

        self._f.seek(self._o)
        self._address = self._f.read(self._f.size_of_offsets)
        self._scaled_offset_address = self._o + self._f.size_of_offsets

    @property
    def size(self):
        return self._f.size_of_offsets + self._ndim * 8

    @property
    def address(self):
        return self._address

    @property
    def scaled_offset(self):
        scaled_offset = []

        self._f.seek(self._scaled_offset_address)
        for i in range(self._ndim):
            scaled_offset.append(
                int.from_bytes(self._f.read(8), "little"))

        return tuple(scaled_offset)


# Filtered Dataset Chunks
class BtreeV2RecordLayout11:
    pass


class BtreeV2:
    def __init__(self, file, offset, dataset=None):
        self._f = file
        self._o = offset
        self._f.seek(offset)
        self._dataset = dataset

        byts = self._f.read(22 + self._f.size_of_offsets + self._f.size_of_lengths)
        assert byts[:4] == b"BTHD"

        self._version = byts[4]
        self._type = byts[5]
        self._node_size = int.from_bytes(byts[6:10], "little")
        self._record_size = int.from_bytes(byts[10:12], "little")
        self._depth = int.from_bytes(byts[12:14], "little")
        self._split_percent = byts[14]
        self._merge_percent = byts[15]
        self._root_node_address = int.from_bytes(byts[16:16 + self._f.size_of_offsets], "little")
        self._number_of_records_in_root_node = int.from_bytes(
            byts[16 + self._f.size_of_offsets:16 + 2 + self._f.size_of_offsets], "little")
        pos = 16 + 2 + self._f.size_of_offsets
        self._total_number_of_records_in_btree = int.from_bytes(byts[pos:pos + self._f.size_of_lengths], "little")
        pos += self._f.size_of_lengths
        self._checksum = byts[-4:]

        if self._depth == 0:
            self._root_node = BtreeV2LeafNode(self._f, self._root_node_address, self)
        else:
            self._root_node = BtreeV2InternalNode(self._f, self._root_node_address, self)

    @property
    def type(self):
        return self._type

    @property
    def record_size(self):
        return self._record_size

    @property
    def nrecords(self):
        return self._number_of_records_in_root_node

    @property
    def node_size(self):
        return self._node_size

    @property
    def dataset(self):
        return self._dataset

    def records(self):
        yield from self._root_node.records()

    @property
    def btree_type(self):
        # 0 	This B-tree is used for testing only. This value should not be used for storing records in actual HDF5 files.
        # 1 	This B-tree is used for indexing indirectly accessed, non-filtered ‘huge’ fractal heap objects.
        # 2 	This B-tree is used for indexing indirectly accessed, filtered ‘huge’ fractal heap objects.
        # 3 	This B-tree is used for indexing directly accessed, non-filtered ‘huge’ fractal heap objects.
        # 4 	This B-tree is used for indexing directly accessed, filtered ‘huge’ fractal heap objects.
        # 5 	This B-tree is used for indexing the ‘name’ field for links in indexed groups.
        # 6 	This B-tree is used for indexing the ‘creation order’ field for links in indexed groups.
        # 7 	This B-tree is used for indexing shared object header messages.
        # 8 	This B-tree is used for indexing the ‘name’ field for indexed attributes.
        # 9 	This B-tree is used for indexing the ‘creation order’ field for indexed attributes.
        # 10 	This B-tree is used for indexing chunks of datasets with no filters and with more than one dimension of unlimited extent.
        # 11 	This B-tree is used for indexing chunks of datasets with filters and more than one dimension of unlimited extent.
        return self._type

    def parse_record(self):  # de momento retorno dict, ya veré como hacer esto
        # esto lo hice en 2024, ha llegado 2025 y tengo que hacer esto para chunks
        d = {}
        if self._type == 6:
            byts = self._f.read(self.record_size)
            d["creation_order"] = int.from_bytes(byts[:8], "little")
            d["heap_id"] = byts[8:]

        return d

    # i have to rethink this to see if it is correct
    def inspect_chunks(self):
        yield from self._root_node.inspect_chunks(self._number_of_records_in_root_node, self._depth)


class BtreeV2LeafNode:
    def __init__(self, file, offset, tree):
        self._f = file
        self._o = offset
        self._tree = tree

        self._f.seek(self._o)
        byts = self._f.read(6)
        assert byts[:4] == b"BTLF"
        self._version = byts[4]
        self._type = byts[5]
        assert self._type == self._tree.type

        # maybe need to review this, in this example the root node is a leaf node
        # might be different if internal nodes are present
        # From HDF5 spec: size of this field is determined by the number of records
        # for this node and the record size (from the header). The format of records
        # depends on the type of B-tree.
        self._record_offset = self._f.tell()
        self._record_size = self._tree.record_size
        self._records_size = self._tree.record_size * self._tree.nrecords

        self._f.seek(self._record_offset + self._records_size)
        self._checksum = self._f.read(4)

    @property
    def record_size(self):
        return self._record_size

    def records(self):
        for i in range(self._tree.nrecords):
            self._f.seek(self._record_offset + self.record_size * i)
            record = self._tree.parse_record()
            # pos = self._f.tell()
            yield record
            # self._f.seek(pos)

    def inspect_chunks(self, nnodes, depth):
        if depth != 0:
            raise ValueError("Depth must be 0 for a BTLF.")

        self._f.seek(self._record_offset)
        for i in range(nnodes):
            byts = self._f.read(self._tree.record_size)
            # this is type 10 only
            chunk_addr = int.from_bytes(byts[:8], "little")

            chunk_offset_list = []
            for j in range(self._tree.dataset.ndim):
                frm = 8 + 8 * j
                to = frm + 8
                chunk_offset_list.append(int.from_bytes(byts[frm:to], "little"))

            d = {"offset": chunk_addr,
                 "length": 4 * 10 * 10,  # sacar del dataset porque es tipo 10 (unfiltered chunk, 10x10 i4)
                 "filter_mask": b"\x00" * 4,
                 "chunk_offset": tuple(chunk_offset_list),
                 "type": "chunk",
                 "object": self._tree.dataset.name}

            yield d


class BtreeV2InternalNode:
    def __init__(self, file, offset, tree):
        self._f = file
        self._o = offset
        self._tree = tree
        self._signature = b"BTIN"

        # records_size = self._tree.record_size  * self._tree.nrecords
        records_size = self._tree.record_size * self._tree.nrecords
        self._f.seek(offset)
        byts = self._f.read(6 + records_size)
        assert byts[:4] == self._signature
        self._version = byts[4]
        self._type = byts[5]
        self._child_node_pointers_offset = self._o + 6 + records_size

    def inspect_chunks(self, nnodes, depth):
        self._f.seek(self._child_node_pointers_offset)
        for i in range(nnodes):
            child_node_pointer = int.from_bytes(self._f.read(self._f.size_of_offsets), "little")
            number_of_records_child_node = int.from_bytes(self._f.read(1), "little")
            if depth > 1:
                total_number_of_records_child_node = int.from_bytes(self._f.read(1), "little")

            self._f.seek(child_node_pointer)
            child_node_signature = self._f.read(4)
            if child_node_signature == b"BTIN":
                node = BtreeV2InternalNode(self._f, child_node_pointer, self._tree)
            elif child_node_signature == b"BTLF":
                node = BtreeV2LeafNode(self._f, child_node_pointer, self._tree)
            else:
                raise ValueError("Invalid signature.")

            yield from node.inspect_chunks(number_of_records_child_node, depth - 1)


class BtreeV2Chunk:
    def __init__(self, file, offset, tree):
        self._f = file
        self._o = offset
        self._tree = tree

    # https://github.com/HDFGroup/hdf5/blob/e5f526b62d3ca81ee281a68626beb5c3edd8dcc3/src/H5B2.c#L509
    def inspect_chunks(self, nodes=None):
        yield from self._tree.inspect_chunks()
