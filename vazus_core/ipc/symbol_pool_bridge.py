import ctypes
import os
import threading
from typing import Dict, List, Optional

FNV_PRIME = 0x100000001B3
FNV_OFFSET = 0xCBF29CE484222325


def fnv1a_64(text: str) -> int:
    h = FNV_OFFSET
    for b in text.encode("utf-8"):
        h = ((h ^ b) * FNV_PRIME) & 0xFFFFFFFFFFFFFFFF
    return h


class SymbolPoolBridge:
    """
    Bidirectional symbol interning pool connecting to services/gomcp Go backend
    with 64-bit FNV-1a high-speed in-memory fallback.
    """

    def __init__(self, dll_path: Optional[str] = None):
        self._lock = threading.RLock()
        self._table: Dict[str, int] = {}
        self._strings: List[str] = []
        self._hash_map: Dict[int, str] = {}
        self._dll = None

        target_dll = dll_path or os.path.join(r"C:\vazus\services\gomcp\bin", "symbol_pool.dll")
        if os.path.exists(target_dll):
            try:
                self._dll = ctypes.CDLL(target_dll)
            except Exception:
                self._dll = None

    def intern(self, symbol: str) -> int:
        """Inserts or looks up the string, returning its canonical SymbolID in O(1)."""
        with self._lock:
            if symbol in self._table:
                return self._table[symbol]

            sym_id = len(self._strings)
            self._table[symbol] = sym_id
            self._strings.append(symbol)

            h64 = fnv1a_64(symbol)
            self._hash_map[h64] = symbol
            return sym_id

    def resolve(self, symbol_id: int) -> Optional[str]:
        """Looks up canonical string for a SymbolID."""
        with self._lock:
            if 0 <= symbol_id < len(self._strings):
                return self._strings[symbol_id]
            return None

    def hash_symbol(self, symbol: str) -> int:
        """Computes 64-bit FNV-1a hash and interns symbol."""
        self.intern(symbol)
        return fnv1a_64(symbol)

    def resolve_hash(self, hash_val: int) -> Optional[str]:
        """Resolves string from 64-bit FNV-1a hash."""
        with self._lock:
            return self._hash_map.get(hash_val)

    def batch_intern(self, symbols: List[str]) -> List[int]:
        """Interns a batch of symbols, returning list of SymbolIDs."""
        with self._lock:
            return [self.intern(s) for s in symbols]

    def size(self) -> int:
        """Returns count of unique interned symbols."""
        with self._lock:
            return len(self._strings)

    def clear(self) -> None:
        """Clears symbol pool."""
        with self._lock:
            self._table.clear()
            self._strings.clear()
            self._hash_map.clear()
