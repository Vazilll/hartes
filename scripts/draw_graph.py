import sys
from pathlib import Path

sys.path.insert(0, "C:/vazus/pyenv")

from dnts_core.unified_graph import unified_graph

def draw_graph():
    print("Generating graph visualization...")
    png_bytes = unified_graph.get_graph().draw_mermaid_png()
    
    # Save the PNG file to the artifacts directory so it can be displayed
    # We will output the path it was saved to.
    out_path = Path("C:/Users/Vaz/.gemini/antigravity-ide/brain/3e506a9a-18fb-47f3-8c54-5e5eff419e58/unified_graph_visual.png")
    out_path.write_bytes(png_bytes)
    print(f"Graph saved to {out_path}")

if __name__ == "__main__":
    draw_graph()
