"""
GC Rules API — Experiment
A lightweight API serving Government of Canada program rules, amounts,
and eligibility criteria as structured, queryable, computable data.

This is a proof of concept. Not an official Government of Canada product.
"""

import json
import re
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

PROGRAMS_DIR = Path(__file__).resolve().parent.parent / "programs"

app = FastAPI(
    title="GC Rules API",
    description=(
        "Experimental API for querying Government of Canada program rules, "
        "eligibility criteria, and benefit amounts as structured data."
    ),
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # experiment only — lock down in production
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_programs() -> dict:
    """Load all program JSON files from the programs directory."""
    programs = {}
    for file in PROGRAMS_DIR.glob("*.json"):
        with open(file, "r", encoding="utf-8") as f:
            data = json.load(f)
            programs[data["id"]] = data
    return programs


PROGRAMS = load_programs()

# Build a param lookup per program: { program_id: { param_id: value } }
PARAMS = {}
for pid, prog in PROGRAMS.items():
    PARAMS[pid] = {
        p["id"]: p["value"]
        for p in prog.get("amounts", {}).get("parameters", [])
    }


# ---------------------------------------------------------------------------
# $param: resolver
# ---------------------------------------------------------------------------

PARAM_RE = re.compile(r"\$param:([a-zA-Z0-9_]+)")


def resolve_param(value, params: dict):
    """
    If value is a string like "$param:income_threshold_1", return the
    numeric parameter value. If it's a list, resolve each element.
    Otherwise return as-is.
    """
    if isinstance(value, str):
        m = PARAM_RE.fullmatch(value)
        if m:
            return params.get(m.group(1), value)
        return value
    if isinstance(value, list):
        return [resolve_param(v, params) for v in value]
    return value


# ---------------------------------------------------------------------------
# Condition evaluator (now with $param: resolution)
# ---------------------------------------------------------------------------

def evaluate_condition(operator: str, threshold, actual, params: dict) -> bool:
    """Evaluate a single condition, resolving any $param: references first."""
    if actual is None:
        return False
    threshold = resolve_param(threshold, params)
    ops = {
        "eq": lambda a, t: a == t,
        "neq": lambda a, t: a != t,
        "lt": lambda a, t: a < t,
        "lte": lambda a, t: a <= t,
        "gt": lambda a, t: a > t,
        "gte": lambda a, t: a >= t,
        "in": lambda a, t: a in t,
        "between": lambda a, t: t[0] <= a <= t[1],
    }
    fn = ops.get(operator)
    if fn is None:
        return False
    return fn(actual, threshold)


def evaluate_decision_table(table: dict, inputs: dict, params: dict) -> dict:
    """Run inputs through a decision table, return the first matching outcome."""
    for rule in table.get("rules", []):
        conditions = rule.get("conditions", {})
        all_match = True
        for field, cond in conditions.items():
            actual = inputs.get(field)
            if not evaluate_condition(cond["operator"], cond["value"], actual, params):
                all_match = False
                break
        if all_match:
            return {
                "outcome": rule["outcome"],
                "note": rule.get("note"),
                "matched_rule": rule,
            }
    return {
        "outcome": table.get("default_outcome", "refer"),
        "note": None,
        "matched_rule": None,
    }


# ---------------------------------------------------------------------------
# Benefit calculator (reads from the new `calculation` structure)
# ---------------------------------------------------------------------------

def calculate_benefit(program: dict, inputs: dict) -> dict:
    """
    Calculate benefit amounts using the program's parameters and
    calculation structure. All magic numbers come from parameters.
    """
    pid = program["id"]
    params = PARAMS.get(pid, {})
    amounts = program.get("amounts", {})
    calc = amounts.get("calculation", {})

    # --- CCB ---
    if pid == "canada-child-benefit":
        children = inputs.get("children", [])
        num_children = inputs.get("num_children", len(children))
        family_income = inputs.get("family_net_income", 0)

        young_cutoff = params["young_child_age_cutoff"]
        max_under = params["max_annual_under_6"]
        max_over = params["max_annual_6_to_17"]
        threshold_1 = params["income_threshold_1"]
        threshold_2 = params["income_threshold_2"]

        # Step 1: sum max benefit per child by age
        total_max = 0
        for child in children:
            age = child.get("age", 0)
            total_max += max_under if age < young_cutoff else max_over

        # Step 2: income reduction using the reduction_table from data
        reduction_table = (
            calc
            .get("step_2_income_reduction", {})
            .get("reduction_table", [])
        )
        # Build lookup from the table in the JSON
        tier = None
        for row in reduction_table:
            nc = row["num_children"]
            if isinstance(nc, int) and nc == num_children:
                tier = row
                break
            if isinstance(nc, str) and nc.endswith("+"):
                min_nc = int(nc.replace("+", ""))
                if num_children >= min_nc:
                    tier = row
                    # don't break — keep looking for a more specific match

        if tier is None:
            # fallback to last row (4+)
            tier = reduction_table[-1] if reduction_table else {
                "rate_mid": 0, "rate_high": 0, "base_reduction": 0
            }

        if family_income <= threshold_1:
            annual = total_max
        elif family_income <= threshold_2:
            annual = max(0, total_max - tier["rate_mid"] * (family_income - threshold_1))
        else:
            annual = max(0, total_max - tier["base_reduction"] - tier["rate_high"] * (family_income - threshold_2))

        return {
            "program_id": pid,
            "currency": amounts.get("currency", "CAD"),
            "frequency": amounts.get("payment_frequency", "monthly"),
            "annual": round(annual, 2),
            "monthly": round(annual / 12, 2),
            "parameters_used": params,
            "inputs_received": inputs,
        }

    # --- EI ---
    elif pid == "employment-insurance":
        weekly_earnings = inputs.get("average_insurable_weekly_earnings", 0)
        rate = params["benefit_rate"] / 100
        max_weekly = params["max_weekly_benefit"]
        weekly = min(rate * weekly_earnings, max_weekly)

        return {
            "program_id": pid,
            "currency": amounts.get("currency", "CAD"),
            "frequency": amounts.get("payment_frequency", "bi-weekly"),
            "weekly": round(weekly, 2),
            "bi_weekly": round(weekly * 2, 2),
            "parameters_used": params,
            "inputs_received": inputs,
        }

    # --- OAS ---
    elif pid == "old-age-security":
        applicant_age = inputs.get("applicant_age", 0)
        years_residence = inputs.get("years_residence_after_18", 0)
        individual_income = inputs.get("individual_net_income", 0)

        full_years = params["full_pension_years"]
        senior_cutoff = params["senior_age_cutoff"]

        if applicant_age >= senior_cutoff:
            max_pension = params["max_monthly_75_plus"]
        else:
            max_pension = params["max_monthly_65_to_74"]

        proportion = min(years_residence / full_years, 1.0)
        base_pension = max_pension * proportion

        clawback_threshold = params["clawback_threshold"]
        clawback_rate = params["clawback_rate"] / 100

        if individual_income > clawback_threshold:
            monthly_clawback = clawback_rate * (individual_income - clawback_threshold) / 12
            pension = max(0, base_pension - monthly_clawback)
        else:
            pension = base_pension

        return {
            "program_id": pid,
            "currency": amounts.get("currency", "CAD"),
            "frequency": amounts.get("payment_frequency", "monthly"),
            "monthly": round(pension, 2),
            "annual": round(pension * 12, 2),
            "full_or_partial": "full" if years_residence >= full_years else "partial",
            "parameters_used": params,
            "inputs_received": inputs,
        }

    return {"error": "No calculation logic implemented for this program"}


# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    return {
        "service": "GC Rules API",
        "version": "0.2.0",
        "status": "experiment",
        "description": "Structured, queryable rules and amounts for GC programs and services.",
        "endpoints": {
            "programs": "/programs",
            "program_detail": "/programs/{program_id}",
            "eligibility": "/programs/{program_id}/eligibility",
            "amounts": "/programs/{program_id}/amounts",
            "parameters": "/programs/{program_id}/parameters",
            "check_eligibility": "/programs/{program_id}/check-eligibility (POST)",
            "calculate": "/programs/{program_id}/calculate (POST)",
        },
    }


@app.get("/programs")
def list_programs(lang: str = Query("en", regex="^(en|fr)$")):
    """List all available programs with basic info."""
    result = []
    for pid, prog in PROGRAMS.items():
        result.append({
            "id": prog["id"],
            "name": prog["name"].get(lang, prog["name"]["en"]),
            "description": prog["description"].get(lang, prog["description"]["en"]),
            "status": prog["status"],
            "administered_by": prog["administered_by"]["name"].get(lang),
            "last_updated": prog["last_updated"],
        })
    return result


@app.get("/programs/{program_id}")
def get_program(program_id: str, lang: Optional[str] = None):
    """Get full program data."""
    prog = PROGRAMS.get(program_id)
    if not prog:
        raise HTTPException(status_code=404, detail=f"Program '{program_id}' not found")
    return prog


@app.get("/programs/{program_id}/eligibility")
def get_eligibility(program_id: str):
    """Get eligibility criteria and decision table for a program."""
    prog = PROGRAMS.get(program_id)
    if not prog:
        raise HTTPException(status_code=404, detail=f"Program '{program_id}' not found")
    return prog.get("eligibility", {})


@app.get("/programs/{program_id}/amounts")
def get_amounts(program_id: str):
    """Get benefit amounts, parameters, and calculation rules for a program."""
    prog = PROGRAMS.get(program_id)
    if not prog:
        raise HTTPException(status_code=404, detail=f"Program '{program_id}' not found")
    return prog.get("amounts", {})


@app.get("/programs/{program_id}/parameters")
def get_parameters(program_id: str):
    """
    Get just the named parameters (the single source of truth for all
    numeric values used in this program's rules and calculations).
    """
    prog = PROGRAMS.get(program_id)
    if not prog:
        raise HTTPException(status_code=404, detail=f"Program '{program_id}' not found")
    return {
        "program_id": program_id,
        "parameters": prog.get("amounts", {}).get("parameters", []),
        "resolved": PARAMS.get(program_id, {}),
    }


@app.post("/programs/{program_id}/check-eligibility")
def check_eligibility(program_id: str, inputs: dict):
    """
    Check eligibility by running inputs through the program's decision table.
    $param: references in conditions are resolved automatically.

    Example body for CCB:
    {
        "child_age": 5,
        "is_primary_caregiver": true,
        "is_canadian_resident_tax": true,
        "immigration_status": "canadian_citizen"
    }
    """
    prog = PROGRAMS.get(program_id)
    if not prog:
        raise HTTPException(status_code=404, detail=f"Program '{program_id}' not found")

    params = PARAMS.get(program_id, {})
    eligibility = prog.get("eligibility", {})
    table = eligibility.get("decision_table")
    if not table:
        raise HTTPException(status_code=400, detail="No decision table available for this program")

    result = evaluate_decision_table(table, inputs, params)
    return {
        "program_id": program_id,
        "inputs": inputs,
        "result": result["outcome"],
        "note": result["note"],
    }


@app.post("/programs/{program_id}/calculate")
def calculate(program_id: str, inputs: dict):
    """
    Calculate estimated benefit amount based on inputs.
    All numeric values come from the program's parameters — no hardcoded numbers.

    Example body for CCB:
    {
        "num_children": 2,
        "children": [{"age": 4}, {"age": 8}],
        "family_net_income": 55000
    }

    Example body for EI:
    {
        "average_insurable_weekly_earnings": 1000
    }

    Example body for OAS:
    {
        "applicant_age": 68,
        "years_residence_after_18": 25,
        "individual_net_income": 40000
    }
    """
    prog = PROGRAMS.get(program_id)
    if not prog:
        raise HTTPException(status_code=404, detail=f"Program '{program_id}' not found")

    return calculate_benefit(prog, inputs)


# ---------------------------------------------------------------------------
# OpenAI-compatible function definitions (for LLM tool use)
# ---------------------------------------------------------------------------

@app.get("/openai-tools")
def get_openai_tools():
    """
    Return OpenAI function-calling tool definitions that an LLM can use
    to query this API.
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "list_gc_programs",
                "description": "List all Government of Canada programs available in the rules API, with their names, descriptions, and status.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "lang": {
                            "type": "string",
                            "enum": ["en", "fr"],
                            "description": "Language for the response (en or fr)",
                        }
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_program_details",
                "description": "Get full details about a specific GC program including eligibility rules, benefit amounts, how to apply, and processing times.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "program_id": {
                            "type": "string",
                            "enum": list(PROGRAMS.keys()),
                            "description": "The program identifier",
                        }
                    },
                    "required": ["program_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_program_parameters",
                "description": "Get the named parameters (thresholds, rates, maximums) for a program. These are the single source of truth for all numeric values.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "program_id": {
                            "type": "string",
                            "enum": list(PROGRAMS.keys()),
                        }
                    },
                    "required": ["program_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "check_eligibility",
                "description": "Check if someone is eligible for a GC program based on their situation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "program_id": {
                            "type": "string",
                            "enum": list(PROGRAMS.keys()),
                        },
                        "inputs": {
                            "type": "object",
                            "description": "Key-value pairs of eligibility inputs (varies by program)",
                        },
                    },
                    "required": ["program_id", "inputs"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "calculate_benefit",
                "description": "Calculate the estimated benefit amount for a GC program based on the applicant's situation (income, family size, age, etc.).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "program_id": {
                            "type": "string",
                            "enum": list(PROGRAMS.keys()),
                        },
                        "inputs": {
                            "type": "object",
                            "description": "Key-value pairs needed for the calculation (varies by program)",
                        },
                    },
                    "required": ["program_id", "inputs"],
                },
            },
        },
    ]
