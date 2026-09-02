"""
vazus_core.integrations.vault_graph_canvas
Obsidian Visual Canvas & Knowledge Graph Synthesis Engine (Milestone 2 & SOTA 2026).
Generates interactive Obsidian .canvas JSON files connecting academic courses,
voice thought streams, and 768D semantic memory facts.
"""

import logging
import json
import math
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger("vault_graph_canvas")

from vazus_core.engine.config import settings
from vazus_core.memory.db import get_db_connection


def _create_canvas_node(
    node_id: str,
    text: str,
    x: int,
    y: int,
    *,
    width: int = 260,
    height: int = 140,
    color: str = "1",
    node_type: str = "text"
) -> Dict[str, Any]:
    """Helper to create a single Obsidian Canvas node dictionary."""
    return {
        "id": node_id,
        "type": node_type,
        "text": text,
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "color": color
    }


def _create_canvas_edge(
    edge_id: str,
    from_node: str,
    to_node: str,
    label: str = "",
    color: str = "1"
) -> Dict[str, Any]:
    """Helper to create a directed edge between two Canvas nodes."""
    return {
        "id": edge_id,
        "fromNode": from_node,
        "fromSide": "right",
        "toNode": to_node,
        "toSide": "left",
        "label": label,
        "color": color
    }


class VaultGraphCanvasGenerator:
    """Generates visual Obsidian .canvas maps from database facts and academic schedule."""

    def __init__(self, db_path: Optional[str] = None):
        env_db = os.environ.get("VAZUS_DB_PATH")
        self.db_path = str(db_path or env_db or settings.VAZUS_DB_PATH)

    def generate_academic_canvas(self, schedule_data: Dict[str, Any]) -> Dict[str, Any]:
        """Builds an Obsidian Canvas linking group, courses, teachers, and exam milestones."""
        nodes = []
        edges = []

        group_name = schedule_data.get("group_name", "ИКБО-01-23")
        # Root node
        nodes.append(_create_canvas_node("root_group", f"🎓 **Группа {group_name}**\nРасписание & Дедлайны", 0, 200, width=240, height=100, color="5"))

        schedule_items = schedule_data.get("schedule", [])
        milestones = schedule_data.get("milestones", [])

        # Add course nodes in a circular layout
        num_items = len(schedule_items)
        for i, item in enumerate(schedule_items):
            angle = (2 * math.pi / max(num_items, 1)) * i
            x = int(350 + 280 * math.cos(angle))
            y = int(200 + 240 * math.sin(angle))
            
            node_id = f"course_{i}"
            subject = item.get("subject", "Предмет")
            teacher = item.get("teacher", "Преподаватель")
            time_slot = item.get("lesson_time", "")
            weekday = item.get("weekday", "")
            classroom = item.get("classroom", "")

            text = f"📚 **{subject}**\n{weekday} {time_slot}\n👨‍🏫 {teacher}\n📍 Ауд. {classroom}"
            nodes.append(_create_canvas_node(node_id, text, x, y, color="2"))
            edges.append(_create_canvas_edge(f"e_root_{i}", "root_group", node_id, label=weekday[:2]))

        # Add milestone nodes on the right
        for j, m in enumerate(milestones):
            m_id = f"milestone_{j}"
            m_subject = m.get("subject", "")
            m_title = m.get("milestone_name", "")
            due_date = m.get("due_date", "")
            status = m.get("status", "PENDING")

            text = f"🎯 **{m_title}**\n📖 {m_subject}\n⏰ Дедлайн: {due_date}\nСтатус: {status}"
            nodes.append(_create_canvas_node(m_id, text, 800, j * 160, width=280, height=130, color="4"))

            # Link milestone to matching course
            for i, item in enumerate(schedule_items):
                if item.get("subject") == m_subject:
                    edges.append(_create_canvas_edge(f"e_m_{j}_{i}", f"course_{i}", m_id, label="Экзамен/Зачёт", color="4"))
                    break

        return {"nodes": nodes, "edges": edges}

    def generate_memory_facts_canvas(self, limit: int = 15) -> Dict[str, Any]:
        """Constructs a Canvas from latest memory_facts_v2 in SQLite."""
        nodes = []
        edges = []
        conn = None
        try:
            conn = get_db_connection(self.db_path)
            cur = conn.cursor()
            cols = [c[1] for c in cur.execute("PRAGMA table_info(memory_facts_v2)").fetchall()]
            text_col = "fact_text" if "fact_text" in cols else "statement"
            domain_col = "provenance" if "provenance" in cols else "source_domain"
            id_col = "id" if "id" in cols else "node_id"
            rows = cur.execute(f"""
            SELECT {id_col}, category, {text_col}, confidence, {domain_col}
            FROM memory_facts_v2
            ORDER BY created_at DESC
            LIMIT ?
            """, (limit,)).fetchall()

            # Center hub
            nodes.append(_create_canvas_node("hub_memory", "🧠 **Vazus SuperGraph Memory**\n768D Векторные факты", 0, 300, width=240, height=100, color="6"))

            for i, r in enumerate(rows):
                node_id = f"fact_{i}"
                category = r[1]
                statement = r[2]
                domain = r[4] or "general"

                x = int(350 + (i % 4) * 300)
                y = int((i // 4) * 180)

                text = f"💡 **{category.upper()}**\n{statement[:140]}...\n🏷️ *{domain}*"
                nodes.append(_create_canvas_node(node_id, text, x, y, width=280, height=140, color="3"))
                edges.append(_create_canvas_edge(f"e_fact_{i}", "hub_memory", node_id, label=category))

        except Exception as e:
            logger.debug("Failed building memory facts canvas: %s", e)
            nodes.append(_create_canvas_node("hub_empty", "🧠 **Memory Hub**\nНет записей в базе", 0, 0, color="1"))
        finally:
            if conn:
                try:
                    conn.close()
                except Exception as ce:
                    logger.debug("db close error: %s", ce)

        return {"nodes": nodes, "edges": edges}

    def export_canvas_to_file(self, canvas_data: Dict[str, Any], output_path: str) -> str:
        """Serializes Canvas dictionary to JSON file."""
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(canvas_data, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(p)
