"""
vazus_core/kgb_analytical_extractor.py
KGB/FSB ИАД + ACH Analytical Extractor Engine for vazus SuperGraph OS.

Implements:
1. ИАД (Information-Analytical Diagnostics) scene/text decomposition into ThesisNode (facts, claims)
   and ProtocolNode (rules, procedures).
2. ACH (Analysis of Competing Hypotheses) matrix evaluation calculating weighted inconsistency scores
   and identifying conflicting statements (CONTRADICTS).
3. Edge relation detection: CAUSES, REQUIRES, CONTRADICTS, and BELONGS_TO.
4. 768D vector embedding persistence via UnifiedEmbeddingManager into kg_nodes and kg_edges in vazus.db and dnts.db.
"""

import os
import sys
import re
import json
import sqlite3
import hashlib
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Set, Union

# Import UnifiedEmbeddingManager from vazus_core.embeddings
try:
    from vazus_core.embeddings import UnifiedEmbeddingManager
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from vazus_core.embeddings import UnifiedEmbeddingManager

# Import text normalization from multimodal_knowledge if available
try:
    from vazus_core.multimodal_knowledge import normalize_russian_text
except ImportError:
    def normalize_russian_text(text: str) -> str:
        if not text:
            return ""
        text = re.sub(r'\[[^\]]*\]', ' ', text)
        text = re.sub(r'\(\s*(?:музыка|смех|аплодисменты|шум|кашель|вздох|пауза|тишина|laughter|music|applause)\s*\)', ' ', text, flags=re.I)
        text = text.replace('\xa0', ' ').replace('\u200b', '')
        return re.sub(r'\s+', ' ', text).strip()


DEFAULT_DB_PATH = r"C:\vazus\vazus.db"
SECONDARY_DB_PATH = r"C:\vazus\memory\dnts.db"
TERTIARY_DB_PATH = r"C:\vazus\services\memory\vazus.db"


class ThesisNode:
    """Represents an analytical claim, factual assertion, hypothesis, or scientific thesis."""
    def __init__(
        self,
        id: str,
        name: str,
        statement: str,
        confidence: float = 0.85,
        confidence_score: Optional[float] = None,
        domain: str = "kgb_analytics",
        node_type: str = "ThesisNode",
        ach_status: str = "HYPOTHESIS",
        evidence_sources: Optional[List[str]] = None,
        source_file: str = "",
        scene_id: str = "",
        start_sec: float = 0.0,
        end_sec: float = 0.0,
        tags: Union[str, List[str]] = "iad,thesis",
        properties: Optional[Dict[str, Any]] = None,
        embedding_json: Optional[str] = None,
        node_id: Optional[str] = None
    ):
        self.id = node_id or id
        self.node_id = self.id
        self.name = name
        self.statement = statement
        self.confidence = confidence_score if confidence_score is not None else confidence
        self.confidence_score = self.confidence
        self.domain = domain
        self.node_type = "ThesisNode"
        self.ach_status = ach_status
        self.evidence_sources = evidence_sources or []
        self.source_file = source_file
        self.scene_id = scene_id
        self.start_sec = start_sec
        self.end_sec = end_sec
        self.tags = tags if isinstance(tags, str) else ",".join(tags)
        self.properties = properties or {}
        self.embedding_json = embedding_json

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "node_id": self.id,
            "name": self.name,
            "statement": self.statement,
            "confidence": self.confidence,
            "confidence_score": self.confidence_score,
            "domain": self.domain,
            "node_type": "ThesisNode",
            "ach_status": self.ach_status,
            "evidence_sources": self.evidence_sources,
            "source_file": self.source_file,
            "scene_id": self.scene_id,
            "start_sec": self.start_sec,
            "end_sec": self.end_sec,
            "tags": self.tags,
            "properties": self.properties,
            "embedding_json": self.embedding_json
        }


class ProtocolNode:
    """Represents an operational directive, protocol, step-by-step algorithm, or procedure."""
    def __init__(
        self,
        id: str,
        name: str,
        action_instruction: str = "",
        steps: Optional[List[str]] = None,
        prerequisites: Optional[List[str]] = None,
        sequence_order: int = 1,
        target_outcome: str = "",
        frequency_periodicity: str = "",
        safety_warnings: Optional[List[str]] = None,
        domain: str = "kgb_analytics",
        node_type: str = "ProtocolNode",
        source_file: str = "",
        scene_id: str = "",
        start_sec: float = 0.0,
        end_sec: float = 0.0,
        tags: Union[str, List[str]] = "iad,protocol",
        properties: Optional[Dict[str, Any]] = None,
        embedding_json: Optional[str] = None,
        node_id: Optional[str] = None
    ):
        self.id = node_id or id
        self.node_id = self.id
        self.name = name
        self.action_instruction = action_instruction or (steps[0] if steps else name)
        self.steps = steps or ([self.action_instruction] if self.action_instruction else [])
        self.prerequisites = prerequisites or []
        self.sequence_order = sequence_order
        self.target_outcome = target_outcome
        self.frequency_periodicity = frequency_periodicity
        self.safety_warnings = safety_warnings or []
        self.domain = domain
        self.node_type = "ProtocolNode"
        self.source_file = source_file
        self.scene_id = scene_id
        self.start_sec = start_sec
        self.end_sec = end_sec
        self.tags = tags if isinstance(tags, str) else ",".join(tags)
        self.properties = properties or {}
        self.embedding_json = embedding_json

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "node_id": self.id,
            "name": self.name,
            "action_instruction": self.action_instruction,
            "steps": self.steps,
            "prerequisites": self.prerequisites,
            "sequence_order": self.sequence_order,
            "target_outcome": self.target_outcome,
            "frequency_periodicity": self.frequency_periodicity,
            "safety_warnings": self.safety_warnings,
            "domain": self.domain,
            "node_type": "ProtocolNode",
            "source_file": self.source_file,
            "scene_id": self.scene_id,
            "start_sec": self.start_sec,
            "end_sec": self.end_sec,
            "tags": self.tags,
            "properties": self.properties,
            "embedding_json": self.embedding_json
        }


class KGBAnalyticalExtractor:
    """
    KGB/FSB ИАД (Information-Analytical Diagnostics) + ACH (Analysis of Competing Hypotheses) Engine.
    Processes scene dicts or raw text, decomposes into ThesisNode and ProtocolNode entities,
    detects CAUSES, REQUIRES, CONTRADICTS, and BELONGS_TO edges, computes ACH matrices,
    generates 768D Gemini embeddings, and persists into SQLite SuperGraph databases.
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH, vector_dim: int = 768):
        self.db_path = db_path
        self.embedder = UnifiedEmbeddingManager(dimension=vector_dim)
        self._ensure_tables(self.db_path)

    def _ensure_tables(self, db_path: str):
        """Ensures kg_nodes and kg_edges tables exist in the specified SQLite database."""
        try:
            p = Path(db_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(db_path) as conn:
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
                """)
                conn.commit()
        except Exception as e:
            sys.stderr.write(f"[KGB Extractor] DB table initialization note for {db_path}: {e}\n")

    def decompose_text(
        self,
        text: str,
        source_file: str = "",
        scene_id: str = "",
        start_sec: float = 0.0,
        end_sec: float = 0.0
    ) -> Tuple[List[ThesisNode], List[ProtocolNode]]:
        """
        Decomposes transcript / text into atomic ThesisNode and ProtocolNode entities using ИАД principles.
        """
        theses: List[ThesisNode] = []
        protocols: List[ProtocolNode] = []

        if text is None:
            text = ""
        elif isinstance(text, (list, tuple)):
            text = " ".join(str(item) for item in text if item is not None)
        elif not isinstance(text, str):
            text = str(text)

        if not text or not text.strip():
            return theses, protocols

        normalized = normalize_russian_text(text)
        if not normalized:
            return theses, protocols

        # Sentence split handling multiline and punctuation boundaries
        sentences = re.split(r'(?<=[.!?])\s+|\n+', normalized)

        # Regex patterns for protocol directives
        protocol_patterns = [
            r'\bнеобходимо\b', r'\bследует\b', r'\bобязательно\b', r'\bшаг\b',
            r'\bправило\b', r'\bинструкция\b', r'\bрекомендуется\b', r'\bсделайте\b',
            r'\bпринимать\b', r'\bвыполните\b', r'\bиспользуйте\b', r'\bпротокол\b',
            r'\bдозировка\b', r'\bприменяйте\b', r'\bпринимайте\b', r'\bциклировани[ея]\b',
            r'\bmust\b', r'\bshould\b', r'\balways\b', r'\bprotocol\b', r'\bstep\b'
        ]

        # Periodicity / dosage extraction helpers
        freq_pattern = r'(\d+\s*(?:мг|г|мкг|МЕ|табл|капс|раз|недели|дней|минут|часов)\s*(?:в\s*день|ежедневно|перед\s*сном|в\s*течение|день|сутки|через)?|[0-9]+\s*недел[ьи]|\d+\s*дн[ейя])'

        for idx, sent in enumerate(sentences):
            sent_clean = sent.strip()
            if len(sent_clean) < 8:
                continue

            node_hash = hashlib.md5(f"{scene_id}:{sent_clean}".encode('utf-8')).hexdigest()[:8]

            is_protocol = any(re.search(pat, sent_clean, re.IGNORECASE) for pat in protocol_patterns)

            if is_protocol:
                freq_match = re.findall(freq_pattern, sent_clean, re.IGNORECASE)
                periodicity = ", ".join(freq_match) if freq_match else ""

                safety_match = re.findall(r'(?:предотвращения|во избежание|опасно|риск|побочн|осторожно)[^.!?]*', sent_clean, re.IGNORECASE)

                name_title = sent_clean[:50] + ("..." if len(sent_clean) > 50 else "")
                p_node = ProtocolNode(
                    id=f"protocol_{node_hash}",
                    name=name_title,
                    action_instruction=sent_clean,
                    steps=[sent_clean],
                    sequence_order=idx + 1,
                    frequency_periodicity=periodicity,
                    safety_warnings=safety_match,
                    source_file=source_file,
                    scene_id=scene_id,
                    start_sec=start_sec,
                    end_sec=end_sec,
                    tags="iad,protocol",
                    properties={"raw_sentence": sent_clean, "step_index": idx + 1}
                )
                protocols.append(p_node)

            # Note: A sentence can also yield a ThesisNode if it makes a factual claim
            # If it's not a protocol, or if it contains a declarative claim alongside protocol
            is_declarative = not is_protocol or re.search(r'\b(стимулирует|вызывает|приводит|снижает|повышает|является|подтверждают)\b', sent_clean, re.I)

            if is_declarative:
                conf = 0.85
                if re.search(r'\b(подтверждают|доказано|установлено|точно|100%|исследования)\b', sent_clean, re.I):
                    conf = 0.95
                elif re.search(r'\b(возможно|предположительно|вероятно|может|гипотеза)\b', sent_clean, re.I):
                    conf = 0.65

                name_title = sent_clean[:50] + ("..." if len(sent_clean) > 50 else "")
                t_node = ThesisNode(
                    id=f"thesis_{node_hash}",
                    name=name_title,
                    statement=sent_clean,
                    confidence=conf,
                    source_file=source_file,
                    scene_id=scene_id,
                    start_sec=start_sec,
                    end_sec=end_sec,
                    tags="iad,thesis",
                    properties={"raw_sentence": sent_clean, "sentence_index": idx + 1}
                )
                theses.append(t_node)

        return theses, protocols

    def extract_graph_edges(
        self,
        theses: List[ThesisNode],
        protocols: List[ProtocolNode],
        scene_id: str = ""
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Extracts graph relations:
        - BELONGS_TO (linking nodes to scene_id)
        - CAUSES (causal connections between theses or protocols, enforcing DAG acyclicity)
        - REQUIRES (prerequisite co-factors or sequence requirements)
        - CONTRADICTS (conflicting analytical statements)

        Returns tuple of (causes_edges, requires_edges, contradicts_edges, belongs_to_edges)
        """
        causes_edges: List[Dict[str, Any]] = []
        requires_edges: List[Dict[str, Any]] = []
        contradicts_edges: List[Dict[str, Any]] = []
        belongs_to_edges: List[Dict[str, Any]] = []

        if scene_id and (theses or protocols):
            if not any(t.id == scene_id for t in theses) and not any(p.id == scene_id for p in protocols):
                s_node = ThesisNode(
                    id=scene_id,
                    name=scene_id,
                    statement=f"Scene container {scene_id}",
                    confidence=1.0,
                    source_file=scene_id,
                    scene_id=scene_id,
                    tags="iad,scene",
                    properties={"scene_id": scene_id, "container": True}
                )
                theses.append(s_node)

        all_nodes = theses + protocols
        real_nodes = [n for n in all_nodes if not (getattr(n, 'properties', {}).get('container') or n.id == scene_id)]

        # 1. Structural BELONGS_TO edges
        if scene_id:
            for node in all_nodes:
                if node.id != scene_id:
                    belongs_to_edges.append({
                        "source_id": node.id,
                        "target_id": scene_id,
                        "relation": "BELONGS_TO",
                        "strength": 1.0,
                        "properties": {"scene_id": scene_id, "node_type": node.node_type}
                    })

        # 2. Sequential / Prerequisite REQUIRES edges between consecutive protocols
        for i in range(len(protocols) - 1):
            requires_edges.append({
                "source_id": protocols[i+1].id,
                "target_id": protocols[i].id,
                "relation": "REQUIRES",
                "strength": 0.90,
                "properties": {"type": "sequential_step", "prerequisite": protocols[i].name}
            })

        # Regex triggers
        causal_regex = re.compile(
            r'\b(приводит к|вызывает|вызывают|из-за|результатом является|способствует|влечет за собой|causes|leads to|results in|stimulates)\b',
            re.IGNORECASE
        )
        requires_regex = re.compile(
            r'\b(требует|необходимо|сопроводительный прием|предполагает наличие|при условии|обязательным условием|requires|prerequisite|depends on)\b',
            re.IGNORECASE
        )
        contradict_regex = re.compile(
            r'\b(в отличие от|ошибочно|заблуждение|противоречит|напротив|опровергает|наоборот|вместо того чтобы|contradicts|opposes|inconsistent)\b',
            re.IGNORECASE
        )

        # Build causal DAG graph tracker for cycle detection
        causal_adj: Dict[str, Set[str]] = {}

        def has_path(src: str, dst: str, visited: Optional[Set[str]] = None) -> bool:
            """DFS cycle check: returns True if path exists from src to dst."""
            if visited is None:
                visited = set()
            if src == dst:
                return True
            visited.add(src)
            for nxt in causal_adj.get(src, set()):
                if nxt not in visited:
                    if has_path(nxt, dst, visited):
                        return True
            return False

        # Single node check for internal causes / requires / contradicts if multiple nodes are present
        for i, n1 in enumerate(all_nodes):
            text1 = n1.statement if isinstance(n1, ThesisNode) else n1.action_instruction

            # Check explicit REQUIRES in node text
            if requires_regex.search(text1):
                found_match = False
                for j, n2 in enumerate(all_nodes):
                    if i == j:
                        continue
                    text2 = n2.statement if isinstance(n2, ThesisNode) else n2.action_instruction
                    words2 = [w.lower() for w in re.findall(r'\b[А-Яа-яA-Za-z0-9]{3,}\b', text2) if w.lower() not in ("для", "при", "или", "что", "как", "без", "этом")]
                    if any(w in text1.lower() for w in words2):
                        requires_edges.append({
                            "source_id": n1.id,
                            "target_id": n2.id,
                            "relation": "REQUIRES",
                            "strength": 0.85,
                            "properties": {"prerequisite_statement": text2}
                        })
                        found_match = True

                # If no other node matched or for sub-sentence prerequisite extraction
                if not found_match or len(all_nodes) == 1:
                    parts = requires_regex.split(text1)
                    if len(parts) >= 3:
                        target_part, trigger, prereq_part = parts[0].strip(), parts[1].strip(), parts[2].strip()
                        r_hash2 = hashlib.md5(f"{scene_id}:{prereq_part}".encode('utf-8')).hexdigest()[:8]
                        prereq_node_id = f"protocol_{r_hash2}"

                        if not any(p.id == prereq_node_id for p in protocols) and not any(t.id == prereq_node_id for t in theses):
                            p_virtual = ProtocolNode(
                                id=prereq_node_id,
                                name=prereq_part[:50] + ("..." if len(prereq_part) > 50 else ""),
                                action_instruction=prereq_part,
                                steps=[prereq_part],
                                source_file=n1.source_file,
                                scene_id=scene_id,
                                start_sec=n1.start_sec,
                                end_sec=n1.end_sec,
                                tags="iad,protocol,virtual",
                                properties={"raw_sentence": prereq_part, "virtual": True}
                            )
                            protocols.append(p_virtual)
                            if scene_id:
                                belongs_to_edges.append({
                                    "source_id": p_virtual.id,
                                    "target_id": scene_id,
                                    "relation": "BELONGS_TO",
                                    "strength": 1.0,
                                    "properties": {"scene_id": scene_id, "node_type": p_virtual.node_type}
                                })

                        requires_edges.append({
                            "source_id": n1.id,
                            "target_id": prereq_node_id,
                            "relation": "REQUIRES",
                            "strength": 0.90,
                            "properties": {"target": target_part, "trigger": trigger, "prerequisite": prereq_part}
                        })

            # Check explicit CAUSES within single node text or across nodes
            if causal_regex.search(text1) and (len(all_nodes) == 1 or len(real_nodes) <= 1):
                # Sub-sentence split for causal relation in single sentence
                parts = causal_regex.split(text1)
                if len(parts) >= 3:
                    cause_part, trigger, effect_part = parts[0].strip(), parts[1].strip(), parts[2].strip()
                    c_hash1 = hashlib.md5(f"{scene_id}:{cause_part}".encode('utf-8')).hexdigest()[:8]
                    c_hash2 = hashlib.md5(f"{scene_id}:{effect_part}".encode('utf-8')).hexdigest()[:8]
                    cause_node_id = f"thesis_{c_hash1}"
                    effect_node_id = f"thesis_{c_hash2}"

                    if not any(t.id == cause_node_id for t in theses) and not any(p.id == cause_node_id for p in protocols):
                        t_cause = ThesisNode(
                            id=cause_node_id,
                            name=cause_part[:50] + ("..." if len(cause_part) > 50 else ""),
                            statement=cause_part,
                            confidence=0.85,
                            source_file=n1.source_file,
                            scene_id=scene_id,
                            start_sec=n1.start_sec,
                            end_sec=n1.end_sec,
                            tags="iad,thesis,virtual",
                            properties={"raw_sentence": cause_part, "virtual": True}
                        )
                        theses.append(t_cause)
                        if scene_id:
                            belongs_to_edges.append({
                                "source_id": t_cause.id,
                                "target_id": scene_id,
                                "relation": "BELONGS_TO",
                                "strength": 1.0,
                                "properties": {"scene_id": scene_id, "node_type": t_cause.node_type}
                            })

                    if not any(t.id == effect_node_id for t in theses) and not any(p.id == effect_node_id for p in protocols):
                        t_effect = ThesisNode(
                            id=effect_node_id,
                            name=effect_part[:50] + ("..." if len(effect_part) > 50 else ""),
                            statement=effect_part,
                            confidence=0.85,
                            source_file=n1.source_file,
                            scene_id=scene_id,
                            start_sec=n1.start_sec,
                            end_sec=n1.end_sec,
                            tags="iad,thesis,virtual",
                            properties={"raw_sentence": effect_part, "virtual": True}
                        )
                        theses.append(t_effect)
                        if scene_id:
                            belongs_to_edges.append({
                                "source_id": t_effect.id,
                                "target_id": scene_id,
                                "relation": "BELONGS_TO",
                                "strength": 1.0,
                                "properties": {"scene_id": scene_id, "node_type": t_effect.node_type}
                            })

                    causes_edges.append({
                        "source_id": cause_node_id,
                        "target_id": effect_node_id,
                        "relation": "CAUSES",
                        "strength": 0.90,
                        "properties": {"cause": cause_part, "trigger": trigger, "effect": effect_part}
                    })

            for j, n2 in enumerate(all_nodes):
                if i >= j:
                    continue
                text2 = n2.statement if isinstance(n2, ThesisNode) else n2.action_instruction

                # Skip container nodes (e.g. scene container) for relational edge detection
                if getattr(n1, 'properties', {}).get('container') or getattr(n2, 'properties', {}).get('container') or n1.id == scene_id or n2.id == scene_id:
                    continue

                # CAUSES detection between nodes
                if causal_regex.search(text1) or causal_regex.search(text2):
                    src_node, dst_node = (n1, n2) if causal_regex.search(text1) else (n2, n1)
                    if not has_path(dst_node.id, src_node.id):
                        causal_edges_item = {
                            "source_id": src_node.id,
                            "target_id": dst_node.id,
                            "relation": "CAUSES",
                            "strength": 0.85,
                            "properties": {"trigger": "causal_keyword"}
                        }
                        causes_edges.append(causal_edges_item)
                        if src_node.id not in causal_adj:
                            causal_adj[src_node.id] = set()
                        causal_adj[src_node.id].add(dst_node.id)

                # CONTRADICTS detection between nodes
                is_contradiction = False
                words1 = set(w.lower() for w in re.findall(r'\b[А-Яа-яA-Za-z0-9]{4,}\b', text1))
                words2 = set(w.lower() for w in re.findall(r'\b[А-Яа-яA-Za-z0-9]{4,}\b', text2))
                overlap = words1.intersection(words2)

                if contradict_regex.search(text1) or contradict_regex.search(text2):
                    if len(overlap) >= 1 or len(all_nodes) <= 3:
                        is_contradiction = True
                else:
                    if len(overlap) >= 2:
                        neg1 = bool(re.search(r'\b(не|без|отсутствие|ошибочно|заблуждение|опасно|противоречит)\b', text1, re.I))
                        neg2 = bool(re.search(r'\b(не|без|отсутствие|ошибочно|заблуждение|опасно|противоречит)\b', text2, re.I))
                        if neg1 != neg2:
                            is_contradiction = True

                if is_contradiction:
                    if contradict_regex.search(text2) and not contradict_regex.search(text1):
                        c_src, c_dst = n2.id, n1.id
                    else:
                        c_src, c_dst = n1.id, n2.id
                    contradicts_edges.append({
                        "source_id": c_src,
                        "target_id": c_dst,
                        "relation": "CONTRADICTS",
                        "strength": 0.95,
                        "properties": {"reason": "opposing_claims_or_negation"}
                    })

        return causes_edges, requires_edges, contradicts_edges, belongs_to_edges

    def extract(self, scene_or_text_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes input scene / text dictionary and executes ИАД + ACH extraction pipeline.
        """
        if not isinstance(scene_or_text_dict, dict):
            if isinstance(scene_or_text_dict, str):
                scene_or_text_dict = {"transcript": scene_or_text_dict}
            else:
                scene_or_text_dict = {"transcript": str(scene_or_text_dict or "")}

        raw_scene_id = scene_or_text_dict.get("scene_id")
        scene_id = str(raw_scene_id) if raw_scene_id else f"scene_{hashlib.md5(str(time.time()).encode()).hexdigest()[:8]}"
        source_file = str(scene_or_text_dict.get("source_file", "") or "")

        try:
            start_sec = float(scene_or_text_dict.get("start_sec", 0.0))
        except (TypeError, ValueError):
            start_sec = 0.0

        try:
            end_sec = float(scene_or_text_dict.get("end_sec", 0.0))
        except (TypeError, ValueError):
            end_sec = 0.0

        text = scene_or_text_dict.get("transcript")
        if text is None:
            text = scene_or_text_dict.get("text")
        if text is None:
            text = scene_or_text_dict.get("content")
        if text is None:
            text = ""

        # 1. ИАД text decomposition
        theses, protocols = self.decompose_text(
            text=text,
            source_file=source_file,
            scene_id=scene_id,
            start_sec=start_sec,
            end_sec=end_sec
        )

        # 2. Relation edge extraction
        causes_edges, requires_edges, contradicts_edges, belongs_to_edges = self.extract_graph_edges(
            theses=theses,
            protocols=protocols,
            scene_id=scene_id
        )

        # 3. ACH matrix evaluation
        input_hypotheses = scene_or_text_dict.get("hypotheses", [])
        if not isinstance(input_hypotheses, list):
            if isinstance(input_hypotheses, str):
                input_hypotheses = [{"id": "H1", "label": input_hypotheses}]
            elif isinstance(input_hypotheses, dict):
                input_hypotheses = [input_hypotheses]
            else:
                input_hypotheses = []

        if not input_hypotheses and theses:
            valid_theses = [t for t in theses if not (getattr(t, 'properties', {}).get('container') or t.id == scene_id or "scene" in getattr(t, 'tags', ''))]
            input_hypotheses = [{"id": t.id, "label": t.statement} for t in (valid_theses[:5] if valid_theses else theses[:5])]

        ach_summary = evaluate_ach_hypotheses(hypotheses=input_hypotheses, evidence=theses)

        # Update theses ACH status based on evaluation
        status_map = {r["hypothesis_id"]: r["ach_status"] for r in ach_summary.get("ranked_hypotheses", [])}
        for t in theses:
            if t.id in status_map:
                t.ach_status = status_map[t.id]

        # Update disproved status if node is target of CONTRADICTS or part of mutually contradictory pair
        for edge in contradicts_edges:
            src_id = edge.get("source_id")
            dst_id = edge.get("target_id")

            src_node = next((t for t in theses if t.id == src_id), None)
            dst_node = next((t for t in theses if t.id == dst_id), None)

            if src_node and dst_node:
                # dst_node is the target claim contradicted by src_node
                if src_node.confidence >= dst_node.confidence:
                    dst_node.ach_status = "REJECTED"
                    if src_node.ach_status in ("REJECTED", "HYPOTHESIS"):
                        src_node.ach_status = "ACCEPTED"
                else:
                    src_node.ach_status = "REJECTED"
                    if dst_node.ach_status in ("REJECTED", "HYPOTHESIS"):
                        dst_node.ach_status = "ACCEPTED"
            elif dst_node:
                dst_node.ach_status = "REJECTED"

        # 4. Format outputs
        thesis_nodes_dicts = [t.to_dict() for t in theses]
        protocol_nodes_dicts = [p.to_dict() for p in protocols]
        all_nodes_dicts = thesis_nodes_dicts + protocol_nodes_dicts
        all_edges_dicts = causes_edges + requires_edges + contradicts_edges + belongs_to_edges

        result = {
            "scene_id": scene_id,
            "source_file": source_file,
            "theses_extracted": len(theses),
            "protocols_extracted": len(protocols),
            "edges_extracted": len(all_edges_dicts),
            "thesis_nodes": thesis_nodes_dicts,
            "protocol_nodes": protocol_nodes_dicts,
            "causes_edges": causes_edges,
            "requires_edges": requires_edges,
            "contradicts_edges": contradicts_edges,
            "belongs_to_edges": belongs_to_edges,
            "nodes": all_nodes_dicts,
            "edges": all_edges_dicts,
            "ach_matrix_summary": ach_summary,
            "status": "SUCCESS"
        }

        # 5. Persist nodes and edges to SQLite SuperGraph databases
        persisted_count = self.persist(result)
        result["persisted_counts"] = {"total_entities": persisted_count}

        return result

    def persist(self, extraction_result: Dict[str, Any], db_path: Optional[str] = None) -> int:
        target_path = db_path or self.db_path
        return persist_kgb_analytics_to_supergraph(extraction_result, db_path=target_path)


def evaluate_ach_hypotheses(
    hypotheses: List[Dict[str, Any]],
    evidence: List[Union[Dict[str, Any], ThesisNode]]
) -> Dict[str, Any]:
    """
    Evaluates an Analysis of Competing Hypotheses (ACH) matrix.
    Calculates weighted inconsistency scores IS(H_j) for each hypothesis against evidence nodes.
    Ranks hypotheses (favoring those with the fewest contradictions) and identifies rejected hypotheses.

    Args:
      hypotheses: List of dicts, e.g. [{"id": "H1", "label": "..."}, ...]
      evidence: List of dicts or ThesisNode objects.

    Returns:
      Dict with keys: matrix, inconsistency_scores, ranked_hypotheses, contradictions_detected
    """
    matrix = []
    scores: Dict[str, float] = {}
    contradictions_detected: List[Dict[str, Any]] = []

    if not isinstance(hypotheses, list):
        if isinstance(hypotheses, str):
            hypotheses = [{"id": "H1", "label": hypotheses}]
        elif isinstance(hypotheses, dict):
            hypotheses = [hypotheses]
        else:
            hypotheses = []

    sanitized_hypotheses: List[Dict[str, Any]] = []
    for i, h in enumerate(hypotheses):
        if isinstance(h, str):
            sanitized_hypotheses.append({"id": f"H{i+1}", "label": h})
        elif isinstance(h, dict):
            h_copy = dict(h)
            if "id" not in h_copy or not h_copy["id"]:
                h_copy["id"] = f"H{i+1}"
            if "label" not in h_copy or not h_copy["label"]:
                h_copy["label"] = str(h_copy.get("statement") or h_copy.get("name") or str(h_copy))
            sanitized_hypotheses.append(h_copy)
        else:
            sanitized_hypotheses.append({"id": f"H{i+1}", "label": str(h)})
    hypotheses = sanitized_hypotheses

    ev_list: List[Dict[str, Any]] = []
    if isinstance(evidence, list):
        for ev in evidence:
            if isinstance(ev, ThesisNode):
                ev_list.append(ev.to_dict())
            elif isinstance(ev, dict):
                ev_list.append(ev)

    for h in hypotheses:
        h_id = h.get("id") or h.get("label", "H_unknown")
        scores[h_id] = 0.0

    neg_words = re.compile(r'\b(не|без|отсутствие|против|опасн\w*|ошибочн\w*|заблужден\w*|неэффективн\w*|противореч\w*|опроверг\w*|вредн\w*|not|no|harmful|inconsistent|contradict\w*)\b', re.I)

    for ev in ev_list:
        ev_id = ev.get("id") or ev.get("node_id", "E_unknown")
        ev_stmt = ev.get("statement") or ev.get("name") or ev.get("description") or ""
        ev_conf = float(ev.get("confidence") or ev.get("confidence_score") or 0.85)

        row = {
            "evidence_id": ev_id,
            "evidence_statement": ev_stmt,
            "confidence": ev_conf,
            "ratings": {}
        }

        ev_words = set(w.lower() for w in re.findall(r'\b[А-Яа-яA-Za-z0-9]{4,}\b', ev_stmt))

        for h in hypotheses:
            h_id = h.get("id") or h.get("label", "H_unknown")
            h_label = h.get("label") or h.get("statement") or h.get("name") or ""
            h_words = set(w.lower() for w in re.findall(r'\b[А-Яа-яA-Za-z0-9]{4,}\b', h_label))

            overlap = ev_words.intersection(h_words)

            if len(overlap) >= 1:
                ev_has_neg = bool(neg_words.search(ev_stmt))
                h_has_neg = bool(neg_words.search(h_label))

                if ev_has_neg != h_has_neg:
                    rating = -1.0
                    scores[h_id] += ev_conf * 1.0
                    contradictions_detected.append({
                        "evidence_id": ev_id,
                        "hypothesis_id": h_id,
                        "evidence_statement": ev_stmt,
                        "hypothesis_label": h_label,
                        "inconsistency_weight": ev_conf
                    })
                else:
                    rating = 1.0
            else:
                rating = 0.0

            row["ratings"][h_id] = rating

        matrix.append(row)

    sorted_h = sorted(scores.items(), key=lambda x: x[1])
    min_score = sorted_h[0][1] if sorted_h else 0.0
    max_score = sorted_h[-1][1] if sorted_h else 0.0

    ranked = []
    first_accepted = False
    for h_id, score in sorted_h:
        if score == min_score:
            if not first_accepted or min_score == 0.0:
                status = "ACCEPTED"
                first_accepted = True
            else:
                status = "REJECTED"
        elif score == max_score and len(sorted_h) > 1 and max_score > min_score:
            status = "DISPROVED"
        else:
            status = "REJECTED"

        ranked.append({
            "hypothesis_id": h_id,
            "inconsistency_score": round(score, 4),
            "ach_status": status
        })

    return {
        "matrix": matrix,
        "inconsistency_scores": {k: round(v, 4) for k, v in scores.items()},
        "ranked_hypotheses": ranked,
        "contradictions_detected": contradictions_detected
    }


def extract_kgb_analytics(
    scene_or_text_dict: Dict[str, Any],
    db_path: str = DEFAULT_DB_PATH
) -> Dict[str, Any]:
    """
    Main export function: extracts KGB/FSB ИАД analytics and ACH matrix evaluations
    from scene or text dict, generates 768D vector embeddings, and persists into SuperGraph databases.

    Args:
      scene_or_text_dict: Dict containing transcript/text, optional scene_id, source_file, hypotheses, etc.
      db_path: Primary SQLite database path (default "C:\\vazus\\vazus.db").

    Returns:
      Dict with extracted nodes, edges, ACH evaluation summary, and persistence status.
    """
    if isinstance(scene_or_text_dict, str):
        scene_or_text_dict = {"transcript": scene_or_text_dict}

    extractor = KGBAnalyticalExtractor(db_path=db_path)
    return extractor.extract(scene_or_text_dict)


def persist_kgb_analytics_to_supergraph(
    extraction_result: Dict[str, Any],
    db_path: str = DEFAULT_DB_PATH
) -> int:
    """
    Persists extracted ThesisNode, ProtocolNode entities and CAUSES, REQUIRES, CONTRADICTS, BELONGS_TO edges
    into SQLite tables kg_nodes and kg_edges across vazus.db and dnts.db.

    Generates 768D vector embeddings via UnifiedEmbeddingManager.

    Returns:
      Total number of entity records inserted/updated.
    """
    embedder = UnifiedEmbeddingManager(dimension=768)

    nodes = extraction_result.get("nodes", [])
    if not nodes:
        nodes = extraction_result.get("thesis_nodes", []) + extraction_result.get("protocol_nodes", [])

    edges = extraction_result.get("edges", [])
    if not edges:
        edges = (
            extraction_result.get("causes_edges", []) +
            extraction_result.get("requires_edges", []) +
            extraction_result.get("contradicts_edges", []) +
            extraction_result.get("belongs_to_edges", [])
        )

    target_dbs = [db_path, SECONDARY_DB_PATH]
    tertiary_parent = Path(TERTIARY_DB_PATH).parent
    if tertiary_parent.exists():
        target_dbs.append(TERTIARY_DB_PATH)

    total_inserted = 0

    for dbp in set(target_dbs):
        try:
            p = Path(dbp)
            p.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(dbp) as conn:
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
                """)

                # Insert nodes
                for n in nodes:
                    node_id = n.get("id") or n.get("node_id")
                    name = n.get("name") or node_id
                    domain = n.get("domain", "kgb_analytics")
                    node_type = n.get("node_type", "ThesisNode")
                    desc = n.get("statement") or n.get("action_instruction") or name
                    tags = n.get("tags")
                    if isinstance(tags, list):
                        tags = ",".join(tags)

                    emb = embedder.get_embedding(f"{name} {desc}")
                    emb_json = json.dumps(emb)

                    props = n.get("properties") or {}
                    props["confidence"] = n.get("confidence") or n.get("confidence_score")
                    props["ach_status"] = n.get("ach_status")
                    props["steps"] = n.get("steps")
                    props["frequency_periodicity"] = n.get("frequency_periodicity")
                    props_json = json.dumps(props, ensure_ascii=False)

                    conn.execute("""
                        INSERT OR REPLACE INTO kg_nodes
                        (id, name, domain, node_type, description, tags, properties, embedding_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (node_id, name, domain, node_type, desc, tags, props_json, emb_json))
                    total_inserted += 1

                # Insert edges
                for e in edges:
                    src = e.get("source_id")
                    dst = e.get("target_id")
                    rel = e.get("relation")
                    strength = float(e.get("strength", 1.0))
                    eprops = e.get("properties") or {}
                    eprops_json = json.dumps(eprops, ensure_ascii=False)

                    if src and dst and rel:
                        conn.execute("""
                            INSERT OR REPLACE INTO kg_edges
                            (source_id, target_id, relation, strength, properties)
                            VALUES (?, ?, ?, ?, ?)
                        """, (src, dst, rel, strength, eprops_json))
                        total_inserted += 1

                conn.commit()
        except Exception as err:
            sys.stderr.write(f"[KGB Extractor] Persistence warning for {dbp}: {err}\n")

    return total_inserted


if __name__ == "__main__":
    sample_data = {
        "scene_id": "scene_demo_01",
        "transcript": "Высокие дозы Витамина D3 стимулируют синтез остеокальцина. Приём Витамина D3 требует обязательного приёма Витамина K2 и Магния.",
        "hypotheses": [
            {"id": "H1", "label": "Витамин D3 стимулирует остеокальцин"},
            {"id": "H2", "label": "Витамин D3 не стимулирует остеокальцин"}
        ]
    }
    output = extract_kgb_analytics(sample_data)
    print("Extracted output status:", output["status"])
    print("Theses count:", output["theses_extracted"])
    print("Protocols count:", output["protocols_extracted"])
    print("Edges count:", output["edges_extracted"])
    print("Persisted count:", output["persisted_counts"])
