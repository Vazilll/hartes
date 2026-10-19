# Domain Specification: Real-Time Vision & Clipboard Subsystem
**Module Path**: services/vision  
**Domain Lead Archetype**: azus-auto-reviewer / worker_implementer  
**Current Skill Rank**: Level 4 (WebSocket & WAL Visual Event Bus)  

## 1. Core Mission & Boundaries
### 1.1 Primary Mission
The Real-Time Vision & Clipboard Subsystem captures, deduplicates, and processes visual input from the Windows desktop. It provides Win32 clipboard bitmap interception (WM_CLIPBOARDUPDATE), local optical character recognition (RapidOCR), SHA-256 fingerprinting, terminal TUI previews, and real-time WebSocket event streaming (ws://127.0.0.1:8766/ws/vision).

### 1.2 Strict Boundary Rules
- **ALLOWED**:
  - Listening to Win32 WM_CLIPBOARDUPDATE (0x031D) events without stealing window focus.
  - SHA-256 fingerprinting and LRU deduplication (TTL cache) to prevent duplicate processing.
  - Local optical character recognition using RapidOCR and PIL.ImageGrab.
  - Broadcasting structured visual events over WebSocket (ws://127.0.0.1:8766/ws/vision).
  - Terminal-friendly ANSI rendering via TUIPreviewRenderer.
- **PROHIBITED**:
  - Calling iew_file on binary image files (.png, .jpg, .jpeg, .webp), which causes Gemini API stream freezes (empty content).
  - Storing uncompressed raw bitmaps in database records (must store SHA-256 and structured OCR/metadata).
  - Port collision on port 8765 (reserved for system_daemon; vision daemon must use 8766).
  - Blocking event loops on heavy OCR inference.

## 2. Public Typed Interface Contracts
### 2.1 Primary Classes & Signatures
`python
from typing import Dict, Any, Optional
from pathlib import Path

class ImageDeduplicator:
    def __init__(self, max_size: int = 100, ttl_seconds: float = 300.0) -> None: ...
    def is_duplicate(self, sha256_hash: str) -> bool: ...

class VisionPayloadGenerator:
    def __init__(self) -> None: ...
    def generate(self, source_input: Any, source_type: str = 'clipboard', file_path: Optional[str] = None) -> Dict[str, Any]: ...

class VazusVisionDaemon:
    def __init__(
        self,
        ws_host: str = '127.0.0.1',
        ws_port: int = 8766,
        workspace_dir: str = 'C:/vazus/labs/native_vision_system',
        db_path: str = 'C:/vazus/services/memory/vazus.db'
    ) -> None: ...
    async def start(self) -> None: ...
    def stop(self) -> None: ...
    def status(self) -> Dict[str, Any]: ...

def read_clipboard_ocr() -> None: ...
`

### 2.2 Invariant Guarantees
- Invariant 1: Zero image payload binary serialization into LLM tool responses (Anti-Freeze Safety).
- Invariant 2: SHA-256 deduplication rejects duplicate clipboard bitmaps within 300s TTL.
- Invariant 3: Vision WebSocket operates strictly on port 8766 (never colliding with 8765).
- Invariant 4: OCR extraction operations complete with fallback to NO_TEXT_FOUND on empty images.

## 3. Progressive Skill Level (Level 1..5) & Upgrade Criteria
- **Level 1 (CLI Clipboard Tool)**: Standalone Python script (clip_ocr.py) reading Windows clipboard on demand.  
  *Upgrade criteria*: Implement Win32 HWND clipboard event listener daemon.
- **Level 2 (Win32 Event Daemon)**: Background daemon capturing WM_CLIPBOARDUPDATE and filesystem image drops.  
  *Upgrade criteria*: Implement SHA-256 deduplication and TUI ANSI preview renderer.
- **Level 3 (Multimodal Resolver & RapidOCR)**: OCR extraction with confidence scores, SQLite logging, and file drop watching.  
  *Upgrade criteria*: Implement WebSocket event streaming and integration with LLM vision pipeline.
- **Level 4 (WebSocket & WAL Visual Event Bus)**: Real-time WebSocket server (ws://127.0.0.1:8766), LRU deduplication, multimodal payload generation, zero-freeze guarantee.  
  *Upgrade criteria*: Implement multi-modal visual grounding with sub-50ms processing.
- **Level 5 (Autonomous Visual Grounding Engine)**: Local NPU-accelerated sub-10ms visual segmentation, autonomous UI element bounding box detection, and interactive desktop navigation.

## 4. Known Bottlenecks & Optimization Backlog
- [ ] RapidOCR model loading latency on cold start.
- [ ] Win32 clipboard locked by other foreground applications during high-speed copying.
- [ ] Port 8766 WebSocket reconnect handling during daemon restarts.
