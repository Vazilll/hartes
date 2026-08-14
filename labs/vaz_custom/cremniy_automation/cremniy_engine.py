"""
vazus.labs.cremniy_automation.cremniy_engine — Cremniy C++ Core Engine & 768D Vector Space.

Implements Requirement R1:
1. FileDataBuffer: Thread-safe (RLock), 64KB chunk LRU caching, dirty overlay map, transactional undo/redo stack, SHA-256 integrity.
2. ModuleManager: Thread-safe singleton registry mapping category string groups to ModuleDescription factories.
3. DisassemblerEngine: Structured disassembly dataclasses with radare2/rizin execution and robust fallback heuristics.
4. HexEditorWrapper: Visual document model wrapping FileDataBuffer with range metadata, styles, and hex formatting.
5. CremniySuperGraphExtractor: Indexes sections, functions, and hex buffers into kg_nodes/kg_edges (cremniy_disasm domain) with 768D embeddings in vazus.db.
"""

import os
import sys
import json
import sqlite3
import hashlib
import threading
import subprocess
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Any, Optional, Union, Callable

VAZUS_DIR = Path("C:/vazus")
if str(VAZUS_DIR) not in sys.path:
    sys.path.insert(0, str(VAZUS_DIR))

try:
    from vazus_core.embeddings import UnifiedEmbeddingManager
    from vazus_core.supergraph_linker import DEFAULT_DB_PATH, calculate_cosine_similarity
except ImportError:
    UnifiedEmbeddingManager = None
    DEFAULT_DB_PATH = Path("C:/vazus/services/memory/vazus.db")
    if not DEFAULT_DB_PATH.exists():
        DEFAULT_DB_PATH = Path("C:/vazus/vazus.db")
    
    def calculate_cosine_similarity(vec_a, vec_b):
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        na = sum(a * a for a in vec_a) ** 0.5
        nb = sum(b * b for b in vec_b) ** 0.5
        return float(dot / (na * nb)) if na > 0 and nb > 0 else 0.0


# ============================================================================
# 1. FileDataBuffer (Thread-Safe, LRU 64KB Cache, Overrides, Transactional Undo)
# ============================================================================

class FileDataBuffer:
    """
    Thread-safe low-level byte buffer wrapping binary files or memory streams.
    Features:
    - 64KB chunk LRU cache (max 64 cached chunks = 4MB cache ceiling)
    - Dirty byte overlay map for sparse non-destructive edits
    - Transactional undo/redo stack supporting history groups
    - SHA-256 byte stream integrity verification
    """

    def __init__(self, chunk_size: int = 64 * 1024, max_cached_chunks: int = 64):
        self.chunk_size = chunk_size
        self.max_cached_chunks = max_cached_chunks
        self._mutex = threading.RLock()
        
        self._raw_data = bytearray()
        self._overrides: Dict[int, int] = {}
        
        # LRU Chunk Cache
        self._chunk_cache: Dict[int, bytes] = {}
        self._chunk_lru: List[int] = []
        
        # Transactional Undo/Redo
        # Each entry in a group is a tuple: (offset, old_val, new_val)
        self._undo_stack: List[List[Tuple[int, Optional[int], Optional[int]]]] = []
        self._redo_stack: List[List[Tuple[int, Optional[int], Optional[int]]]] = []
        self._active_group: Optional[List[Tuple[int, Optional[int], Optional[int]]]] = None
        self._file_path: Optional[Path] = None

    def load_data(self, data: bytes) -> None:
        """Loads raw binary data into buffer and resets state."""
        with self._mutex:
            self._raw_data = bytearray(data)
            self._overrides.clear()
            self._chunk_cache.clear()
            self._chunk_lru.clear()
            self._undo_stack.clear()
            self._redo_stack.clear()
            self._active_group = None
            self._file_path = None

    def load_file(self, file_path: Union[str, Path]) -> None:
        """Reads a binary file from disk into the buffer."""
        with self._mutex:
            path = Path(file_path)
            self._file_path = path
            with open(path, "rb") as f:
                self.load_data(f.read())

    def size(self) -> int:
        """Returns the effective size of the buffer taking dirty overrides into account."""
        with self._mutex:
            max_override = (max(self._overrides.keys()) + 1) if self._overrides else 0
            return max(len(self._raw_data), max_override)

    def __len__(self) -> int:
        return self.size()

    def _get_chunk_locked(self, chunk_index: int) -> bytes:
        """Retrieves a 64KB chunk using LRU cache (caller must hold mutex)."""
        if chunk_index in self._chunk_cache:
            self._chunk_lru.remove(chunk_index)
            self._chunk_lru.append(chunk_index)
            return self._chunk_cache[chunk_index]

        start_offset = chunk_index * self.chunk_size
        end_offset = start_offset + self.chunk_size
        chunk_bytes = bytes(self._raw_data[start_offset:end_offset])

        # Evict oldest chunk if cache size reached
        if len(self._chunk_lru) >= self.max_cached_chunks:
            evict_idx = self._chunk_lru.pop(0)
            self._chunk_cache.pop(evict_idx, None)

        self._chunk_cache[chunk_index] = chunk_bytes
        self._chunk_lru.append(chunk_index)
        return chunk_bytes

    def get_byte(self, offset: int) -> int:
        """Returns byte value at offset (overlay byte if edited, else raw byte)."""
        with self._mutex:
            if offset in self._overrides:
                return self._overrides[offset]
            
            buf_size = self.size()
            if offset < 0 or offset >= buf_size:
                raise IndexError(f"Offset {offset} out of bounds for FileDataBuffer of size {buf_size}")
            
            if offset < len(self._raw_data):
                chunk_idx = offset // self.chunk_size
                chunk_off = offset % self.chunk_size
                chunk = self._get_chunk_locked(chunk_idx)
                return chunk[chunk_off] if chunk_off < len(chunk) else 0
            return 0

    def read_bytes(self, offset: int, length: int) -> bytes:
        """Reads a slice of bytes starting at offset, incorporating dirty overlays."""
        with self._mutex:
            buf_size = self.size()
            if offset < 0 or offset >= buf_size:
                return b""
            actual_len = min(length, buf_size - offset)
            result = bytearray()
            for i in range(actual_len):
                curr_off = offset + i
                result.append(self.get_byte(curr_off))
            return bytes(result)

    def data(self) -> bytes:
        """Returns full effective byte content of buffer."""
        with self._mutex:
            return self.read_bytes(0, self.size())

    def set_byte(self, offset: int, val: int) -> None:
        """Overwrites byte value at offset and records transaction for undo."""
        with self._mutex:
            val = val & 0xFF
            
            # Determine existing byte value before change
            if offset in self._overrides:
                old_val: Optional[int] = self._overrides[offset]
            elif offset < len(self._raw_data):
                old_val = self._raw_data[offset]
            else:
                old_val = None

            self._overrides[offset] = val
            
            # Clear cached chunk containing this offset
            chunk_idx = offset // self.chunk_size
            if chunk_idx in self._chunk_cache:
                self._chunk_cache.pop(chunk_idx, None)
                if chunk_idx in self._chunk_lru:
                    self._chunk_lru.remove(chunk_idx)

            record = (offset, old_val, val)
            if self._active_group is not None:
                self._active_group.append(record)
            else:
                self._undo_stack.append([record])
                self._redo_stack.clear()

    def set_bytes(self, offset: int, data: bytes) -> None:
        """Overwrites a sequence of bytes starting at offset within a single transaction group."""
        with self._mutex:
            was_in_group = self._active_group is not None
            if not was_in_group:
                self.begin_history_group()
            
            for i, b in enumerate(data):
                self.set_byte(offset + i, b)
                
            if not was_in_group:
                self.end_history_group()

    def begin_history_group(self) -> None:
        """Starts a multi-change transactional undo group."""
        with self._mutex:
            if self._active_group is None:
                self._active_group = []

    def end_history_group(self) -> None:
        """Finalizes a multi-change transactional undo group."""
        with self._mutex:
            if self._active_group is not None:
                if self._active_group:
                    self._undo_stack.append(self._active_group)
                    self._redo_stack.clear()
                self._active_group = None

    def undo(self) -> bool:
        """Undoes the last transaction group. Returns True if successful."""
        with self._mutex:
            if not self._undo_stack:
                return False
            group = self._undo_stack.pop()
            
            for offset, old_val, new_val in reversed(group):
                if old_val is None:
                    self._overrides.pop(offset, None)
                else:
                    self._overrides[offset] = old_val
                
                chunk_idx = offset // self.chunk_size
                if chunk_idx in self._chunk_cache:
                    self._chunk_cache.pop(chunk_idx, None)
                    if chunk_idx in self._chunk_lru:
                        self._chunk_lru.remove(chunk_idx)
                        
            self._redo_stack.append(group)
            return True

    def redo(self) -> bool:
        """Redoes the last undone transaction group. Returns True if successful."""
        with self._mutex:
            if not self._redo_stack:
                return False
            group = self._redo_stack.pop()
            
            for offset, old_val, new_val in group:
                if new_val is None:
                    self._overrides.pop(offset, None)
                else:
                    self._overrides[offset] = new_val
                
                chunk_idx = offset // self.chunk_size
                if chunk_idx in self._chunk_cache:
                    self._chunk_cache.pop(chunk_idx, None)
                    if chunk_idx in self._chunk_lru:
                        self._chunk_lru.remove(chunk_idx)
                        
            self._undo_stack.append(group)
            return True

    def current_hash(self) -> str:
        """Calculates SHA-256 digest of the effective buffer bytes."""
        with self._mutex:
            return hashlib.sha256(self.data()).hexdigest()

    def save_to_file(self, filepath: Union[str, Path]) -> None:
        """Saves current buffer data to specified file path."""
        with self._mutex:
            path = Path(filepath)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(self.data())


# ============================================================================
# 2. ModuleManager (Thread-Safe Singleton Module Registry)
# ============================================================================

@dataclass
class ModuleDescription:
    """Descriptor struct for Cremniy IDE modules/tabs."""
    name: str
    category: str
    position: int = 0
    creator: Optional[Callable[[], Any]] = None


class ModuleManager:
    """
    Thread-safe singleton registry mapping category string groups to ModuleDescription factories.
    """
    _instance = None
    _lock = threading.RLock()

    def __init__(self):
        self._registry: Dict[str, List[ModuleDescription]] = {}

    @classmethod
    def instance(cls) -> "ModuleManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = ModuleManager()
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        with cls._lock:
            cls._instance = None

    def register_module(
        self,
        category: str,
        name: str,
        creator: Optional[Callable[[], Any]] = None,
        position: int = 0
    ) -> ModuleDescription:
        """Registers a module under category string group."""
        with self._lock:
            if category not in self._registry:
                self._registry[category] = []
            
            desc = ModuleDescription(name=name, category=category, position=position, creator=creator)
            self._registry[category].append(desc)
            # Sort by position
            self._registry[category].sort(key=lambda m: m.position)
            return desc

    def get_modules(self, category: str) -> List[ModuleDescription]:
        """Returns registered modules for a category."""
        with self._lock:
            return list(self._registry.get(category, []))

    def get_all_modules(self) -> Dict[str, List[ModuleDescription]]:
        """Returns entire module registry map."""
        with self._lock:
            return {cat: list(mods) for cat, mods in self._registry.items()}

    def clear(self) -> None:
        """Clears registry entries."""
        with self._lock:
            self._registry.clear()


# ============================================================================
# 3. DisassemblerEngine (Structured Disassembly Data & Execution)
# ============================================================================

@dataclass
class DisasmInstruction:
    """Represents a disassembled instruction."""
    address: str
    bytes_hex: str
    mnemonic: str
    operands: str = ""
    file_offset: int = 0
    size: int = 1


@dataclass
class DisasmSection:
    """Represents a binary section containing instructions."""
    name: str
    instructions: List[DisasmInstruction] = field(default_factory=list)
    vaddr: int = 0
    file_offset: int = 0
    size: int = 0
    has_file_mapping: bool = True


@dataclass
class DisasmFunction:
    """Represents a disassembled function signature and block."""
    name: str
    address: str
    size: int = 0
    instructions: List[DisasmInstruction] = field(default_factory=list)


@dataclass
class DisasmString:
    """Represents an extracted ASCII/Unicode string."""
    address: str
    value: str
    length: int = 0


class DisassemblerEngine:
    """
    Engine executing radare2/rizin or fallback python disassembly heuristics.
    """

    def __init__(self, bin_dir: Optional[Path] = None):
        self.bin_dir = bin_dir or Path("C:/vazus/bin")

    @staticmethod
    def _find_disasm_binary() -> Optional[str]:
        """Looks for r2.exe or rizin.exe in C:/vazus/bin or PATH."""
        candidates = ["r2.exe", "rizin.exe", "r2", "rizin"]
        bin_dir = Path("C:/vazus/bin")
        for cand in candidates:
            p = bin_dir / cand
            if p.exists():
                return str(p)
        for cand in candidates:
            try:
                subprocess.run([cand, "-v"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return cand
            except Exception:
                continue
        return None

    def disassemble_buffer(
        self,
        buffer: bytes,
        base_address: int = 0x1000,
        arch: str = "x86_64"
    ) -> List[DisasmInstruction]:
        """Disassembles a raw byte buffer into a list of DisasmInstruction objects."""
        if not buffer:
            return []

        # Attempt Capstone disassembly if available
        try:
            import capstone
            cs_arch = capstone.CS_ARCH_X86
            cs_mode = capstone.CS_MODE_64 if "64" in arch else capstone.CS_MODE_32
            md = capstone.Cs(cs_arch, cs_mode)
            instructions = []
            for insn in md.disasm(buffer, base_address):
                b_hex = insn.bytes.hex()
                instructions.append(DisasmInstruction(
                    address=f"0x{insn.address:x}",
                    bytes_hex=b_hex,
                    mnemonic=insn.mnemonic,
                    operands=insn.op_str,
                    file_offset=insn.address - base_address,
                    size=len(insn.bytes)
                ))
            if instructions:
                return instructions
        except Exception:
            pass

        # Pure Python Fallback Disassembler Heuristics
        instructions = []
        curr_offset = 0
        buf_len = len(buffer)
        
        while curr_offset < buf_len:
            curr_addr = base_address + curr_offset
            addr_str = f"0x{curr_addr:x}"
            b = buffer[curr_offset]
            
            # Pattern matching common x86/x64 instructions
            if b == 0x90:
                instructions.append(DisasmInstruction(addr_str, "90", "nop", "", curr_offset, 1))
                curr_offset += 1
            elif b == 0xC3:
                instructions.append(DisasmInstruction(addr_str, "c3", "ret", "", curr_offset, 1))
                curr_offset += 1
            elif b == 0x55:
                instructions.append(DisasmInstruction(addr_str, "55", "push", "rbp", curr_offset, 1))
                curr_offset += 1
            elif b == 0x5D:
                instructions.append(DisasmInstruction(addr_str, "5d", "pop", "rbp", curr_offset, 1))
                curr_offset += 1
            elif b == 0x48 and curr_offset + 2 < buf_len and buffer[curr_offset+1] == 0x89 and buffer[curr_offset+2] == 0xE5:
                instructions.append(DisasmInstruction(addr_str, "4889e5", "mov", "rbp, rsp", curr_offset, 3))
                curr_offset += 3
            elif b == 0x48 and curr_offset + 2 < buf_len and buffer[curr_offset+1] == 0x83 and buffer[curr_offset+2] == 0xEC:
                imm = buffer[curr_offset+3] if curr_offset+3 < buf_len else 0
                instructions.append(DisasmInstruction(addr_str, f"4883ec{imm:02x}", "sub", f"rsp, 0x{imm:x}", curr_offset, 4))
                curr_offset += 4
            elif b == 0xE8 and curr_offset + 4 < buf_len:
                rel = int.from_bytes(buffer[curr_offset+1:curr_offset+5], byteorder="little", signed=True)
                target = curr_addr + 5 + rel
                b_hex = buffer[curr_offset:curr_offset+5].hex()
                instructions.append(DisasmInstruction(addr_str, b_hex, "call", f"0x{target:x}", curr_offset, 5))
                curr_offset += 5
            elif b == 0xEB and curr_offset + 1 < buf_len:
                rel = int.from_bytes(buffer[curr_offset+1:curr_offset+2], byteorder="little", signed=True)
                target = curr_addr + 2 + rel
                b_hex = buffer[curr_offset:curr_offset+2].hex()
                instructions.append(DisasmInstruction(addr_str, b_hex, "jmp", f"0x{target:x}", curr_offset, 2))
                curr_offset += 2
            elif b == 0x31 and curr_offset + 1 < buf_len:
                reg_byte = buffer[curr_offset+1]
                b_hex = buffer[curr_offset:curr_offset+2].hex()
                instructions.append(DisasmInstruction(addr_str, b_hex, "xor", f"reg_{reg_byte:02x}, reg_{reg_byte:02x}", curr_offset, 2))
                curr_offset += 2
            elif b == 0x0F and curr_offset + 1 < buf_len and buffer[curr_offset+1] == 0x05:
                instructions.append(DisasmInstruction(addr_str, "0f05", "syscall", "", curr_offset, 2))
                curr_offset += 2
            else:
                # Default byte instruction
                instructions.append(DisasmInstruction(addr_str, f"{b:02x}", "db", f"0x{b:02x}", curr_offset, 1))
                curr_offset += 1

        return instructions

    def disassemble_file(self, filepath: Union[str, Path]) -> Dict[str, Any]:
        """Extracts disassembly sections, functions, and strings from binary file."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        content = path.read_bytes()
        
        # Try radare2 CLI execution if tool is present
        r2_bin = DisassemblerEngine._find_disasm_binary()
        if r2_bin:
            try:
                cmd = [r2_bin, "-q", "-c", "iSj; ij; iFj; izj", str(path)]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                if res.returncode == 0:
                    lines = [line.strip() for line in res.stdout.splitlines() if line.strip().startswith("[")]
                    if len(lines) >= 1:
                        sections_raw = json.loads(lines[0])
                        sections = [DisasmSection(name=s.get("name", ".sec"), vaddr=s.get("vaddr", 0), size=s.get("size", 0)) for s in sections_raw]
                        if not sections:
                            sections.append(DisasmSection(name=".text", vaddr=0x1000, size=len(content)))
                        
                        # Extract strings from content
                        extracted_strings = []
                        curr_str = []
                        curr_start = 0
                        for idx, byte_val in enumerate(content):
                            if 32 <= byte_val <= 126:
                                if not curr_str:
                                    curr_start = idx
                                curr_str.append(chr(byte_val))
                            else:
                                if len(curr_str) >= 4:
                                    extracted_strings.append(DisasmString(
                                        address=f"0x{0x1000 + curr_start:x}",
                                        value="".join(curr_str),
                                        length=len(curr_str)
                                    ))
                                curr_str = []

                        return {
                            "filename": path.name,
                            "sections": sections,
                            "functions": [DisasmFunction(name="main", address="0x1000")],
                            "strings": extracted_strings or [DisasmString(address="0x2000", value="Radare2 Disassembled")]
                        }
            except Exception:
                pass

        # Fallback python parsing
        instructions = self.disassemble_buffer(content[:2048], base_address=0x1000)
        
        main_sec = DisasmSection(
            name=".text",
            instructions=instructions,
            vaddr=0x1000,
            file_offset=0,
            size=len(content),
            has_file_mapping=True
        )
        
        main_fn = DisasmFunction(
            name="main",
            address="0x1000",
            size=len(content),
            instructions=instructions
        )

        # String extraction
        extracted_strings = []
        curr_str = []
        curr_start = 0
        for idx, byte_val in enumerate(content):
            if 32 <= byte_val <= 126:
                if not curr_str:
                    curr_start = idx
                curr_str.append(chr(byte_val))
            else:
                if len(curr_str) >= 4:
                    extracted_strings.append(DisasmString(
                        address=f"0x{0x1000 + curr_start:x}",
                        value="".join(curr_str),
                        length=len(curr_str)
                    ))
                curr_str = []

        return {
            "filename": path.name,
            "sections": [main_sec],
            "functions": [main_fn],
            "strings": extracted_strings
        }


# ============================================================================
# 4. HexEditorWrapper (Visual Document Model wrapping FileDataBuffer)
# ============================================================================

class HexEditorWrapper:
    """
    Visual document model wrapping FileDataBuffer with range-based metadata,
    styling, comments, selections, and ASCII/Hex dump formatting.
    """

    def __init__(self, buffer: Optional[FileDataBuffer] = None):
        self._buffer = buffer or FileDataBuffer()
        self._metadata: Dict[int, Dict[str, Any]] = {}
        self._comments: Dict[int, str] = {}
        self._foregrounds: Dict[int, str] = {}
        self._backgrounds: Dict[int, str] = {}
        self._selection: Tuple[int, int] = (0, 0)

    def set_shared_buffer(self, buffer: FileDataBuffer) -> None:
        """Binds wrapper to a shared FileDataBuffer instance."""
        self._buffer = buffer

    @property
    def buffer(self) -> FileDataBuffer:
        return self._buffer

    def set_metadata(self, offset: int, length: int, key: str, value: Any) -> None:
        """Sets metadata key-value pair for a range of bytes."""
        for i in range(offset, offset + length):
            if i not in self._metadata:
                self._metadata[i] = {}
            self._metadata[i][key] = value

    def get_metadata(self, offset: int) -> Dict[str, Any]:
        """Returns metadata map at specified offset."""
        return dict(self._metadata.get(offset, {}))

    def set_comment(self, offset: int, comment: str) -> None:
        """Annotates byte offset with a comment string."""
        self._comments[offset] = comment

    def get_comment(self, offset: int) -> Optional[str]:
        """Returns comment annotation at offset if present."""
        return self._comments.get(offset)

    def set_foreground(self, offset: int, length: int, color_hex: str) -> None:
        """Sets foreground text color for a byte range."""
        for i in range(offset, offset + length):
            self._foregrounds[i] = color_hex

    def set_background(self, offset: int, length: int, color_hex: str) -> None:
        """Sets background highlight color for a byte range."""
        for i in range(offset, offset + length):
            self._backgrounds[i] = color_hex

    def get_styles(self, offset: int) -> Dict[str, str]:
        """Returns CSS style dict for offset (foreground & background colors)."""
        styles = {}
        if offset in self._foregrounds:
            styles["color"] = self._foregrounds[offset]
        if offset in self._backgrounds:
            styles["background-color"] = self._backgrounds[offset]
        return styles

    def set_selection(self, start_offset: int, end_offset: int) -> None:
        """Sets cursor selection byte range."""
        self._selection = (min(start_offset, end_offset), max(start_offset, end_offset))

    def get_selection(self) -> Tuple[int, int]:
        """Returns active cursor selection byte range."""
        return self._selection

    def format_hex_dump(self, offset: int = 0, length: int = 256, bytes_per_line: int = 16) -> str:
        """
        Formats buffer slice into standard HEX + ASCII editor view text:
        00000000  48 45 4c 4c 4f 20 57 4f  52 4c 44 21 00 00 00 00  |HELLO WORLD!....|
        """
        data = self._buffer.read_bytes(offset, length)
        lines = []
        for i in range(0, len(data), bytes_per_line):
            chunk = data[i:i + bytes_per_line]
            addr_str = f"{offset + i:08x}"
            
            # Format hex bytes
            hex_parts = []
            for idx, b in enumerate(chunk):
                hex_parts.append(f"{b:02x}")
                if idx == (bytes_per_line // 2) - 1:
                    hex_parts.append("")
            hex_str = " ".join(hex_parts).ljust(bytes_per_line * 3 + 1)
            
            # Format ASCII bytes
            ascii_chars = []
            for b in chunk:
                if 32 <= b <= 126:
                    ascii_chars.append(chr(b))
                else:
                    ascii_chars.append(".")
            ascii_str = "".join(ascii_chars)
            
            lines.append(f"{addr_str}  {hex_str} |{ascii_str}|")
        return "\n".join(lines)


# ============================================================================
# 5. CremniySuperGraphExtractor (768D Vector Space Ingestion & Search)
# ============================================================================

class CremniySuperGraphExtractor:
    """
    Indexes disassembly sections, function signatures, and hex buffers into
    kg_nodes and kg_edges under domain 'cremniy_disasm' with 768D Gemini vector embeddings.
    """

    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        if UnifiedEmbeddingManager:
            self.embedder = UnifiedEmbeddingManager(dimension=768)
        else:
            self.embedder = None

    def _get_embedding(self, text: str) -> List[float]:
        if self.embedder:
            try:
                return self.embedder.get_embedding(text)
            except Exception:
                pass
        # Deterministic 768D pseudo-embedding fallback
        h = hashlib.sha256(text.encode("utf-8")).digest()
        vec = []
        for i in range(768):
            val = (h[i % 32] + (i * 13)) % 256
            vec.append((val / 128.0) - 1.0)
        return vec

    def _ensure_db_schema(self, conn: sqlite3.Connection) -> None:
        """Ensures kg_nodes and kg_edges tables exist matching vazus.db schema."""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS kg_nodes (
                id TEXT PRIMARY KEY,
                name TEXT,
                domain TEXT,
                node_type TEXT,
                description TEXT,
                tags TEXT,
                properties TEXT,
                embedding_json TEXT
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS kg_edges (
                source_id TEXT,
                target_id TEXT,
                relation TEXT,
                strength REAL,
                properties TEXT,
                PRIMARY KEY (source_id, target_id, relation)
            );
        """)
        conn.commit()

    def index_disassembly_section(
        self,
        section: DisasmSection,
        source_filename: str = "binary.bin"
    ) -> str:
        """Vectorizes and indexes a DisasmSection into 768D kg_nodes in vazus.db."""
        node_id = f"cremniy_disasm_sec_{source_filename}_{section.name}".replace("/", "_").replace("\\", "_")
        
        # Build assembly representation snippet
        insn_texts = [f"{insn.address}: {insn.bytes_hex:<10} {insn.mnemonic} {insn.operands}" for insn in section.instructions[:50]]
        snippet = f"Section {section.name} (VAddr: 0x{section.vaddr:x}, Size: {section.size} bytes)\n" + "\n".join(insn_texts)
        
        vec = self._get_embedding(snippet)
        
        conn = sqlite3.connect(str(self.db_path))
        try:
            self._ensure_db_schema(conn)
            props = json.dumps({"source_file": source_filename, "vaddr": section.vaddr, "size": section.size})
            conn.execute("""
                INSERT OR REPLACE INTO kg_nodes (id, name, domain, node_type, description, tags, properties, embedding_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                node_id,
                f"Section {section.name} [{source_filename}]",
                "cremniy_disasm",
                "DisasmSectionNode",
                snippet,
                "cremniy,disasm,section",
                props,
                json.dumps(vec)
            ))
            conn.commit()
        finally:
            conn.close()

        return node_id

    def index_disassembly_function(
        self,
        func: DisasmFunction,
        source_filename: str = "binary.bin"
    ) -> str:
        """Vectorizes and indexes a DisasmFunction into 768D kg_nodes in vazus.db."""
        node_id = f"cremniy_disasm_fn_{source_filename}_{func.name}".replace("/", "_").replace("\\", "_")
        
        insn_texts = [f"{insn.address}: {insn.mnemonic} {insn.operands}" for insn in func.instructions[:50]]
        snippet = f"Function {func.name} @ {func.address} (Size: {func.size} bytes)\n" + "\n".join(insn_texts)
        
        vec = self._get_embedding(snippet)
        
        conn = sqlite3.connect(str(self.db_path))
        try:
            self._ensure_db_schema(conn)
            props = json.dumps({"source_file": source_filename, "address": func.address, "size": func.size})
            conn.execute("""
                INSERT OR REPLACE INTO kg_nodes (id, name, domain, node_type, description, tags, properties, embedding_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                node_id,
                f"Function {func.name} [{source_filename}]",
                "cremniy_disasm",
                "DisasmFunctionNode",
                snippet,
                "cremniy,disasm,function",
                props,
                json.dumps(vec)
            ))
            conn.commit()
        finally:
            conn.close()

        return node_id

    def index_hex_buffer(
        self,
        buffer: FileDataBuffer,
        source_filename: str = "binary.bin",
        slice_size: int = 512
    ) -> str:
        """Vectorizes and indexes a FileDataBuffer hex preview into 768D kg_nodes in vazus.db."""
        node_id = f"cremniy_hex_{source_filename}_{buffer.current_hash()[:8]}"
        wrapper = HexEditorWrapper(buffer)
        dump_text = wrapper.format_hex_dump(offset=0, length=slice_size)
        
        snippet = f"HEX Buffer Preview ({source_filename}, Hash: {buffer.current_hash()[:16]})\n" + dump_text
        vec = self._get_embedding(snippet)
        
        conn = sqlite3.connect(str(self.db_path))
        try:
            self._ensure_db_schema(conn)
            props = json.dumps({"source_file": source_filename, "hash": buffer.current_hash()})
            conn.execute("""
                INSERT OR REPLACE INTO kg_nodes (id, name, domain, node_type, description, tags, properties, embedding_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                node_id,
                f"HEX Buffer [{source_filename}]",
                "cremniy_disasm",
                "HexBufferNode",
                snippet,
                "cremniy,hex,buffer",
                props,
                json.dumps(vec)
            ))
            conn.commit()
        finally:
            conn.close()

        return node_id

    def query_vector_space(
        self,
        query: str,
        top_k: int = 5,
        domain_filter: Optional[str] = "cremniy_disasm"
    ) -> List[Dict[str, Any]]:
        """Queries 768D vector space in vazus.db using cosine similarity."""
        query_vec = self._get_embedding(query)
        
        conn = sqlite3.connect(str(self.db_path))
        try:
            self._ensure_db_schema(conn)
            if domain_filter:
                cursor = conn.execute(
                    "SELECT id, name, domain, node_type, description, properties, embedding_json FROM kg_nodes WHERE domain = ?",
                    (domain_filter,)
                )
            else:
                cursor = conn.execute("SELECT id, name, domain, node_type, description, properties, embedding_json FROM kg_nodes")
            
            rows = cursor.fetchall()
            results = []
            
            for row in rows:
                nid, name, dom, ntype, desc, props, vec_json = row
                if vec_json:
                    node_vec = json.loads(vec_json)
                    sim = calculate_cosine_similarity(query_vec, node_vec)
                    results.append({
                        "id": nid,
                        "name": name,
                        "domain": dom,
                        "node_type": ntype,
                        "description": desc,
                        "properties": props,
                        "similarity": round(sim, 4)
                    })
            
            results.sort(key=lambda x: x["similarity"], reverse=True)
            return results[:top_k]
        finally:
            conn.close()
