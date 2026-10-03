"""
services.data_fabric.entity_schema
==================================
Canonical Pydantic entity definitions ("truth tables") for Vazus App Engine VAE 2.0.
Acts as Single Source of Truth for Auto-CRUD generation, Data Fabric API, and UI bindings.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AcademicDebtEntity(BaseModel):
    """Academic debt milestone in RTU MIREA curriculum (18 debts baseline)."""
    id: int
    subject: str
    teacher: str = "Кафедра КИТПиПИ"
    type: str = "Лабораторная"
    room: str = "А-10"
    next: str = "Сдача на паре"
    status: str = "PENDING"  # PENDING, В процессе, Готово к сдаче, Сдано
    stage1_deadline: str = "15.10.2026"
    moodle_course_id: Optional[str] = None
    semester: Optional[str] = "3"


class ScheduleSlotEntity(BaseModel):
    """Weekly academic timetable slot."""
    id: int
    weekday: str
    time: str
    subject: str
    teacher: str
    room: str
    type: str = "Семинар"
    urgent: bool = False


class KnowledgeNodeEntity(BaseModel):
    """Concept node in the MAGMA knowledge graph."""
    id: str
    name: str
    domain: str = "core"
    node_type: str = "concept"
    description: str = ""
    tags: List[str] = Field(default_factory=list)
    salience: float = 1.0


class OrganicInsightEntity(BaseModel):
    """Durable insight entry in the organic_insights ledger."""
    id: Optional[int] = None
    category: str
    insight: str
    node_id: Optional[str] = None
    created_at: Optional[str] = None
    timestamp: Optional[float] = None
