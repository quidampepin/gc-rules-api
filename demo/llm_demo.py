"""
LLM Function-Calling Demo
==========================
Demonstrates how a GenAI chatbot can use the GC Rules API to answer
questions about Canadian government programs with authoritative,
structured data — instead of relying on training data or web scraping.

This demo simulates the function-calling flow:
1. User asks a question in natural language
2. The LLM decides which API endpoint to call
3. The API returns structured data
4. The LLM formulates a human-readable answer grounded in that data

No actual LLM API key is needed — this demo uses httpx to call the
local Rules API and shows the full request/response cycle.

Usage:
    # First, start the API server:
    cd gc-rules-api && uvicorn api.main:app --reload --port 8000

    # Then run this demo:
    python demo/llm_demo.py
"""

import httpx
import json
import sys

API_BASE = "http://localhost:8000"


def separator(title: str):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")


def call_api(method: str, path: str, body: dict = None) -> dict:
    """Call the local GC Rules API."""
    url = f"{API_BASE}{path}"
    if method == "GET":
        r = httpx.get(url)
    else:
        r = httpx.post(url, json=body)
    r.raise_for_status()
    return r.json()


def demo_scenario_1():
    """
    Scenario: "How much Canada Child Benefit would I get? I have 2 kids
    (ages 4 and 8) and our family income is $55,000."
    """
    separator("SCENARIO 1: CCB Benefit Calculation")

    print("User: How much Canada Child Benefit would I get? I have 2 kids")
    print("      (ages 4 and 8) and our family income is $55,000.\n")

    print("--- LLM decides to call: POST /programs/canada-child-benefit/calculate ---\n")

    inputs = {
        "num_children": 2,
        "children": [{"age": 4}, {"age": 8}],
        "family_net_income": 55000,
    }
    print(f"Request body: {json.dumps(inputs, indent=2)}\n")

    result = call_api("POST", "/programs/canada-child-benefit/calculate", inputs)
    print(f"API response: {json.dumps(result, indent=2)}\n")

    # Simulated LLM response using the API data
    print("--- LLM response (grounded in API data) ---\n")
    print(f"Based on your family situation, you would receive approximately")
    print(f"${result['monthly']:,.2f} per month (${result['annual']:,.2f} per year)")
    print(f"in Canada Child Benefit payments.")
    print(f"\nThis accounts for:")
    print(f"  - 1 child under 6 (max ${result['parameters_used']['max_annual_under_6']:,}/year)")
    print(f"  - 1 child aged 6-17 (max ${result['parameters_used']['max_annual_6_to_17']:,}/year)")
    print(f"  - Income-based reduction (your AFNI of $55,000 is above the")
    print(f"    ${result['parameters_used']['income_threshold_1']:,} threshold)")


def demo_scenario_2():
    """
    Scenario: "Am I eligible for EI? I was laid off and worked for 8 months."
    """
    separator("SCENARIO 2: EI Eligibility Check")

    print("User: Am I eligible for EI? I was laid off last week and worked")
    print("      for 8 months full-time (about 1,400 hours).\n")

    print("--- LLM decides to call: POST /programs/employment-insurance/check-eligibility ---\n")

    inputs = {
        "was_insurable_employment": True,
        "separation_reason": "shortage_of_work",
        "consecutive_days_without_work": 7,
        "insurable_hours": 1400,
        "regional_unemployment_rate": 6.5,
        "is_ready_willing_capable": True,
    }
    print(f"Request body: {json.dumps(inputs, indent=2)}\n")

    result = call_api("POST", "/programs/employment-insurance/check-eligibility", inputs)
    print(f"API response: {json.dumps(result, indent=2)}\n")

    print("--- LLM response (grounded in API data) ---\n")
    print(f"Based on the information you provided, you {result['result'].replace('_', ' ')}.")
    print(f"You were laid off (not your fault), worked 1,400 insurable hours")
    print(f"(well above the minimum of 420), and are ready to work.")

    # Also calculate the amount
    print("\n--- LLM follows up with: POST /programs/employment-insurance/calculate ---\n")
    calc_inputs = {"average_insurable_weekly_earnings": 850}
    calc_result = call_api("POST", "/programs/employment-insurance/calculate", calc_inputs)
    print(f"API response: {json.dumps(calc_result, indent=2)}\n")
    print("--- LLM continues ---\n")
    print(f"If your average weekly earnings were around $850, you'd receive")
    print(f"approximately ${calc_result['weekly']:,.2f}/week (55% of your earnings,")
    print(f"capped at ${calc_result['parameters_used']['max_weekly_benefit']}/week max).")


def demo_scenario_3():
    """
    Scenario: "What programs are available and what's the OAS amount for
    someone who lived here 25 years?"
    """
    separator("SCENARIO 3: Browse Programs + OAS Partial Pension")

    print("User: What benefits programs do you have info on? And how much OAS")
    print("      would I get if I'm 68 and lived in Canada for 25 years?\n")

    print("--- LLM decides to call: GET /programs ---\n")
    programs = call_api("GET", "/programs?lang=en")
    print(f"Available programs: {json.dumps(programs, indent=2)}\n")

    print("--- LLM then calls: POST /programs/old-age-security/calculate ---\n")
    inputs = {
        "applicant_age": 68,
        "years_residence_after_18": 25,
        "individual_net_income": 40000,
    }
    result = call_api("POST", "/programs/old-age-security/calculate", inputs)
    print(f"API response: {json.dumps(result, indent=2)}\n")

    print("--- LLM response (grounded in API data) ---\n")
    print(f"I have information on {len(programs)} programs:")
    for p in programs:
        print(f"  - {p['name']} ({p['status']})")
    print(f"\nFor OAS: since you're 68 and lived in Canada 25 years (out of 40")
    print(f"needed for a full pension), you'd receive a {result['full_or_partial']}")
    print(f"pension of approximately ${result['monthly']:,.2f}/month.")
    print(f"Your income of $40,000 is below the clawback threshold, so no")
    print(f"recovery tax applies.")


def demo_scenario_4_bilingual():
    """
    Scenario: Same query in French
    """
    separator("SCENARIO 4: Bilingual — French response")

    print("User: Quels sont les montants de l'Allocation canadienne pour enfants?\n")

    print("--- LLM calls: GET /programs/canada-child-benefit/amounts ---\n")
    amounts = call_api("GET", "/programs/canada-child-benefit/amounts")

    params = {p["id"]: p for p in amounts["parameters"]}
    print("--- LLM response (in French, using fr fields) ---\n")
    print(f"Voici les montants maximaux de l'ACE :")
    annual_u6 = params['max_annual_under_6']['value']
    monthly_u6 = int(annual_u6) // 12
    print(f"  - {params['max_annual_under_6']['label']['fr']}: "
          f"{annual_u6:,} $ par année "
          f"({monthly_u6} $ par mois)")
    annual_6_17 = params['max_annual_6_to_17']['value']
    monthly_6_17 = int(annual_6_17) // 12
    print(f"  - {params['max_annual_6_to_17']['label']['fr']}: "
          f"{annual_6_17:,} $ par année "
          f"({monthly_6_17} $ par mois)")
    print(f"\nCes montants sont réduits si votre revenu familial net rajusté")
    print(f"dépasse {params['income_threshold_1']['value']:,} $.")


def main():
    # Check if API is running
    try:
        httpx.get(f"{API_BASE}/", timeout=3)
    except httpx.ConnectError:
        print("ERROR: GC Rules API is not running.")
        print("Start it first with: uvicorn api.main:app --reload --port 8000")
        sys.exit(1)

    demo_scenario_1()
    demo_scenario_2()
    demo_scenario_3()
    demo_scenario_4_bilingual()

    separator("SUMMARY")
    print("This demo showed 4 scenarios where an LLM uses the GC Rules API")
    print("to provide grounded, accurate answers about government programs.")
    print()
    print("Key takeaways:")
    print("  1. The LLM never needs to 'know' the rules — it queries them")
    print("  2. Amounts are always current (updated in one place)")
    print("  3. Eligibility checks are deterministic, not probabilistic")
    print("  4. Bilingual by design — same data, both languages")
    print("  5. The API doubles as documentation (self-describing)")
    print()
    print("Next steps:")
    print("  - Connect this to a real LLM with function calling (Claude, GPT-4)")
    print("  - Add more programs")
    print("  - Build a web frontend that pulls amounts from the API")
    print("  - Version the rules (track changes over time)")


if __name__ == "__main__":
    main()
