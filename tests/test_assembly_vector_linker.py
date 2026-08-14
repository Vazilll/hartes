"""
tests/test_assembly_vector_linker.py — Unit Tests for Assembly Opcode 768D Vector Linker.
"""

import sys
import os
import json
import sqlite3
import pytest
import numpy as np
from pathlib import Path

VAZUS_DIR = Path("C:/vazus")
if str(VAZUS_DIR) not in sys.path:
    sys.path.insert(0, str(VAZUS_DIR))

from vazus_core.supergraph_linker import SuperGraphLinker
from vazus_core.embeddings import UnifiedEmbeddingManager
from vazus_core.assembly_vector_linker import AssemblyVectorLinker


def test_assembly_vector_linker_initialization(tmp_path):
    db_path = tmp_path / "test_linker.db"
    linker = AssemblyVectorLinker(db_path=db_path)
    
    assert isinstance(linker, SuperGraphLinker)
    assert hasattr(linker, "embedding_manager")
    assert isinstance(linker.embedding_manager, UnifiedEmbeddingManager)
    assert linker.db_path == db_path
    assert db_path.exists()


def test_disassemble_routine_x86_64():
    linker = AssemblyVectorLinker()
    code_bytes = b"\x55\x48\x89\xe5\x48\x83\xec\x20\x90\xc3"
    instructions = linker.disassemble_routine(code_bytes, arch="x86_64")

    assert isinstance(instructions, list)
    assert len(instructions) >= 5

    first_inst = instructions[0]
    assert "address" in first_inst
    assert "mnemonic" in first_inst
    assert "op_str" in first_inst
    assert "esil" in first_inst
    assert "raw_bytes" in first_inst

    assert first_inst["mnemonic"] == "push"
    assert first_inst["op_str"] == "rbp"
    assert first_inst["raw_bytes"] == "55"

    mnemonics = [inst["mnemonic"] for inst in instructions]
    assert "mov" in mnemonics
    assert "sub" in mnemonics
    assert "nop" in mnemonics
    assert "ret" in mnemonics


def test_disassemble_routine_arm64():
    linker = AssemblyVectorLinker()
    # ARM64: nop (0x1f 0x20 0x03 0xd5), ret (0xc0 0x03 0x5f 0xd6)
    code_bytes = b"\x1f\x20\x03\xd5\xc0\x03\x5f\xd6"
    instructions = linker.disassemble_routine(code_bytes, arch="arm64")

    assert isinstance(instructions, list)
    assert len(instructions) == 2
    assert instructions[0]["mnemonic"] == "nop"
    assert instructions[1]["mnemonic"] == "ret"


def test_disassemble_binary(tmp_path):
    linker = AssemblyVectorLinker()

    # Test returning empty list for non-existent path
    assert linker.disassemble_binary(str(tmp_path / "non_existent_binary.exe")) == []

    # Test returning empty list immediately for directory path (verifying zero deadlock)
    dir_path = tmp_path / "somedir_test"
    dir_path.mkdir()
    assert linker.disassemble_binary(str(dir_path)) == []

    # Test disassembling existing executable (sys.executable)
    bin_path = sys.executable
    instructions = linker.disassemble_binary(bin_path)

    assert isinstance(instructions, list)
    assert len(instructions) > 0
    for inst in instructions[:5]:
        assert "address" in inst
        assert "mnemonic" in inst
        assert "op_str" in inst
        assert "esil" in inst
        assert "raw_bytes" in inst


def test_build_opcode_embeddings():
    linker = AssemblyVectorLinker()
    opcodes = ["push rbp", "mov rbp, rsp", "sub rsp, 0x20"]
    embeddings = linker.build_opcode_embeddings(opcodes)

    assert isinstance(embeddings, np.ndarray)
    assert embeddings.shape == (3, 768)

    # Test empty opcodes list
    empty_embeddings = linker.build_opcode_embeddings([])
    assert isinstance(empty_embeddings, np.ndarray)
    assert empty_embeddings.shape == (0, 768)


def test_link_assembly_to_ast_parameter_aliases(tmp_path):
    test_db = tmp_path / "vazus_param_test.db"
    linker = AssemblyVectorLinker(db_path=test_db)
    insts = [{"address": "0x1000", "mnemonic": "nop", "op_str": "", "esil": "nop", "raw_bytes": "90"}]

    # Test with assembly_instructions
    node_id1 = linker.link_assembly_to_ast(
        ast_node_id="ast:test_func_1",
        assembly_instructions=insts
    )
    assert node_id1 == "asm:test_func_1"

    # Test with assembly_ir alias
    node_id2 = linker.link_assembly_to_ast(
        ast_node_id="ast:test_func_2",
        assembly_ir=insts
    )
    assert node_id2 == "asm:test_func_2"


def test_generate_assembly_embedding():
    linker = AssemblyVectorLinker()
    instructions = [
        {"address": "0x1000", "mnemonic": "push", "op_str": "rbp", "esil": "rbp,rsp", "raw_bytes": "55"},
        {"address": "0x1001", "mnemonic": "mov", "op_str": "rbp, rsp", "esil": "rsp,rbp,=", "raw_bytes": "4889e5"}
    ]

    vec = linker.generate_assembly_embedding(instructions)
    assert isinstance(vec, list)
    assert len(vec) == 768
    assert all(isinstance(val, float) for val in vec)

    # Test empty instructions embedding
    empty_vec = linker.generate_assembly_embedding([])
    assert isinstance(empty_vec, list)
    assert len(empty_vec) == 768


def test_link_assembly_to_ast(tmp_path):
    test_db = tmp_path / "vazus_test.db"
    linker = AssemblyVectorLinker(db_path=test_db)

    code_bytes = b"\x55\x48\x89\xe5\x48\x83\xec\x20\x90\xc3"
    instructions = linker.disassemble_routine(code_bytes, arch="x86_64")

    ast_node_id = "ast:vazus_core/example.py::compute_hash"
    asm_node_id = linker.link_assembly_to_ast(
        ast_node_id=ast_node_id,
        assembly_instructions=instructions,
        binary_path=sys.executable,
        db_path=test_db
    )

    assert asm_node_id == "asm:vazus_core/example.py::compute_hash"

    # Verify node in kg_nodes
    conn = sqlite3.connect(test_db)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        node_row = cursor.execute("SELECT * FROM kg_nodes WHERE id = ?", (asm_node_id,)).fetchone()
        assert node_row is not None
        assert node_row["domain"] == "assembly"
        assert node_row["node_type"] == "AssemblyFunction"
        assert "Assembly for" in node_row["name"]

        emb = json.loads(node_row["embedding_json"])
        assert isinstance(emb, list)
        assert len(emb) == 768

        props = json.loads(node_row["properties"])
        assert props["ast_node_id"] == ast_node_id
        assert props["instruction_count"] == len(instructions)

        # Verify edges in kg_edges
        edges = cursor.execute("SELECT * FROM kg_edges WHERE source_id = ?", (asm_node_id,)).fetchall()
        relations = [e["relation"] for e in edges]
        assert "DISASSEMBLED_FROM" in relations
        assert "IMPLEMENTS_AST" in relations
    finally:
        conn.close()

    # Verify binding into Unified Vector Space search
    results = linker.embedding_manager.search_unified_vector_space(
        query="assembly routine push rbp mov rbp rsp",
        db_path=test_db,
        top_k=5
    )
    assert len(results) > 0
    found_ids = [r["id"] for r in results]
    assert asm_node_id in found_ids


def test_edge_cases():
    linker = AssemblyVectorLinker()
    assert linker.disassemble_routine(b"") == []
    
    # Test invalid arch fallback
    instructions = linker.disassemble_routine(b"\x90\xc3", arch="unknown_arch")
    assert len(instructions) == 2


def test_malformed_binary_files(tmp_path):
    linker = AssemblyVectorLinker()
    malformed_file = tmp_path / "corrupt.exe"
    malformed_file.write_bytes(b"\x00\xff" * 500 + b"INVALID_HEADER_DATA")

    # Should fall back gracefully to Capstone disasm without crashing
    instructions = linker.disassemble_binary(str(malformed_file))
    assert isinstance(instructions, list)

    # Test directory input gracefully handling
    dir_path = tmp_path / "somedir"
    dir_path.mkdir()
    instructions_dir = linker.disassemble_binary(str(dir_path))
    assert instructions_dir == []


def test_architecture_modes():
    linker = AssemblyVectorLinker()
    code_bytes = b"\x90\xc3"  # nop, ret

    # Test various valid/invalid arch strings
    archs = ["x86_64", "x86", "arm", "arm64", "mips", "mips64", "ppc", "unknown_arch", ""]
    for arch in archs:
        res = linker.disassemble_routine(code_bytes, arch=arch)
        assert isinstance(res, list)

    # Test None arch handling
    res_none = linker.disassemble_routine(code_bytes, arch=None)
    assert isinstance(res_none, list)


def test_empty_instructions_linking(tmp_path):
    custom_db = tmp_path / "nested" / "dir" / "custom_vazus.db"
    linker = AssemblyVectorLinker(db_path=custom_db)

    empty_vec = linker.generate_assembly_embedding([])
    assert len(empty_vec) == 768

    asm_id = linker.link_assembly_to_ast(
        ast_node_id="ast:empty_func",
        assembly_instructions=[],
        db_path=custom_db
    )
    assert asm_id == "asm:empty_func"
    assert custom_db.exists()

    conn = sqlite3.connect(custom_db)
    cursor = conn.cursor()
    row = cursor.execute("SELECT properties FROM kg_nodes WHERE id = ?", (asm_id,)).fetchone()
    props = json.loads(row[0])
    assert props["instruction_count"] == 0
    conn.close()


def test_concurrent_db_writes(tmp_path):
    import concurrent.futures

    concurrent_db = tmp_path / "concurrent_vazus.db"
    linker = AssemblyVectorLinker(db_path=concurrent_db)
    sample_instructions = [{"address": "0x1000", "mnemonic": "nop", "op_str": "", "esil": "nop", "raw_bytes": "90"}]

    def worker(worker_id: int):
        ast_id = f"ast:module::fn_{worker_id}"
        return linker.link_assembly_to_ast(
            ast_node_id=ast_id,
            assembly_instructions=sample_instructions,
            db_path=concurrent_db
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(worker, i) for i in range(30)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    assert len(results) == 30

    conn = sqlite3.connect(concurrent_db)
    cursor = conn.cursor()
    count = cursor.execute("SELECT COUNT(*) FROM kg_nodes WHERE domain = 'assembly'").fetchone()[0]
    edge_count = cursor.execute("SELECT COUNT(*) FROM kg_edges WHERE relation = 'DISASSEMBLED_FROM'").fetchone()[0]
    conn.close()

    assert count == 30
    assert edge_count == 30


def test_corrupt_byte_streams():
    linker = AssemblyVectorLinker()
    # Random unaligned noisy byte stream
    corrupt_bytes = os.urandom(1024)
    instructions = linker.disassemble_routine(corrupt_bytes, arch="x86_64")
    assert isinstance(instructions, list)


def test_node_id_prefix_variants(tmp_path):
    db_path = tmp_path / "prefix_test.db"
    linker = AssemblyVectorLinker(db_path=db_path)
    insts = [{"address": "0x1000", "mnemonic": "ret", "op_str": "", "esil": "ret", "raw_bytes": "c3"}]

    id1 = linker.link_assembly_to_ast("ast:func1", insts, db_path=db_path)
    id2 = linker.link_assembly_to_ast("asm:func2", insts, db_path=db_path)
    id3 = linker.link_assembly_to_ast("func3", insts, db_path=db_path)

    assert id1 == "asm:func1"
    assert id2 == "asm:func2"
    assert id3 == "asm:func3"

