import asyncio
import os
import sys
import uuid
from dotenv import load_dotenv

# Ensure src is in python path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from open_deep_research.deep_researcher import deep_researcher_builder
from langgraph.checkpoint.memory import MemorySaver

# Load environment variables
load_dotenv()

async def main():
    query = (
        "Detailed investigation into the prompt engineering meta-optimization landscape up to July 2026. "
        "Focus on state-of-the-art methods for: (1) chain-of-thought (CoT) generation, "
        "(2) instruction following, (3) constitutional AI (alignment, critique, and revision), "
        "and (4) prompt compression techniques. Prioritize peer-reviewed academic publications from venues "
        "such as arXiv, NeurIPS, ICLR, and ACL, as well as official code repository links. "
        "Find specific target models, benchmark tasks, and optimization algorithms (e.g. evolutionary, RL, gradient-based)."
    )
    print(f"Starting research on: {query}")
    
    checkpointer = MemorySaver()
    graph = deep_researcher_builder.compile(checkpointer=checkpointer)
    
    config = {
        "configurable": {
            "thread_id": str(uuid.uuid4()),
            "max_structured_output_retries": 3,
            "allow_clarification": False,
            "max_concurrent_research_units": 3,
            "search_api": "ddg",
            "max_researcher_iterations": 5,
            "max_react_tool_calls": 6
        }
    }
    
    # Run using the official ainvoke method
    final_state = await graph.ainvoke(
        {"messages": [{"role": "user", "content": query}]},
        config
    )
    
    report = final_state.get("final_report")
    if report:
        md_filename = "prompt_optimization_report.md"
        with open(md_filename, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"Markdown report saved successfully to {md_filename}")
        
        try:
            import markdown
            html_content = markdown.markdown(report, extensions=['extra', 'toc'])
            html_template = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Prompt Engineering Meta-Optimization Report</title>
    <style>
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; 
            line-height: 1.7; 
            max-width: 900px; 
            margin: 40px auto; 
            padding: 0 20px; 
            color: #24292e; 
        }}
        h1, h2, h3 {{ color: #1a1a1a; font-family: "Outfit", -apple-system, sans-serif; }}
        h1 {{ border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; }}
        h2 {{ border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; margin-top: 24px; }}
        pre {{ background: #f6f8fa; padding: 16px; border-radius: 6px; overflow: auto; }}
        code {{ font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace; font-size: 85%; background: rgba(27,31,35,0.05); padding: 0.2em 0.4em; border-radius: 3px; }}
        pre code {{ background: transparent; padding: 0; font-size: 100%; }}
        blockquote {{ border-left: 0.25em solid #dfe2e5; color: #6a737d; padding: 0 1em; margin: 20px 0; }}
        a {{ color: #0366d6; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <h1>Prompt Engineering Meta-Optimization Landscape</h1>
    <p style="color: #6a737d; font-size: 0.9em;">Generated via Open Deep Research (DeepSeek v4 Flash) &bull; {uuid.uuid4().hex[:8]}</p>
    <hr>
    {html_content}
</body>
</html>"""
            html_filename = "prompt_optimization_report.html"
            with open(html_filename, "w", encoding="utf-8") as f:
                f.write(html_template)
            print(f"HTML report saved successfully to {html_filename}")
        except Exception as e:
            print(f"Error generating HTML: {e}")
    else:
        print("Error: No final report generated.")

if __name__ == "__main__":
    asyncio.run(main())
