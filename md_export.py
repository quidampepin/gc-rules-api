"""
md_export.py — Generate Markdown fact sheets from program JSON files.

Reads each JSON in programs/ and outputs a concise, LLM-optimized
Markdown file in md/ that contains all the key facts, rules, and
examples. Also generates programs-index.json for retrieval.

Usage:
    python md_export.py

Output:
    md/canada-child-benefit.md
    md/employment-insurance.md
    md/old-age-security.md
    md/programs-index.json
"""

import json
import re
from pathlib import Path

PROGRAMS_DIR = Path(__file__).parent / "programs"
MD_DIR = Path(__file__).parent / "md"


def fmt(n):
    """Format number with commas."""
    if isinstance(n, float):
        return f"{n:,.2f}" if n != int(n) else f"{int(n):,}"
    return f"{n:,}"


def resolve_params(text, params):
    """Replace $param:xyz with formatted value."""
    def replacer(m):
        val = params.get(m.group(1))
        if val is None:
            return m.group(0)
        if isinstance(val, (int, float)):
            return fmt(val)
        return str(val)
    return re.sub(r'\$param:([a-zA-Z0-9_]+)', replacer, text)


def program_to_md(prog):
    """Convert a program JSON to a Markdown fact sheet."""
    p = prog
    params = {}
    for param in p.get("amounts", {}).get("parameters", []):
        params[param["id"]] = param["value"]

    lines = []

    # Header
    lines.append(f"# {p['name']['en']}")
    lines.append(f"")
    lines.append(f"{p['description']['en']}")
    lines.append(f"")
    lines.append(f"- **Administered by:** {p['administered_by']['name']['en']}")
    lines.append(f"- **Effective date:** {p.get('effective_date', 'N/A')}")
    lines.append(f"- **Status:** {p.get('status', 'active')}")
    lines.append(f"")

    # Eligibility
    if "eligibility" in p:
        lines.append(f"## Eligibility")
        lines.append(f"")
        lines.append(p["eligibility"]["summary"]["en"])
        lines.append(f"")
        for c in p["eligibility"].get("criteria", []):
            lines.append(f"- {c['description']['en']}")
        lines.append(f"")

    # Amounts and parameters
    if "amounts" in p:
        a = p["amounts"]
        lines.append(f"## Amounts")
        lines.append(f"")
        lines.append(a["summary"]["en"])
        lines.append(f"")

        # Parameters table
        param_list = a.get("parameters", [])
        if param_list:
            lines.append(f"### Key values")
            lines.append(f"")
            lines.append(f"| Parameter | Value |")
            lines.append(f"|---|---|")
            for param in param_list:
                val = param["value"]
                unit = param.get("unit", "")
                if unit == "dollars":
                    display = f"${fmt(val)}"
                elif unit == "percent":
                    display = f"{val}%"
                else:
                    display = f"{val} {unit}".strip()
                lines.append(f"| {param['label']['en']} | {display} |")
            lines.append(f"")

        # Calculation rules
        calc = a.get("calculation", {})
        if calc:
            lines.append(f"### Calculation rules")
            lines.append(f"")
            desc = calc.get("description", {})
            if isinstance(desc, dict):
                lines.append(resolve_params(desc.get("en", ""), params))
            elif isinstance(desc, str):
                lines.append(resolve_params(desc, params))
            lines.append(f"")

            # CCB-specific: step 1 max benefit
            s1 = calc.get("step_1_max_benefit", {})
            if s1:
                lines.append(f"**Maximum benefit per child:**")
                lines.append(f"")
                for rule in s1.get("rules", []):
                    cond = resolve_params(rule["condition"], params)
                    amt = rule.get("annual_amount", "")
                    if amt.startswith("$param:"):
                        amt = f"${fmt(params.get(amt.replace('$param:', ''), '?'))}"
                    lines.append(f"- If {cond}: {amt}/year")
                lines.append(f"")

            # CCB-specific: reduction brackets
            s2 = calc.get("step_2_income_reduction", {})
            if s2:
                lines.append(f"**Income reduction brackets:**")
                lines.append(f"")
                for b in s2.get("brackets", []):
                    rng = resolve_params(b.get("income_range", ""), params)
                    red = resolve_params(b.get("reduction", b.get("formula", "")), params)
                    lines.append(f"- {rng}: {red}")
                lines.append(f"")

                rt = s2.get("reduction_table", [])
                if rt:
                    lines.append(f"**Reduction table:**")
                    lines.append(f"")
                    lines.append(f"| Children | Mid-bracket rate | High-bracket rate | Base reduction |")
                    lines.append(f"|---|---|---|---|")
                    for tier in rt:
                        nc = str(tier["num_children"])
                        mid = f"{tier['rate_mid']*100:.10g}%"
                        high = f"{tier['rate_high']*100:.10g}%"
                        base = f"${fmt(tier['base_reduction'])}"
                        lines.append(f"| {nc} | {mid} | {high} | {base} |")
                    lines.append(f"")

            # EI-specific: formula and duration
            formula = calc.get("formula")
            if formula:
                lines.append(f"**Formula:** {resolve_params(formula, params)}")
                lines.append(f"")

            duration = calc.get("duration_table", {})
            if isinstance(duration, dict) and "description" in duration:
                lines.append(f"**Duration:** {resolve_params(duration['description']['en'], params)}")
                lines.append(f"")

            # OAS-specific: steps
            for key in ["step_1_base_pension", "step_2_proration", "step_3_clawback", "optional_deferral"]:
                step = calc.get(key)
                if step and isinstance(step, dict):
                    desc = step.get("description", {}).get("en", "")
                    if desc:
                        label = key.replace("_", " ").title()
                        lines.append(f"**{label}:** {resolve_params(desc, params)}")
                        # Include any nested values
                        for sk, sv in step.items():
                            if sk == "description":
                                continue
                            if isinstance(sv, dict) and "en" in sv:
                                lines.append(f"- {sk}: {resolve_params(sv['en'], params)}")
                            elif isinstance(sv, (int, float, str)):
                                lines.append(f"- {sk}: {resolve_params(str(sv), params)}")
                        lines.append(f"")

        # Examples
        examples = a.get("examples", [])
        if examples:
            lines.append(f"### Examples")
            lines.append(f"")
            for ex in examples:
                scenario = ex["scenario"]["en"]
                r = ex["result"]
                amounts = []
                if "annual" in r:
                    amounts.append(f"${fmt(r['annual'])}/year")
                if "monthly" in r:
                    amounts.append(f"${fmt(r['monthly'])}/month")
                elif "annual" in r:
                    amounts.append(f"${fmt(round(r['annual']/12, 2))}/month")
                if "weekly" in r:
                    amounts.append(f"${fmt(r['weekly'])}/week")
                lines.append(f"- **{scenario}** → {', '.join(amounts)}")
            lines.append(f"")

    # How to apply
    if "how_to_apply" in p:
        lines.append(f"## How to apply")
        lines.append(f"")
        for ch in p["how_to_apply"].get("channels", []):
            lines.append(f"- **{ch['method'].title()}:** {ch['description']['en']}")
        lines.append(f"")

    # Processing time
    if "processing_time" in p:
        lines.append(f"## Processing time")
        lines.append(f"")
        lines.append(p["processing_time"]["details"]["en"])
        lines.append(f"")

    # Fees
    if "fees" in p:
        lines.append(f"## Fees")
        lines.append(f"")
        lines.append(p["fees"]["details"]["en"])
        lines.append(f"")

    return "\n".join(lines)


def build_index(programs):
    """Generate programs-index.json for retrieval routing."""
    # Auto-generate keywords from program content
    index = {}
    for pid, prog in programs.items():
        # Collect keywords from name, description, and eligibility
        name_en = prog["name"]["en"].lower()
        name_fr = prog["name"]["fr"].lower()
        desc_words = prog["description"]["en"].lower().split()

        # Core keywords: program name words + key terms
        # Skip generic short words that cause false matches
        skip = {"the", "for", "and", "des", "les", "par", "sur", "une", "age",
                "old", "new", "tax", "net", "per", "not", "may", "can"}
        keywords = set()
        for word in name_en.split():
            if len(word) > 3 and word.lower() not in skip:
                keywords.add(word.lower())
        for word in name_fr.split():
            if len(word) > 3 and word.lower() not in skip:
                keywords.add(word.lower())

        # Add common abbreviations and aliases
        aliases = {
            "canada-child-benefit": ["ccb", "child benefit", "children", "child", "family income", "afni", "custody"],
            "employment-insurance": ["ei", "unemployment", "job loss", "maternity", "parental", "sickness", "roe"],
            "old-age-security": ["oas", "gis", "old age", "old-age", "senior", "seniors", "pension", "retirement"],
        }
        for alias in aliases.get(pid, []):
            keywords.add(alias)

        # Topics
        topic_map = {
            "canada-child-benefit": ["family", "children", "tax-free benefit", "monthly payment"],
            "employment-insurance": ["employment", "job loss", "temporary income", "workers"],
            "old-age-security": ["retirement", "seniors", "pension", "aging"],
        }

        index[pid] = {
            "name": {"en": prog["name"]["en"], "fr": prog["name"]["fr"]},
            "keywords": sorted(keywords),
            "topics": topic_map.get(pid, []),
            "file": f"{pid}.md",
        }

    return index


def main():
    MD_DIR.mkdir(exist_ok=True)

    programs = {}
    for f in sorted(PROGRAMS_DIR.glob("*.json")):
        with open(f, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            programs[data["id"]] = data

    # Generate MD fact sheets
    for pid, prog in programs.items():
        md = program_to_md(prog)
        out_file = MD_DIR / f"{pid}.md"
        with open(out_file, "w", encoding="utf-8") as fh:
            fh.write(md)
        print(f"  {out_file} ({len(md):,} chars)")

    # Generate index
    index = build_index(programs)
    index_file = MD_DIR / "programs-index.json"
    with open(index_file, "w", encoding="utf-8") as fh:
        json.dump(index, fh, indent=2, ensure_ascii=False)
    print(f"  {index_file}")

    print(f"\nDone — {len(programs)} programs exported.")


if __name__ == "__main__":
    main()
