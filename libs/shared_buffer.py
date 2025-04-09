import numpy as np
from multiprocessing import shared_memory


class SharedFrameBuffer:

    def __init__(self, name, shape, dtype, create=False):
        self.name = name
        self.shape = shape
        self.dtype = dtype
        self.nbytes = np.prod(shape) * np.dtype(dtype).itemsize

        if create:
            self.shm = shared_memory.SharedMemory(create=True, size=self.nbytes)
            self.name = self.shm.name
        else:
            self.shm = shared_memory.SharedMemory(name=self.name)

        self.array = np.ndarray(self.shape, dtype=self.dtype, buffer=self.shm.buf)

    def close(self):
        self.shm.close()

    def unlink(self):
        self.shm.unlink()
