# GC Rules API — Experiment

**An API-first approach to documenting Government of Canada program rules and amounts as structured, queryable, computable data.**

This is an experiment. Not an official Government of Canada product.

## The Problem

Today, program rules (eligibility criteria, benefit amounts, income thresholds, clawback rates) live as prose text across Canada.ca web pages, PDFs, and internal documents. When amounts change, dozens of pages need manual updates. When a chatbot needs to answer "how much CCB would I get?", it either scrapes web pages or relies on training data that may be outdated.

## The Idea

Encode program rules as **structured data** (JSON with decision tables) and serve them through multiple channels from a single source of truth:

1. **Web content** — Canada.ca pages generated from the JSON
2. **LLM chatbot** — Markdown fact sheets derived from the JSON, served to a local LLM
3. **REST API** — Programs queryable as structured data
4. **Benefit calculators** — Decision tables are computable, not just readable
5. **Policy analysis** — Version-controlled rules make changes visible

## Architecture

```
programs/*.json            (single source of truth)
    │
    ├── md_export.py  ──→  md/*.md + programs-index.json
    │                        └── chat.py reads index, loads relevant MD,
    │                            sends to Ollama LLM for Q&A
    │
    ├── site/build.py ──→  site/_site/*.html
    │                        └── Canada.ca-style pages with GCWeb markup,
    │                            all amounts populated from JSON
    │
    └── api/main.py   ──→  REST API (FastAPI)
                             └── /programs, /calculate, /check-eligibility
```

Key design: the JSON files are the canonical data. Everything else (MD, HTML, API responses) is a derived view. Change a number in the JSON, re-run the build scripts, and all outputs update.

## What's in this repo

```
gc-rules-api/
├── programs/                        # Source of truth (one JSON per program)
│   ├── canada-child-benefit.json
│   ├── employment-insurance.json
│   └── old-age-security.json
├── schemas/
│   └── program_schema.json          # JSON Schema for program data
├── md/                              # LLM-optimized Markdown (generated)
│   ├── canada-child-benefit.md
│   ├── employment-insurance.md
│   ├── old-age-security.md
│   └── programs-index.json          # Keyword index for retrieval
├── site/                            # Static site builder
│   ├── _data/programs/              # Copy of JSON for Jekyll compatibility
│   ├── _layouts/gcweb.html          # GCWeb/WET-BOEW layout
│   ├── _site/                       # Generated HTML output
│   └── build.py                     # Builds Canada.ca-style HTML from JSON
├── api/
│   └── main.py                      # FastAPI application
├── demo/
│   └── llm_demo.py                  # API function-calling demo
├── static/
│   └── index.html                   # Web content demo (pulls from API)
├── chat.py                          # Ollama LLM Q&A (reads MD files)
├── md_export.py                     # Generates MD + index from JSON
├── requirements.txt
├── environment.yml
└── README.md
```

## Quick Start

### 1. LLM chatbot (local, using Ollama)

```bash
# Install Ollama: https://ollama.com
ollama pull qwen2.5:7b-instruct-q4_K_M

# Install Python dependency
pip install ollama

# Generate Markdown fact sheets from the JSON
python md_export.py

# Start the chat
python chat.py
```

Ask it questions like:
- "What is the income threshold to get the maximum CCB?"
- "How is EI calculated?"
- "Am I eligible for OAS if I lived in Canada for 20 years?"

### 2. Static site (Canada.ca-style HTML)

```bash
# Build the CCB "How much you can get" page from JSON
cd site
python build.py

# Open the output
# site/_site/en/canada-child-benefit/how-much.html
```

All dollar amounts, thresholds, and reduction rates are pulled from the JSON. Zero hardcoded values in the HTML template.

### 3. REST API

```bash
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000

# Try it
curl http://localhost:8000/programs?lang=en
curl -X POST http://localhost:8000/programs/canada-child-benefit/calculate \
  -H "Content-Type: application/json" \
  -d '{"num_children": 2, "children": [{"age": 4}, {"age": 8}], "family_net_income": 55000}'
```

### 4. LLM function-calling demo

```bash
# Requires the API to be running (step 3)
python demo/llm_demo.py
```

## Workflow: Updating Program Data

When amounts change (e.g., new CCB rates in July):

```bash
# 1. Edit the JSON source of truth
#    programs/canada-child-benefit.json

# 2. Regenerate all derived outputs
python md_export.py          # updates md/*.md + index
cd site && python build.py   # updates site/_site/*.html
cp ../programs/*.json _data/programs/  # sync for Jekyll compat

# 3. Restart the API (if running)
#    It reloads programs/ on startup
```

## Key Design Decisions

### Why JSON, not RDF/Turtle?

The [gc-ontology experiment](https://github.com/gc-proto/ontologie-gc-ontology) used RDF (Turtle files) with SPARQL queries. RDF is powerful for modeling complex entity relationships, but for this use case — "what are the rules and amounts for program X?" — it adds complexity without proportional benefit. JSON is readable by any developer, natively supported by every language and LLM, and easy to version control.

### Why Markdown for the LLM layer?

Raw JSON is token-expensive and hard for small LLMs to parse accurately. A CCB JSON file is ~19K chars; the derived Markdown fact sheet is ~3K chars with the same key facts. LLMs are also trained on vast amounts of Markdown, making it a natural format for grounding context. The JSON remains the source of truth; the MD is a derived view optimized for LLM consumption.

### Why keyword routing instead of embeddings?

For 3 programs, keyword matching is fast, transparent, and accurate. At scale (100+ programs), you'd add embedding-based retrieval or a lightweight classifier. The architecture supports this — swap the `match_programs()` function in `chat.py` without changing anything else.

### Why decision tables?

Inspired by GOV.UK's direction toward structured APIs and Rules as Code initiatives (New Zealand, France's OpenFisca), this experiment encodes rules as **computable decision tables**. The API can actually check eligibility and calculate amounts, not just describe rules in prose.

## Comparison: Before and After

| | Before (status quo) | After (Rules API) |
|---|---|---|
| **Source of truth** | Prose on Canada.ca pages | Structured JSON in version control |
| **Updating amounts** | Edit dozens of web pages manually | Change one JSON value, regenerate |
| **Chatbot accuracy** | Relies on training data / web scraping | Reads structured MD derived from JSON |
| **Web content** | Hand-coded HTML | Generated from JSON, always in sync |
| **Calculators** | Custom code per calculator | Shared calculation engine from API |
| **Bilingual** | Separate EN/FR page maintenance | Single data source, both languages |
| **Change tracking** | No audit trail | Git history shows every change |

## What's Next

1. **Add more programs** — Start with high-traffic ones (CPP, GIS)
2. **Claude/GPT integration** — Use a capable model via API for higher-quality answers
3. **Versioned rules** — Track historical values ("what was the CCB max in 2022?")
4. **Topic-based retrieval** — Group programs by life event for cross-program questions
5. **CI/CD pipeline** — Auto-validate JSON against schema, auto-generate MD + HTML on merge

## Inspiration

- [GOV.UK — Why GOV.UK APIs are changing](https://insidegovuk.blog.gov.uk/2025/04/07/why-gov-uk-apis-are-changing-and-how-you-can-get-involved/) — Moving to GraphQL for multi-channel content
- [gc-proto/ontologie-gc-ontology](https://github.com/gc-proto/ontologie-gc-ontology) — GC knowledge graph experiment using RDF + LLM RAG
- [OpenFisca](https://openfisca.org/) — Open-source rules-as-code platform (France, New Zealand)
- [Better Rules NZ](https://www.digital.govt.nz/blog/labplus-better-rules-for-government-discovery-report/) — New Zealand's Rules as Code initiative
