"""
tests/test_reverse_engineer.py — Tests for ReverseEngineerEngine.
"""

from vazus_core.analysis.reverse_engineer import ReverseEngineerEngine


def test_reconstruct_c_struct():
    c_code = """
    typedef struct {
        int sensor_id;
        double value;
        char status;
    } SensorPacket;
    """
    res = ReverseEngineerEngine.reconstruct_c_struct(c_code)
    assert res is not None
    assert res.name == "SensorPacket"
    assert res.language == "c"
    assert len(res.fields) == 3
    # int (4) + 4 pad + double (8) + char (1) + 7 pad = 24 bytes
    assert res.total_size == 24
    assert res.alignment == 8


def test_reconstruct_go_struct():
    go_code = """
    type NodeHeader struct {
        ID       int64
        Capacity int32
        Flags    byte
    }
    """
    res = ReverseEngineerEngine.reconstruct_go_struct(go_code)
    assert res is not None
    assert res.name == "NodeHeader"
    assert res.language == "go"
    assert len(res.fields) == 3
    # int64 (8) + int32 (4) + byte (1) + 3 pad = 16 bytes
    assert res.total_size == 16


def test_cross_language_type_mapping():
    assert "int64_t" in ReverseEngineerEngine.map_cross_language_types("int")
    assert "double" in ReverseEngineerEngine.map_cross_language_types("float64")
    assert "const char*" in ReverseEngineerEngine.map_cross_language_types("string")
