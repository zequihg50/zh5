from zh5.dataset import Dataset
from zh5.heap import GlobalHeapCollection


class VirtualDataset(Dataset):
    def __init__(self, file, do, name=None, dataspace=None, layout=None):
        super().__init__(file, do, name, dataspace)
        self._layout = layout

        self._f.seek(self._layout.properties_offset)
        byts = self._f.read(self._f.size_of_offsets + 4)
        self._address = int.from_bytes(byts[:-4], "little")  # address of the global heap collection where the VDS mapping entries are stored
        self._index = int.from_bytes(byts[-4:], "little")  # index of the data object within the global heap collection

        self._heap = GlobalHeapCollection(self._f, self._address)

    @property
    def address(self):
        return self._address

    @property
    def index(self):
        return self._index
