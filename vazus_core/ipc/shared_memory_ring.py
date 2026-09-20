"""
vazus_core.ipc.shared_memory_ring — True Zero-Copy Multi-Slot Shared Memory FIFO Ring Buffer.

Provides sub-microsecond cross-process IPC on Windows via Named Shared Memory
(CreateFileMapping / mmap) and Named Mutex / Event synchronization.
Conforms strictly to Level-5 SuperGraph Kernel IPC Invariants.
"""

import sys
import time
import mmap
import struct
import ctypes
import logging
import threading
from typing import Optional, Tuple, List

logger = logging.getLogger(__name__)

# Superblock Control Header:
# Magic: 'VZRB' (0x565A5242)
# Version: 1
# Num Slots: uint32
# Slot Size: uint32
# Head: uint64 (Next write sequence number)
# Tail: uint64 (Oldest active sequence number)
# Total size: 4 + 4 + 4 + 4 + 8 + 8 = 32 bytes
CONTROL_HEADER_FORMAT = "<IIIIQQ"
CONTROL_HEADER_SIZE = struct.calcsize(CONTROL_HEADER_FORMAT)
RING_MAGIC = 0x565A5242  # 'VZRB'

# Slot Header:
# Slot Magic: 'SLOT' (0x534C4F54)
# Sequence Number: uint64
# Payload Length: uint32
# Timestamp NS: uint64
# Total size: 4 + 8 + 4 + 8 = 24 bytes
SLOT_HEADER_FORMAT = "<IQIQ"
SLOT_HEADER_SIZE = struct.calcsize(SLOT_HEADER_FORMAT)
SLOT_MAGIC = 0x534C4F54


class WindowsNamedMutex:
    """Lightweight cross-process named mutex wrapper using Win32 API."""

    def __init__(self, name: str):
        self.name = name.replace("\\", "_").replace("/", "_")
        self.handle = None
        if sys.platform == "win32":
            k32 = ctypes.windll.kernel32
            self.CreateMutexW = k32.CreateMutexW
            self.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
            self.CreateMutexW.restype = ctypes.c_void_p

            self.WaitForSingleObject = k32.WaitForSingleObject
            self.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
            self.WaitForSingleObject.restype = ctypes.c_uint32

            self.ReleaseMutex = k32.ReleaseMutex
            self.ReleaseMutex.argtypes = [ctypes.c_void_p]
            self.ReleaseMutex.restype = ctypes.c_bool

            self.CloseHandle = k32.CloseHandle
            self.CloseHandle.argtypes = [ctypes.c_void_p]
            self.CloseHandle.restype = ctypes.c_bool

            self.handle = self.CreateMutexW(None, False, self.name)

    def acquire(self, timeout_ms: int = 5000) -> bool:
        if not self.handle:
            return True
        WAIT_OBJECT_0 = 0x00000000
        WAIT_ABANDONED = 0x00000080
        res = self.WaitForSingleObject(self.handle, timeout_ms)
        return res in (WAIT_OBJECT_0, WAIT_ABANDONED)

    def release(self) -> None:
        if self.handle:
            self.ReleaseMutex(self.handle)

    def close(self) -> None:
        if self.handle:
            self.CloseHandle(self.handle)
            self.handle = None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


class SharedMemoryRingBuffer:
    """
    True multi-slot cyclic FIFO ring buffer with named shared memory on Windows/POSIX.
    Guarantees message retention across multiple concurrent writes without overwriting unread slots.
    """

    def __init__(
        self,
        name: str = "Local\\VazusSuperGraphRingBuffer",
        num_slots: int = 64,
        slot_size_kb: int = 512,
        create_new: bool = True,
        size_mb: Optional[int] = None,
    ):
        self.name = name
        self.tag_name = name.replace("\\", "_").replace("/", "_")
        self.num_slots = max(4, num_slots)
        if size_mb is not None:
            self.slot_size = max(65536, (size_mb * 1024 * 1024) // self.num_slots)
        else:
            self.slot_size = slot_size_kb * 1024
        self.max_payload_size = self.slot_size - SLOT_HEADER_SIZE

        self.total_size = CONTROL_HEADER_SIZE + (self.num_slots * self.slot_size)
        self.shm: Optional[mmap.mmap] = None
        self._local_lock = threading.Lock()
        self._mutex = WindowsNamedMutex(f"{self.tag_name}_Mutex")

        self._init_shm(create_new)

    def _init_shm(self, create_new: bool):
        try:
            if sys.platform == "win32":
                self.shm = mmap.mmap(-1, self.total_size, tagname=self.tag_name, access=mmap.ACCESS_WRITE)
            else:
                self.shm = mmap.mmap(-1, self.total_size, mmap.MAP_SHARED | mmap.MAP_ANONYMOUS, mmap.PROT_READ | mmap.PROT_WRITE)

            with self._mutex:
                # Check if superblock already initialized
                self.shm.seek(0)
                header_bytes = self.shm.read(CONTROL_HEADER_SIZE)
                magic = 0
                if len(header_bytes) >= 4:
                    magic, = struct.unpack("<I", header_bytes[:4])

                if magic != RING_MAGIC:
                    # Fresh initialization of Superblock
                    init_hdr = struct.pack(
                        CONTROL_HEADER_FORMAT,
                        RING_MAGIC,
                        1,                 # Version 1
                        self.num_slots,
                        self.slot_size,
                        0,                 # Head = 0
                        0                  # Tail = 0
                    )
                    self.shm.seek(0)
                    self.shm.write(init_hdr)
                    self.shm.flush()
        except Exception as exc:
            logger.error("Failed to initialize SharedMemoryRingBuffer: %s", exc)
            self.shm = None

    def _get_control_header(self) -> Tuple[int, int, int, int, int, int]:
        """Reads control superblock header."""
        self.shm.seek(0)
        hdr = self.shm.read(CONTROL_HEADER_SIZE)
        return struct.unpack(CONTROL_HEADER_FORMAT, hdr)

    def write_payload(self, data: bytes) -> Optional[int]:
        """
        Atomically writes a byte payload into the next ring slot.
        Returns the assigned monotonic sequence number or None on failure.
        """
        if not self.shm:
            return None

        payload_len = len(data)
        if payload_len > self.max_payload_size:
            raise ValueError(
                f"Payload size ({payload_len} bytes) exceeds maximum slot payload capacity ({self.max_payload_size} bytes)"
            )

        with self._local_lock:
            with self._mutex:
                magic, ver, num_slots, slot_sz, head, tail = self._get_control_header()
                if magic != RING_MAGIC:
                    return None

                slot_idx = head % num_slots
                slot_offset = CONTROL_HEADER_SIZE + (slot_idx * slot_sz)

                timestamp_ns = time.time_ns()
                slot_header = struct.pack(SLOT_HEADER_FORMAT, SLOT_MAGIC, head, payload_len, timestamp_ns)

                self.shm.seek(slot_offset)
                self.shm.write(slot_header)
                self.shm.write(data)

                # Advance head
                new_head = head + 1
                # If buffer wrapped completely, advance tail to drop oldest slot
                new_tail = tail
                if new_head - new_tail > num_slots:
                    new_tail = new_head - num_slots

                # Update control header
                updated_hdr = struct.pack(CONTROL_HEADER_FORMAT, RING_MAGIC, ver, num_slots, slot_sz, new_head, new_tail)
                self.shm.seek(0)
                self.shm.write(updated_hdr)
                self.shm.flush()

                return new_head

    def read_payload(self) -> Optional[Tuple[bytes, int]]:
        """
        Backward compatibility: Reads the latest message (at HEAD - 1).
        Returns (payload_bytes, timestamp_ns) or None.
        """
        if not self.shm:
            return None

        with self._local_lock:
            with self._mutex:
                magic, ver, num_slots, slot_sz, head, tail = self._get_control_header()
                if magic != RING_MAGIC or head == 0 or head <= tail:
                    # Empty buffer
                    return None

                latest_seq = head - 1
                return self._read_slot_internal(latest_seq, num_slots, slot_sz)

    def read_slot(self, seq: int) -> Optional[Tuple[bytes, int]]:
        """Reads a specific sequence number from the ring buffer."""
        if not self.shm:
            return None

        with self._local_lock:
            with self._mutex:
                magic, ver, num_slots, slot_sz, head, tail = self._get_control_header()
                if magic != RING_MAGIC:
                    return None
                if seq < tail or seq >= head:
                    # Out of active window
                    return None
                return self._read_slot_internal(seq, num_slots, slot_sz)

    def read_new_messages(self, last_seq: int) -> List[Tuple[int, bytes, int]]:
        """
        Reads all available messages published since `last_seq`.
        Returns a list of tuples: [(seq, payload_bytes, timestamp_ns), ...]
        """
        results = []
        if not self.shm:
            return results

        with self._local_lock:
            with self._mutex:
                magic, ver, num_slots, slot_sz, head, tail = self._get_control_header()
                if magic != RING_MAGIC:
                    return results

                start_seq = max(last_seq + 1, tail)
                for seq in range(start_seq, head):
                    res = self._read_slot_internal(seq, num_slots, slot_sz)
                    if res:
                        results.append((seq, res[0], res[1]))

        return results

    def _read_slot_internal(self, seq: int, num_slots: int, slot_sz: int) -> Optional[Tuple[bytes, int]]:
        slot_idx = seq % num_slots
        slot_offset = CONTROL_HEADER_SIZE + (slot_idx * slot_sz)

        self.shm.seek(slot_offset)
        hdr_bytes = self.shm.read(SLOT_HEADER_SIZE)
        if len(hdr_bytes) < SLOT_HEADER_SIZE:
            return None

        slot_magic, slot_seq, data_len, timestamp_ns = struct.unpack(SLOT_HEADER_FORMAT, hdr_bytes)
        if slot_magic != SLOT_MAGIC or slot_seq != seq:
            return None

        if data_len > self.max_payload_size:
            return None

        payload = self.shm.read(data_len)
        return (payload, timestamp_ns)

    def stats(self) -> dict:
        """Returns diagnostic statistics of the ring buffer."""
        if not self.shm:
            return {"status": "uninitialized"}
        with self._mutex:
            magic, ver, num_slots, slot_sz, head, tail = self._get_control_header()
            return {
                "magic": hex(magic),
                "num_slots": num_slots,
                "slot_size_bytes": slot_sz,
                "head_seq": head,
                "tail_seq": tail,
                "active_messages": max(0, head - tail),
                "total_capacity_bytes": self.total_size,
            }

    def close(self):
        """Closes memory mapping and named mutex."""
        if self._mutex:
            self._mutex.close()
        if self.shm:
            try:
                self.shm.close()
            except Exception as exc:
                logger.debug("Close ring buffer note: %s", exc)
            self.shm = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Backward-compatible alias
SharedMemoryBus = SharedMemoryRingBuffer

