import zh5
from zh5.dataset import Dataset
from zh5.heap import GlobalHeapCollection


class VirtualDatasetEntry:
    def __init__(self, file, pos):
        self._file = file
        self._pos = pos

        self._file.seek(self._pos)


class VdsMapping:
    def read(self, item):
        raise NotImplementedError()


class SingleSourceSingleVirtualMapping(VdsMapping):
    def __init__(self, vds, source_file, source_dataset):
        self._vds = vds
        self._source_file = source_file
        self._source_dataset = source_dataset

    # item is the selection, for single source single virtual it is unused
    def read(self, item):
        f = zh5.File(self._source_file)
        d = f[self._source_dataset]
        arr = d[item]
        f.close()

        return arr


class HyperMapping(VdsMapping):
    def __init__(self, vds):
        pass

    def read(self, item):
        pass


class VirtualDataset(Dataset):
    def __init__(self, file, do, name=None, dataspace=None, layout=None):
        super().__init__(file, do, name, dataspace)
        self._layout = layout
        self._mapping = None

        self._heap = GlobalHeapCollection(self._f, self._layout.address)
        self._references()

    def _references(self):
        o = self._heap[self._layout.index - 1]
        version = o.data[0]
        num_entries = int.from_bytes(o.data[1:1 + self._f.size_of_lengths], "little")
        byts = o.data[1 + self._f.size_of_lengths:]
        print(byts)

        if num_entries == 1:
            # let's see if this is a single mapping single virtual
            frm, to = 0, 0
            while byts[to] != 0:
                to += 1
            source_fname = byts[frm:to].decode("ascii")

            frm = to + 1
            to = frm
            while byts[to] != 0:
                to += 1
            source_dname = byts[frm:to].decode("ascii")

            frm = to + 1
            to = frm + 4
            source_selection_type = int.from_bytes(byts[frm:to], "little")
            if source_selection_type == 3:
                frm = to
                to = frm + 12
                source_selection_info = byts[frm:to]
                source_selection_info_version = int.from_bytes(source_selection_info[:4], "little")
                source_selection_info_reserved = int.from_bytes(source_selection_info[4:], "little")
                if source_selection_info_version != 1:
                    raise ValueError(
                        f"Invalid source selection version (required 1, found {source_selection_info_version}")
                if source_selection_info_reserved != 0:
                    raise ValueError(
                        f"Invalid source selection bytes (required 0, found {source_selection_info_reserved}")

                frm = to
                to = frm + 4
                virtual_selection_type = int.from_bytes(byts[frm:to], "little")
                if virtual_selection_type == 3:
                    frm = to
                    to = frm + 12
                    virtual_selection_info = byts[frm:to]
                    virtual_selection_info_version = int.from_bytes(virtual_selection_info[:4], "little")
                    virtual_selection_info_reserved = int.from_bytes(virtual_selection_info[4:], "little")

                    if virtual_selection_info_version != 1:
                        raise ValueError(
                            f"Invalid source selection version (required 1, found {source_selection_info_version}")
                    if virtual_selection_info_reserved != 0:
                        raise ValueError(
                            f"Invalid source selection bytes (required 0, found {source_selection_info_reserved}")

                    self._mapping = SingleSourceSingleVirtualMapping(self, source_fname, source_dname)

        # not single source single virtual, more complicated mapping
        # if num_entries == 1 and source_selection_type ==

        # # move this to the different vds mappings?
        # for i in range(num_entries):
        #     frm, to = 0, 0
        #     while byts[to] != 0:
        #         to += 1
        #     vds_fname = byts[frm:to].decode("ascii")
        #     frm = to + 1
        #     to = frm
        #     while byts[to] != 0:
        #         to += 1
        #     vds_dname = byts[frm:to].decode("ascii")
        #
        #     # now it begins the two source and virtual selection dataspaces
        #     # 0 H5S_SEL_NONE: Nothing selected
        #     # 1 H5S_SEL_POINTS: Sequence of points selected
        #     # 2 H5S_SEL_HYPER: Hyperslab selected
        #     # 3 H5S_SEL_ALL: Entire extent selected
        #     source_selection_type = int.from_bytes(byts[null_indices[i + 1] + 1:null_indices[i + 1] + 1 + 4], "little")
        #
        #     # frm = null_indices[i + 1] + 5  # after file and dataset names and the 4 bytes of the selection_type
        #     # print(selection_type, frm, byts[:frm], byts, flush=True)
        #     if source_selection_type == 0:
        #         pass
        #     elif source_selection_type == 1:
        #         pass
        #     elif source_selection_type == 2:
        #         version = int.from_bytes(byts[frm:frm + 4], "little")
        #         if version == 1:  # for dataspace without H5S_UNLIMITED
        #             # 4 bytes reserved
        #             length = int.from_bytes(byts[frm + 4 + 4:frm + 4 + 4 + 4], "little")
        #             rank = int.from_bytes(byts[frm + 12:frm + 16], "little")
        #             num_blocks = int.from_bytes(byts[frm + 16:frm + 20], "little")
        #
        #             print(self.name, length, rank, num_blocks)
        #             starts, ends = [], []
        #             starts_byts = byts[frm + 20:frm + 20 + 8 * num_blocks]
        #             ends_byts = byts[frm + 20 + 8 * num_blocks:frm + 20 + 8 * 2 * num_blocks]
        #             for j in range(num_blocks):
        #                 starts.append(int.from_bytes(starts_byts[j * 8:(j + 1) * 8], "little"))
        #                 ends.append(int.from_bytes(ends_byts[j * 8:(j + 1) * 8], "little"))
        #             print(starts, ends)
        #         elif version == 2:  # for dataspace with H5S_UNLIMITED
        #             start = int.from_bytes(byts[frm + 20:frm + 28], "little")
        #             stride = int.from_bytes(byts[frm + 28:frm + 36], "little")
        #             count = int.from_bytes(byts[frm + 36:frm + 44], "little")
        #             block = int.from_bytes(byts[frm + 44:frm + 52], "little")
        #         else:
        #             raise ValueError(f"Unknown version of virtual hyperslab selection.")
        #
        #         # print(self.name, i, version, length, rank, num_blocks, start, stride, count, block)
        #     elif source_selection_type == 3:
        #         # H5S_SEL_ALL: 4 bytes of version + 8 bytes of zeros (12 bytes)
        #         # there are two selection info: source and virtual
        #         source_selection_info = byts[frm:frm + 12]
        #         virtual_selection_info = byts[frm + 12:frm + 24]
        #         source_version = source_selection_info[0]
        #         virtual_version = virtual_selection_info[0]
        #         print(self.name, source_version, virtual_version)
        #     else:
        #         raise ValueError("Unknown selection type.")

    def __getitem__(self, item):
        return self._mapping.read(item)
