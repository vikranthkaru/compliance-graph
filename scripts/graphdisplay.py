from pathlib import Path

from agents.compliance_agent.graph import build_compliance_graph


def save_graph():
    print("Initializing Compliance Graph...")

    docs_dir = Path("docs")
    docs_dir.mkdir(parents=True, exist_ok=True)

    try:
        graph = build_compliance_graph()

        compiled_graph = graph.get_graph(xray=True)

        # Save Mermaid source
        mermaid = compiled_graph.draw_mermaid()
        mermaid_file = docs_dir / "compliance_agent_graph.mmd"
        mermaid_file.write_text(mermaid, encoding="utf-8")

        print(f"✅ Mermaid diagram saved to: {mermaid_file}")

        # Save PNG
        png = compiled_graph.draw_mermaid_png()

        png_file = docs_dir / "compliance_agent_graph.png"
        with open(png_file, "wb") as f:
            f.write(png)

        print(f"✅ PNG diagram saved to: {png_file}")

    except Exception as e:
        print(f"\n❌ Failed to generate graph: {e}")
        print("\nIf PNG generation fails, install:")
        print("pip install grandalf pygraphviz")


if __name__ == "__main__":
    save_graph()