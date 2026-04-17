"""
chat_claude.py — Claude-powered Q&A for GC program rules.

Same architecture as chat.py (Ollama), but uses the Anthropic API
with Claude Haiku for fast, cheap, accurate answers.

Architecture:
  1. Load programs-index.json (lightweight keyword index)
  2. Match user question to relevant program(s) via keywords
  3. Load only the matched MD fact sheet(s) (~2-3K chars each)
  4. Send MD context + question to Claude via Anthropic API

Cost management:
  - Uses Claude Haiku (cheapest Claude model: ~$0.25/1M input, ~$1.25/1M output)
  - Tracks token usage and estimated cost per session
  - Stops when max_cost_usd is reached (configurable in secrets/config.json)
  - Keyword routing keeps input tokens minimal (~800 per question)

Setup:
    pip install anthropic
    # Put your API key in secrets/config.json (git-ignored)
    python chat_claude.py

Config file (secrets/config.json):
    {
      "anthropic_api_key": "sk-ant-...",
      "model": "claude-haiku-4-5-20251001",
      "max_cost_usd": 5.00
    }
"""

import json
import sys
import argparse
from pathlib import Path

try:
    import anthropic
except ImportError:
    print("Missing dependency: pip install anthropic")
    sys.exit(1)

MD_DIR = Path(__file__).parent / "md"
INDEX_FILE = MD_DIR / "programs-index.json"
SECRETS_FILE = Path(__file__).parent / "secrets" / "config.json"

# Pricing per 1M tokens (USD) — as of 2025
# https://docs.anthropic.com/en/docs/about-claude/models
MODEL_PRICING = {
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.00},
    "claude-sonnet-4-6":        {"input": 3.00, "output": 15.00},
    "claude-opus-4-6":          {"input": 15.00, "output": 75.00},
}
DEFAULT_PRICING = {"input": 3.00, "output": 15.00}


# ── Config ──────────────────────────────────────────────────────────

def load_config(config_path: Path) -> dict:
    if not config_path.exists():
        print(f"Config not found: {config_path}")
        print(f"Create it with your API key:")
        print(f'  {{"anthropic_api_key": "sk-ant-...", "model": "claude-haiku-4-5-20251001", "max_cost_usd": 5.00}}')
        sys.exit(1)
    with open(config_path, "r") as f:
        config = json.load(f)
    if config.get("anthropic_api_key", "").startswith("YOUR"):
        print(f"Please set your Anthropic API key in {config_path}")
        sys.exit(1)
    return config


# ── Cost tracking ───────────────────────────────────────────────────

class CostTracker:
    def __init__(self, model: str, max_cost: float):
        self.model = model
        self.max_cost = max_cost
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
        self.pricing = MODEL_PRICING.get(model, DEFAULT_PRICING)

    def add(self, input_tokens: int, output_tokens: int):
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        cost = (
            input_tokens * self.pricing["input"] / 1_000_000
            + output_tokens * self.pricing["output"] / 1_000_000
        )
        self.total_cost += cost
        return cost

    def budget_remaining(self) -> float:
        return self.max_cost - self.total_cost

    def over_budget(self) -> bool:
        return self.total_cost >= self.max_cost

    def summary(self) -> str:
        return (
            f"${self.total_cost:.4f} spent "
            f"({self.total_input_tokens:,} in / {self.total_output_tokens:,} out) "
            f"— ${self.budget_remaining():.2f} remaining"
        )


# ── Index & retrieval (shared with chat.py) ─────────────────────────

def load_index(index_file: Path) -> dict:
    with open(index_file, "r", encoding="utf-8") as f:
        return json.load(f)


def load_md(md_dir: Path, filename: str) -> str:
    with open(md_dir / filename, "r", encoding="utf-8") as f:
        return f.read()


def match_programs(question: str, index: dict) -> list:
    q_lower = question.lower()
    matched = []
    for pid, entry in index.items():
        for kw in entry["keywords"]:
            if kw in q_lower:
                matched.append(pid)
                break
    return matched


def retrieve_context(question: str, index: dict, md_dir: Path) -> tuple:
    matched_ids = match_programs(question, index)
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


# ── Prompts ─────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a Government of Canada benefits assistant. You answer questions
using ONLY the program data provided in each message.

CRITICAL RULES:
- Every dollar amount, threshold, rate, and rule you need is in the data below.
- Use ONLY those numbers. NEVER use numbers from your training data.
- Show your math when calculating benefits.
- If the question is about a program not in the provided data, say so.
- Be concise and clear.
- Answer in the same language as the question.
"""

USER_TEMPLATE = """\
Answer my question using ONLY the following program data.

{context}

Question: {question}"""


# ── Chat loop ───────────────────────────────────────────────────────

def chat(client: anthropic.Anthropic, model: str, index: dict,
         md_dir: Path, tracker: CostTracker):
    display_history = []

    names = ", ".join(e["name"]["en"] for e in index.values())
    print(f"\nGC Rules Assistant  (model: {model})")
    print(f"Programs: {names}")
    print(f"Budget: ${tracker.max_cost:.2f}")
    print(f"Type your question, or 'quit' to exit.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n\nSession {tracker.summary()}")
            print("Bye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print(f"\nSession {tracker.summary()}")
            print("Bye!")
            break

        # Budget check
        if tracker.over_budget():
            print(f"\n  Budget exhausted ({tracker.summary()})")
            print(f"  Increase max_cost_usd in {SECRETS_FILE} to continue.")
            break

        # Retrieve relevant MD context
        context, matched_names = retrieve_context(user_input, index, md_dir)
        augmented_msg = USER_TEMPLATE.format(context=context, question=user_input)

        # Build message history (last 2 turns for continuity)
        recent = display_history[-4:]
        messages = recent + [{"role": "user", "content": augmented_msg}]

        print(f"  [matched: {', '.join(matched_names)}]")
        print("Assistant: ", end="", flush=True)

        try:
            # Stream the response
            full_response = ""
            with client.messages.stream(
                model=model,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=messages,
                temperature=0,
            ) as stream:
                for text in stream.text_stream:
                    print(text, end="", flush=True)
                    full_response += text

            print()

            # Track cost
            usage = stream.get_final_message().usage
            cost = tracker.add(usage.input_tokens, usage.output_tokens)
            print(f"  [{tracker.summary()}]")

            display_history.append({"role": "user", "content": user_input})
            display_history.append({"role": "assistant", "content": full_response})

        except anthropic.RateLimitError:
            print("\n  Rate limited by the API. Wait a moment and try again.")
        except anthropic.AuthenticationError:
            print(f"\n  Invalid API key. Check {SECRETS_FILE}")
            break
        except anthropic.APIStatusError as e:
            print(f"\n  API error: {e.message}")
        except Exception as e:
            print(f"\n  Error: {e}")


# ── CLI ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="GC Rules Q&A with Claude")
    parser.add_argument("--config", type=Path, default=SECRETS_FILE,
                        help=f"Path to config file (default: {SECRETS_FILE})")
    parser.add_argument("--model", default=None,
                        help="Override model from config")
    parser.add_argument("--max-cost", type=float, default=None,
                        help="Override max cost (USD) from config")
    parser.add_argument("--md-dir", type=Path, default=MD_DIR,
                        help="Path to MD fact sheets directory")
    args = parser.parse_args()

    config = load_config(args.config)

    model = args.model or config.get("model", "claude-haiku-4-5-20251001")
    max_cost = args.max_cost or config.get("max_cost_usd", 5.00)

    index_file = args.md_dir / "programs-index.json"
    if not index_file.exists():
        print(f"Index not found at {index_file}")
        print("Run: python md_export.py")
        sys.exit(1)

    index = load_index(index_file)
    client = anthropic.Anthropic(api_key=config["anthropic_api_key"])
    tracker = CostTracker(model, max_cost)

    chat(client, model, index, args.md_dir, tracker)


if __name__ == "__main__":
    main()
