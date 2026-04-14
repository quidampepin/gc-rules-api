"""
chat.py — Local LLM Q&A for GC program rules using Ollama.

Architecture:
  1. Load programs-index.json (lightweight keyword index)
  2. Match user question to relevant program(s) via keywords
  3. Load only the matched MD fact sheet(s) (~2-3K chars each)
  4. Send MD context + question to Ollama

This keeps context small and focused so 7-8b models can
accurately ground their answers on the provided data.

Prerequisites:
    python md_export.py          # generate MD files + index
    pip install ollama
    Ollama running locally

Usage:
    python chat.py
    python chat.py --model qwen2.5:7b-instruct-q4_K_M
"""

import json
import sys
import argparse
from pathlib import Path

try:
    import ollama
except ImportError:
    print("Missing dependency: pip install ollama")
    sys.exit(1)

MD_DIR = Path(__file__).parent / "md"
INDEX_FILE = MD_DIR / "programs-index.json"
DEFAULT_MODEL = "qwen2.5:7b-instruct-q4_K_M"


# ── Index & retrieval ────────────────────────────────────────────────

def load_index(index_file: Path) -> dict:
    with open(index_file, "r", encoding="utf-8") as f:
        return json.load(f)


def load_md(md_dir: Path, filename: str) -> str:
    with open(md_dir / filename, "r", encoding="utf-8") as f:
        return f.read()


def match_programs(question: str, index: dict) -> list:
    """Match question to program IDs using the keyword index."""
    q_lower = question.lower()
    matched = []

    for pid, entry in index.items():
        for kw in entry["keywords"]:
            if kw in q_lower:
                matched.append(pid)
                break

    return matched


def retrieve_context(question: str, index: dict, md_dir: Path) -> tuple:
    """Route question → load relevant MD files. Returns (context, matched_names)."""
    matched_ids = match_programs(question, index)

    # If no match, load all (small enough for 3 programs)
    if not matched_ids:
        matched_ids = list(index.keys())

    context_parts = []
    names = []
    for pid in matched_ids:
        entry = index[pid]
        md_content = load_md(md_dir, entry["file"])
        context_parts.append(md_content)
        names.append(entry["name"]["en"])

    return "\n\n---\n\n".join(context_parts), names


# ── Prompts ──────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a Government of Canada benefits assistant. You answer questions
using ONLY the program data provided in each message.

CRITICAL RULES:
- Every dollar amount, threshold, rate, and rule you need is in the data below.
- Use ONLY those numbers. NEVER use numbers from your training data.
- Show your math when calculating benefits.
- If the question is about a program not in the provided data, say so.
- Be concise.
- Answer in the same language as the question.
"""

USER_TEMPLATE = """\
Answer my question using ONLY the following program data.

{context}

Question: {question}"""


# ── Chat loop ────────────────────────────────────────────────────────

def chat(model: str, index: dict, md_dir: Path):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    display_history = []

    names = ", ".join(e["name"]["en"] for e in index.values())
    print(f"\nGC Rules Assistant  (model: {model})")
    print(f"Programs: {names}")
    print(f"Type your question, or 'quit' to exit.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nBye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("Bye!")
            break

        # Retrieve relevant MD context
        context, matched_names = retrieve_context(user_input, index, md_dir)
        augmented_msg = USER_TEMPLATE.format(context=context, question=user_input)

        # System + last 2 turns + current question
        recent = display_history[-4:]
        send_messages = [messages[0]] + recent + [{"role": "user", "content": augmented_msg}]

        print(f"  [matched: {', '.join(matched_names)}]")
        print("Assistant: ", end="", flush=True)
        try:
            stream = ollama.chat(
                model=model,
                messages=send_messages,
                stream=True,
                options={"temperature": 0},
            )
            full_response = ""
            for chunk in stream:
                token = chunk["message"]["content"]
                print(token, end="", flush=True)
                full_response += token
            print()

            display_history.append({"role": "user", "content": user_input})
            display_history.append({"role": "assistant", "content": full_response})

        except ollama.ResponseError as e:
            print(f"\nOllama error: {e}")
            print(f"Is the model '{model}' pulled? Try: ollama pull {model}")
        except Exception as e:
            print(f"\nError: {e}")
            print("Is Ollama running? Start it with: ollama serve")


# ── CLI ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="GC Rules Q&A with Ollama")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"Ollama model name (default: {DEFAULT_MODEL})")
    parser.add_argument("--list-models", action="store_true",
                        help="List available Ollama models and exit")
    parser.add_argument("--md-dir", type=Path, default=MD_DIR,
                        help="Path to MD fact sheets directory")
    args = parser.parse_args()

    if args.list_models:
        try:
            models = ollama.list()
            print("Available Ollama models:")
            for m in models.get("models", []):
                size_gb = m.get("size", 0) / 1e9
                print(f"  {m['name']:30s} ({size_gb:.1f} GB)")
        except Exception as e:
            print(f"Could not connect to Ollama: {e}")
        return

    index_file = args.md_dir / "programs-index.json"
    if not index_file.exists():
        print(f"Index not found at {index_file}")
        print("Run: python md_export.py")
        sys.exit(1)

    index = load_index(index_file)
    chat(args.model, index, args.md_dir)


if __name__ == "__main__":
    main()
