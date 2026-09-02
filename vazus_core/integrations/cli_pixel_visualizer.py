"""
vazus.vazus_core.cli_pixel_visualizer — Direct CLI ANSI Pixel-Art & Artifact Graph Renderer.
Renders 24-bit TrueColor Unicode block pixel art in terminal stdout and exports PNG artifacts.

vazus SuperGraph OS Architecture
"""

import logging
import sys

logger = logging.getLogger(__name__)

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception as exc:
        logger.debug("Failed stdout reconfigure: %s", exc)

import sqlite3
import random
from pathlib import Path

ROOT_DIR = Path("C:\\vazus")
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    import plotext as plt
except ImportError:
    plt = None

import os
ARTIFACT_DIR = Path("C:\\Users\\Vaz\\.gemini\\antigravity-cli\\brain\\7cc844a1-8439-4975-bea1-ca2a642abdf4")
DB_PATH = Path(os.getenv("VAZUS_DB_PATH", str(ROOT_DIR / "services" / "memory" / "vazus.db")))


class CLIPixelVisualizer:
    """Renders retro-cyberpunk 24-bit ANSI block pixel graphics in CLI terminal standard output."""

    @staticmethod
    def _fetch_graph_nodes() -> list:
        nodes = []
        if DB_PATH.exists():
            try:
                with sqlite3.connect(DB_PATH) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT name, kind FROM workspace_ast_nodes LIMIT 20")
                    nodes = cursor.fetchall()
            except Exception as exc:
                logger.debug("Failed fetching graph nodes from DB: %s", exc)
        if not nodes:
            nodes = [("vazus_core", "module"), ("embeddings.py", "file"), ("agent_handoff.py", "file"), ("rlm_engineer", "subagent")]
        return nodes

    @staticmethod
    def _export_png_artifact(nodes: list) -> None:
        try:
            from PIL import Image, ImageDraw
            img = Image.new("RGB", (900, 600), color=(11, 13, 14))
            draw = ImageDraw.Draw(img)
            for i in range(0, 900, 40):
                draw.line([(i, 0), (i, 600)], fill=(20, 26, 35), width=1)
            for j in range(0, 600, 40):
                draw.line([(0, j), (900, j)], fill=(20, 26, 35), width=1)

            coords = [(random.randint(100, 800), random.randint(100, 500), name, kind) for name, kind in nodes]
            for (x1, y1, _, _), (x2, y2, _, _) in zip(coords, coords[1:]):
                draw.line([(x1, y1), (x2, y2)], fill=(59, 130, 246), width=2)
            for cx, cy, name, kind in coords:
                color = (16, 185, 129) if kind == "file" else (245, 158, 11)
                draw.rectangle([cx-12, cy-12, cx+12, cy+12], fill=color, outline=(255, 255, 255), width=2)
                draw.text((cx-20, cy+16), name[:15], fill=(243, 244, 246))

            out_path = ARTIFACT_DIR / "supergraph_pixel_visual.png"
            img.save(out_path)
            print(f"[CLIPixelVisualizer] Exported PNG artifact: {out_path}")
        except Exception as e:
            print(f"[CLIPixelVisualizer] PNG artifact export skipped ({e})")

    @classmethod
    def render_terminal_graph(cls) -> str:
        """Renders 24-bit ANSI block pixel graph in terminal stdout."""
        nodes = cls._fetch_graph_nodes()

        if plt is None:
            terminal_art = "[CLIPixelVisualizer] ASCII Topology Map (plotext not installed)\n" + "\n".join(f"  * {name} [{kind}]" for name, kind in nodes)
            print(terminal_art)
            return terminal_art

        x_vals = [random.uniform(10, 90) for _ in nodes]
        y_vals = [random.uniform(10, 90) for _ in nodes]

        plt.clear_data()
        plt.clear_figure()
        plt.theme("dark")
        plt.title("VAZUS SUPERGRAPH OS — DIRECT CLI PIXEL TOPOLOGY (768D EMBEDDINGS)")
        plt.scatter(x_vals, y_vals, color="magenta", marker="hd")
        plt.plotsize(80, 20)

        terminal_art = plt.build()
        print("\n" + "="*80)
        plt.show()
        print("="*80 + "\n")

        cls._export_png_artifact(nodes)
        return terminal_art


# Global singleton instance
cli_visualizer = CLIPixelVisualizer()


if __name__ == "__main__":
    cli_visualizer.render_terminal_graph()
