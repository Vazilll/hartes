"""
vazus.vazus_core.assembly_vector_linker — Requirement R2: Assembly Opcode 768D Vector Linker.

Extends SuperGraphLinker and UnifiedEmbeddingManager to disassemble binary executables and
raw machine code routines using Capstone and Rizin, generate 768D vector embeddings, and
link assembly nodes with AST topology nodes in vazus.db.
"""

import sys
import os
import json
import sqlite3
import time
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional, Union
import numpy as np

VAZUS_DIR = Path("C:/vazus")
if str(VAZUS_DIR) not in sys.path:
    sys.path.insert(0, str(VAZUS_DIR))

from vazus_core.supergraph_linker import SuperGraphLinker, DEFAULT_DB_PATH, DEFAULT_GRAPH_JSON_PATH
from vazus_core.memory.embeddings import UnifiedEmbeddingManager, get_embedding_manager
from vazus_core.memory.db import get_db_connection


class AssemblyVectorLinker(SuperGraphLinker):
    """
    Assembly Opcode 768D Vector Linker.
    Disassembles binary executables / raw bytes via Capstone & Rizin, formats intermediate
    representation (IR) instructions, computes 768D vector embeddings, and links Assembly
    nodes to AST Code Graph nodes in vazus.db.
    """

    def __init__(
        self,
        db_path: Union[Path, str] = DEFAULT_DB_PATH,
        graph_json_path: Optional[Union[Path, str]] = None,
        wiki_dir: Optional[Path] = None,
        wiki_dirs: Optional[List[Path]] = None,
        vector_dim: int = 768,
        embedding_manager: Optional[UnifiedEmbeddingManager] = None
    ):
        gpath = Path(graph_json_path) if graph_json_path else DEFAULT_GRAPH_JSON_PATH
        super().__init__(
            db_path=Path(db_path),
            graph_json_path=gpath,
            wiki_dir=wiki_dir,
            wiki_dirs=wiki_dirs,
            vector_dim=vector_dim
        )
        self.embedding_manager = embedding_manager or self.embedder

    def _get_capstone_arch_mode(self, arch: str) -> Tuple[int, int]:
        import capstone
        arch_lower = (arch or "").lower().strip()
        if arch_lower in ("x86_64", "amd64", "x64"):
            return capstone.CS_ARCH_X86, capstone.CS_MODE_64
        elif arch_lower in ("x86", "x86_32", "i386", "i686"):
            return capstone.CS_ARCH_X86, capstone.CS_MODE_32
        elif arch_lower in ("arm", "arm32"):
            return capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM
        elif arch_lower in ("arm64", "aarch64"):
            return capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM
        elif arch_lower in ("mips", "mips32"):
            return capstone.CS_ARCH_MIPS, capstone.CS_MODE_MIPS32
        elif arch_lower == "mips64":
            return capstone.CS_ARCH_MIPS, capstone.CS_MODE_MIPS64
        elif arch_lower in ("ppc", "ppc64"):
            return capstone.CS_ARCH_PPC, capstone.CS_MODE_64
        else:
            return capstone.CS_ARCH_X86, capstone.CS_MODE_64

    def disassemble_routine(self, code_bytes: bytes, arch: str = "x86_64") -> List[Dict[str, Any]]:
        """
        Disassembles raw machine code bytes into structured IR instruction dictionaries
        containing 'address', 'mnemonic', 'op_str', 'esil', and 'raw_bytes'.
        """
        if not code_bytes:
            return []

        instructions = []
        try:
            import capstone
            cs_arch, cs_mode = self._get_capstone_arch_mode(arch)
            md = capstone.Cs(cs_arch, cs_mode)
            md.detail = True

            for i in md.disasm(code_bytes, 0x1000):
                raw_hex = bytes(i.bytes).hex()
                op_str = i.op_str if i.op_str else ""
                mnemonic = i.mnemonic if i.mnemonic else ""
                esil_str = f"{mnemonic},{op_str}" if op_str else mnemonic

                instructions.append({
                    "address": f"0x{i.address:x}",
                    "mnemonic": mnemonic,
                    "op_str": op_str,
                    "esil": esil_str,
                    "raw_bytes": raw_hex
                })
        except Exception as e:
            sys.stderr.write(f"[AssemblyVectorLinker] Capstone routine disasm error: {e}\n")

        return instructions

    def disassemble_binary(self, binary_path: str) -> List[Dict[str, Any]]:
        """
        Disassembles binary executable/DLL/object files using Capstone (capstone.Cs)
        and/or Rizin (rzpipe / C:\\vazus\\bin\\rizin.exe) into intermediate representation (IR)
        instructions containing address, mnemonic, op_str, esil (if available), and raw_bytes.
        """
        bpath = Path(binary_path)
        if not bpath.exists() or not bpath.is_file():
            return []

        instructions = []

        # 1. Try Rizin via rzpipe if rizin binary or rzpipe is available
        if os.path.exists(r"C:\vazus\bin\rizin.exe"):
            os.environ["PATH"] = r"C:\vazus\bin;" + os.environ.get("PATH", "")

        try:
            import rzpipe
            rz = rzpipe.open(str(bpath))
            rz.cmd("aa")
            pdfj = rz.cmdj("pdfj")
            ops = []
            if pdfj and isinstance(pdfj, dict) and "ops" in pdfj:
                ops = pdfj["ops"]
            if not ops:
                pdrj = rz.cmdj("pdrj")
                if pdrj and isinstance(pdrj, list):
                    ops = pdrj
            if not ops:
                pij = rz.cmdj("pij 200")
                if pij and isinstance(pij, list):
                    ops = pij
            rz.quit()

            if ops:
                for op in ops:
                    if not isinstance(op, dict):
                        continue
                    addr_num = op.get("offset", op.get("addr", 0))
                    addr_str = f"0x{addr_num:x}" if isinstance(addr_num, int) else str(addr_num)

                    opcode_full = op.get("opcode", op.get("disasm", ""))
                    parts = opcode_full.split(None, 1)
                    mnemonic = parts[0] if parts else op.get("type", "")
                    op_str = parts[1] if len(parts) > 1 else ""
                    esil = op.get("esil", "")
                    raw_bytes = op.get("bytes", "")

                    instructions.append({
                        "address": addr_str,
                        "mnemonic": mnemonic,
                        "op_str": op_str,
                        "esil": esil,
                        "raw_bytes": raw_bytes
                    })
        except Exception as e:
            sys.stderr.write(f"[AssemblyVectorLinker] Rizin binary disasm note: {e}\n")
            instructions = []

        # 2. Capstone fallback if Rizin did not yield instructions
        if not instructions:
            try:
                with open(bpath, "rb") as f:
                    code_bytes = f.read()
                if code_bytes:
                    instructions = self.disassemble_routine(code_bytes, arch="x86_64")
            except Exception as e:
                sys.stderr.write(f"[AssemblyVectorLinker] Capstone binary fallback error: {e}\n")

        return instructions

    def generate_assembly_embedding(self, instructions: List[Dict[str, Any]]) -> List[float]:
        """
        Formats the disassembly IR into structured opcode text and generates
        a 768-dim vector embedding via UnifiedEmbeddingManager.
        """
        if not instructions:
            formatted_text = "empty assembly function opcode sequence"
        else:
            lines = []
            for inst in instructions:
                addr = inst.get("address", "")
                mnem = inst.get("mnemonic", "")
                op_str = inst.get("op_str", "")
                esil = inst.get("esil", "")
                raw = inst.get("raw_bytes", "")

                line_str = f"{addr}: {mnem} {op_str}".strip()
                if esil:
                    line_str += f" | esil: {esil}"
                if raw:
                    line_str += f" | raw: {raw}"
                lines.append(line_str)
            formatted_text = "\n".join(lines)

        return self.embedding_manager.get_embedding(formatted_text)

    def build_opcode_embeddings(self, opcodes: List[str]) -> np.ndarray:
        """
        Takes a list of opcode strings, computes 768D vector embeddings for each using
        self.embedding_manager.get_embedding(op), and stacks them into a 2D NumPy array
        of shape (len(opcodes), 768) (or (0, 768) if empty).
        """
        if not opcodes:
            dim = getattr(self, "vector_dim", 768)
            return np.empty((0, dim), dtype=np.float32)
        embeddings = [self.embedding_manager.get_embedding(op) for op in opcodes]
        return np.array(embeddings, dtype=np.float32)

    def link_assembly_to_ast(
        self,
        ast_node_id: str,
        assembly_instructions: Optional[List[Dict[str, Any]]] = None,
        binary_path: Optional[str] = None,
        db_path: Optional[Union[str, Path]] = None,
        assembly_ir: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Creates an assembly node ('AssemblyFunction' / 'AssemblyOpcode') in kg_nodes with its 768D
        vector embedding, inserts edge ('DISASSEMBLED_FROM' / 'IMPLEMENTS_AST') in kg_edges connecting
        to ast_node_id, and binds into the unified vector space alongside AST nodes and Obsidian wiki notes.
        Returns the created assembly node ID string.
        """
        instructions = (
            assembly_instructions
            if assembly_instructions is not None
            else (assembly_ir if assembly_ir is not None else [])
        )

        target_db = Path(db_path) if db_path else self.db_path
        target_db.parent.mkdir(parents=True, exist_ok=True)

        if ast_node_id.startswith("ast:"):
            asm_node_id = f"asm:{ast_node_id[4:]}"
        elif ast_node_id.startswith("asm:"):
            asm_node_id = ast_node_id
        else:
            asm_node_id = f"asm:{ast_node_id}"

        embedding_vec = self.generate_assembly_embedding(instructions)
        embedding_json = json.dumps(embedding_vec)

        instr_summary = []
        for inst in instructions[:10]:
            mnemonic = inst.get("mnemonic", "")
            op_str = inst.get("op_str", "")
            addr = inst.get("address", "")
            instr_summary.append(f"{addr}: {mnemonic} {op_str}".strip())
        description = f"Assembly routine ({len(instructions)} instructions):\n" + "\n".join(instr_summary)

        node_name = f"Assembly for {ast_node_id}"
        if binary_path:
            node_name += f" ({Path(binary_path).name})"

        props = {
            "binary_path": binary_path or "",
            "instruction_count": len(instructions),
            "instructions": instructions,
            "ast_node_id": ast_node_id,
            "linked_at": time.time()
        }
        props_json = json.dumps(props)

        conn = get_db_connection(target_db)
        try:

            conn.executescript("""
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

                CREATE TABLE IF NOT EXISTS kg_edges (
                    source_id TEXT,
                    target_id TEXT,
                    relation TEXT,
                    strength REAL,
                    properties TEXT,
                    PRIMARY KEY (source_id, target_id, relation)
                );

                CREATE INDEX IF NOT EXISTS idx_kg_nodes_domain ON kg_nodes(domain);
                CREATE INDEX IF NOT EXISTS idx_kg_nodes_type ON kg_nodes(node_type);
                CREATE INDEX IF NOT EXISTS idx_kg_edges_source ON kg_edges(source_id);
                CREATE INDEX IF NOT EXISTS idx_kg_edges_target ON kg_edges(target_id);
                CREATE INDEX IF NOT EXISTS idx_kg_edges_rel ON kg_edges(relation);
            """)

            # Insert Assembly Node
            conn.execute(
                """
                INSERT OR REPLACE INTO kg_nodes 
                (id, name, domain, node_type, description, tags, properties, embedding_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    asm_node_id,
                    node_name,
                    "assembly",
                    "AssemblyFunction",
                    description,
                    "assembly,opcode,disassembly,768D",
                    props_json,
                    embedding_json
                )
            )

            # Insert Edge: DISASSEMBLED_FROM (asm -> ast)
            conn.execute(
                """
                INSERT OR REPLACE INTO kg_edges
                (source_id, target_id, relation, strength, properties)
                VALUES (?, ?, ?, ?, ?)
                """,
                (asm_node_id, ast_node_id, "DISASSEMBLED_FROM", 1.0, json.dumps({"source": "assembly_vector_linker"}))
            )

            # Insert Edge: IMPLEMENTS_AST (asm -> ast)
            conn.execute(
                """
                INSERT OR REPLACE INTO kg_edges
                (source_id, target_id, relation, strength, properties)
                VALUES (?, ?, ?, ?, ?)
                """,
                (asm_node_id, ast_node_id, "IMPLEMENTS_AST", 1.0, json.dumps({"source": "assembly_vector_linker"}))
            )

            conn.commit()
        finally:
            conn.close()

        return asm_node_id
