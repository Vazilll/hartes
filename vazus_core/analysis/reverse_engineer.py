"""
vazus_core.analysis.reverse_engineer — Cross-Language Reverse Engineering & Symbol Topology.
Provides struct memory layout reconstruction, cross-language call-graph intersection,
and type mapping across Go, C, and Python.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class StructField:
    name: str
    type_str: str
    byte_size: int
    offset: int


@dataclass
class ReconstructedStruct:
    name: str
    language: str
    total_size: int
    alignment: int
    fields: List[StructField] = field(default_factory=list)


class ReverseEngineerEngine:
    """
    Reverse engineering analysis engine for struct layout reconstruction
    and cross-language symbol lineage.
    """

    TYPE_SIZES_C = {
        "char": 1,
        "uint8_t": 1,
        "int8_t": 1,
        "bool": 1,
        "short": 2,
        "uint16_t": 2,
        "int16_t": 2,
        "int": 4,
        "uint32_t": 4,
        "int32_t": 4,
        "float": 4,
        "long": 8,
        "long long": 8,
        "uint64_t": 8,
        "int64_t": 8,
        "double": 8,
        "void*": 8,
    }

    TYPE_SIZES_GO = {
        "byte": 1,
        "bool": 1,
        "int8": 1,
        "uint8": 1,
        "int16": 2,
        "uint16": 2,
        "int32": 4,
        "uint32": 4,
        "float32": 4,
        "rune": 4,
        "int": 8,
        "uint": 8,
        "int64": 8,
        "uint64": 8,
        "float64": 8,
        "uintptr": 8,
        "string": 16,
    }

    @classmethod
    def reconstruct_c_struct(cls, struct_code: str) -> Optional[ReconstructedStruct]:
        """Parses a C struct definition and computes memory layout offsets and padding."""
        m = re.search(r"typedef\s+struct\s*\{([^}]+)\}\s*([a-zA-Z0-9_]+);", struct_code, re.DOTALL)
        if not m:
            m = re.search(r"struct\s+([a-zA-Z0-9_]+)\s*\{([^}]+)\};", struct_code, re.DOTALL)
            if not m:
                return None
            name, body = m.group(1), m.group(2)
        else:
            body, name = m.group(1), m.group(2)

        fields = []
        offset = 0
        max_align = 1

        for line in body.split(";"):
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                t_str = " ".join(parts[:-1])
                f_name = parts[-1].strip("*")
                is_ptr = "*" in line

                size = 8 if is_ptr else cls.TYPE_SIZES_C.get(t_str, 8)
                align = min(size, 8)
                max_align = max(max_align, align)

                # Add padding for alignment
                if offset % align != 0:
                    offset += align - (offset % align)

                fields.append(StructField(name=f_name, type_str=t_str, byte_size=size, offset=offset))
                offset += size

        # Tail padding to match struct alignment
        if offset % max_align != 0:
            offset += max_align - (offset % max_align)

        return ReconstructedStruct(
            name=name,
            language="c",
            total_size=offset,
            alignment=max_align,
            fields=fields,
        )

    @classmethod
    def reconstruct_go_struct(cls, struct_code: str) -> Optional[ReconstructedStruct]:
        """Parses a Go struct definition and computes 64-bit alignment and offsets."""
        m = re.search(r"type\s+([a-zA-Z0-9_]+)\s+struct\s*\{([^}]+)\}", struct_code, re.DOTALL)
        if not m:
            return None

        name, body = m.group(1), m.group(2)
        fields = []
        offset = 0
        max_align = 1

        for line in body.splitlines():
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                f_name, t_str = parts[0], parts[1]
                is_ptr = t_str.startswith("*")

                size = 8 if is_ptr else cls.TYPE_SIZES_GO.get(t_str, 8)
                align = min(size, 8)
                max_align = max(max_align, align)

                if offset % align != 0:
                    offset += align - (offset % align)

                fields.append(StructField(name=f_name, type_str=t_str, byte_size=size, offset=offset))
                offset += size

        if offset % max_align != 0:
            offset += max_align - (offset % max_align)

        return ReconstructedStruct(
            name=name,
            language="go",
            total_size=offset,
            alignment=max_align,
            fields=fields,
        )

    @classmethod
    def map_cross_language_types(cls, go_type: str) -> str:
        """Maps Go type to equivalent C and Python types."""
        mapping = {
            "int": "int64_t (C) / int (Python)",
            "int32": "int32_t (C) / int (Python)",
            "float64": "double (C) / float (Python)",
            "string": "const char* / len (C) / str (Python)",
            "bool": "bool (C) / bool (Python)",
            "byte": "uint8_t (C) / bytes (Python)",
        }
        return mapping.get(go_type, "void* (C) / Any (Python)")


# Global singleton helper
reverse_engineer_engine = ReverseEngineerEngine()

__all__ = [
    "StructField",
    "ReconstructedStruct",
    "ReverseEngineerEngine",
    "reverse_engineer_engine",
]
