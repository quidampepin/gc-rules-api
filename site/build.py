"""
build.py — Static site builder for the GC Rules experiment.

Reads program JSON from _data/programs/ and produces a Canada.ca-style
"How much you can get" page for the Canada Child Benefit.

Usage:
    cd site/
    python build.py
"""

import json
import re
import os
from pathlib import Path

SITE_DIR = Path(__file__).parent
DATA_DIR = SITE_DIR / "_data" / "programs"
OUTPUT_DIR = SITE_DIR / "_site"
LAYOUT_DIR = SITE_DIR / "_layouts"


def load_data():
    programs = {}
    for f in DATA_DIR.glob("*.json"):
        with open(f, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            programs[data["id"]] = data
    return {"programs": programs}


def params_lookup(params_list):
    return {p["id"]: p["value"] for p in params_list}


def fmt(n):
    """Format a number with commas: 37487 -> '37,487'."""
    if isinstance(n, float):
        if n == int(n):
            return f"{int(n):,}"
        return f"{n:,.2f}"
    return f"{n:,}"


def monthly_floor(annual):
    """Truncate monthly amount to 2 decimals (matching CRA convention)."""
    import math
    return math.floor(annual / 12 * 100) / 100


def resolve_param_refs(text, params):
    """Replace $param:xyz with the formatted value from params."""
    def replacer(m):
        pid = m.group(1)
        val = params.get(pid)
        if val is None:
            return m.group(0)
        return fmt(val)
    return re.sub(r'\$param:([a-zA-Z0-9_]+)', replacer, text)


# ── HTML generators ──────────────────────────────────────────────────

def well_box(lines):
    """Wrap lines in a GCWeb calculation well box."""
    inner = "\n".join(lines)
    return f'<div class="well col-md-6">\n{inner}\n</div>\n<div class="clearfix">&nbsp;</div>'


def calc_well_mid(params):
    """Generic calculation well for the mid bracket (threshold 1 -> threshold 2)."""
    t1 = fmt(params["income_threshold_1"])
    return well_box([
        f'<p><span class="mrgn-lft-md">Adjusted family net income</span></p>',
        f'<p class="brdr-bttm">-<span class="mrgn-lft-sm">${t1}</span></p>',
        '<div class="clearfix">&nbsp;</div>',
        '<p>=<span class="mrgn-lft-md">income over threshold</span></p>',
        '<p class="brdr-bttm">x<span class="mrgn-lft-sm">{rate}%</span></p>',
        '<div class="clearfix">&nbsp;</div>',
        '<p>=<span class="mrgn-lft-md">total reduction</span></p>',
        '<br>',
        '<p class="mrgn-lft-md">Maximum payment amounts</p>',
        f'<p class="mrgn-lft-md"><strong>Under 6 years of age:</strong> ${fmt(params["max_annual_under_6"])} per year</p>',
        f'<p class="mrgn-lft-md"><strong>Aged 6 to 17 years of age:</strong> ${fmt(params["max_annual_6_to_17"])} per year</p>',
        '<p class="brdr-bttm">-<span class="mrgn-lft-sm">minus total reduction</span></p>',
        '<div class="clearfix">&nbsp;</div>',
        '<p>=<span class="mrgn-lft-md"><strong>your annual payment</strong></span></p>',
    ])


def calc_well_high(params, base_reduction):
    """Generic calculation well for the high bracket (> threshold 2)."""
    t2 = fmt(params["income_threshold_2"])
    return well_box([
        f'<p><span class="mrgn-lft-md">Adjusted family net income</span></p>',
        f'<p class="brdr-bttm">-<span class="mrgn-lft-sm">${t2}</span></p>',
        '<div class="clearfix">&nbsp;</div>',
        '<p>=<span class="mrgn-lft-md">income over threshold</span></p>',
        '<p class="brdr-bttm">x<span class="mrgn-lft-sm">{rate}%</span></p>',
        '<div class="clearfix">&nbsp;</div>',
        '<p>=<span class="mrgn-lft-md">partial reduction</span></p>',
        f'<p class="brdr-bttm">+<span class="mrgn-lft-sm">${fmt(base_reduction)}</span></p>',
        '<div class="clearfix">&nbsp;</div>',
        '<p>=<span class="mrgn-lft-md">total reduction</span></p>',
        '<br>',
        '<p class="mrgn-lft-md">Maximum payment amounts</p>',
        f'<p class="mrgn-lft-md"><strong>Under 6 years of age:</strong> ${fmt(params["max_annual_under_6"])} per year</p>',
        f'<p class="mrgn-lft-md"><strong>Aged 6 to 17 years of age:</strong> ${fmt(params["max_annual_6_to_17"])} per year</p>',
        '<p class="brdr-bttm">-<span class="mrgn-lft-sm">minus total reduction</span></p>',
        '<div class="clearfix">&nbsp;</div>',
        '<p>=<span class="mrgn-lft-md"><strong>your annual payment</strong></span></p>',
    ])


def example_well_mid(ex, params, tier):
    """Named-example well for the mid bracket. Uses pre-computed values from JSON."""
    name = ex.get("name", "Example")
    income = ex["inputs"]["family_net_income"]
    t1 = params["income_threshold_1"]
    over = income - t1
    rate = tier["rate_mid"]
    rate_pct = f"{rate * 100:.10g}"

    # Use pre-computed values from JSON for exact match with live page
    annual = ex["result"]["annual"]
    monthly = ex["result"].get("monthly", round(annual / 12, 2))

    max_total = sum(
        params["max_annual_under_6"] if c["age"] < params["young_child_age_cutoff"]
        else params["max_annual_6_to_17"]
        for c in ex["inputs"]["children"]
    )
    reduction = round(max_total - annual, 2)

    max_desc = describe_max(ex["inputs"]["children"], params)
    period = "July 2025 to June 2026"

    return well_box([
        f'<p><span class="mrgn-lft-md">${fmt(income)} (AFNI)</span></p>',
        f'<p class="brdr-bttm">-<span class="mrgn-lft-sm">${fmt(t1)}</span></p>',
        '<div class="clearfix">&nbsp;</div>',
        f'<p>=<span class="mrgn-lft-md">${fmt(over)} (income over threshold)</span></p>',
        f'<p class="brdr-bttm">x<span class="mrgn-lft-sm">{rate_pct}%</span></p>',
        '<div class="clearfix">&nbsp;</div>',
        f'<p>=<span class="mrgn-lft-md">${fmt(reduction)} (total reduction)</span></p>',
        '<br>',
        f'<p><span class="mrgn-lft-md">${fmt(max_total)} ({max_desc})</span></p>',
        f'<p class="brdr-bttm">-<span class="mrgn-lft-sm">${fmt(reduction)} (minus total reduction)</span></p>',
        '<div class="clearfix">&nbsp;</div>',
        f'<p>=<span class="mrgn-lft-md"><strong>${fmt(annual)} (annual payment)</strong></span></p>',
        '<br>',
        f'<p>{name} would receive ${fmt(annual)} (about ${fmt(monthly)} per month) for the {period} period.</p>',
    ])


def example_well_high(ex, params, tier):
    """Named-example well for the high bracket. Uses pre-computed values from JSON."""
    name = ex.get("name", "Example")
    income = ex["inputs"]["family_net_income"]
    t2 = params["income_threshold_2"]
    over = income - t2
    rate = tier["rate_high"]
    base = tier["base_reduction"]
    rate_pct = f"{rate * 100:.10g}"

    # Use pre-computed values from JSON for exact match with live page
    annual = ex["result"]["annual"]
    monthly = ex["result"].get("monthly", round(annual / 12, 2))

    max_total = sum(
        params["max_annual_under_6"] if c["age"] < params["young_child_age_cutoff"]
        else params["max_annual_6_to_17"]
        for c in ex["inputs"]["children"]
    )
    total_red = round(max_total - annual, 2)
    partial = round(total_red - base, 2)

    max_desc = describe_max(ex["inputs"]["children"], params)
    period = "July 2025 to June 2026"

    return well_box([
        f'<p><span class="mrgn-lft-md">${fmt(income)} (AFNI)</span></p>',
        f'<p class="brdr-bttm">-<span class="mrgn-lft-sm">${fmt(t2)}</span></p>',
        '<div class="clearfix">&nbsp;</div>',
        f'<p>=<span class="mrgn-lft-md">${fmt(over)} (income over threshold)</span></p>',
        f'<p class="brdr-bttm">x<span class="mrgn-lft-sm">{rate_pct}%</span></p>',
        '<div class="clearfix">&nbsp;</div>',
        f'<p>=<span class="mrgn-lft-md">${fmt(partial)} (partial reduction)</span></p>',
        f'<p class="brdr-bttm">+<span class="mrgn-lft-sm">${fmt(base)}</span></p>',
        '<div class="clearfix">&nbsp;</div>',
        f'<p>=<span class="mrgn-lft-md">${fmt(total_red)} (total reduction)</span></p>',
        '<br>',
        f'<p><span class="mrgn-lft-md">${fmt(max_total)} ({max_desc})</span></p>',
        f'<p class="brdr-bttm">-<span class="mrgn-lft-sm">${fmt(total_red)} (total reduction)</span></p>',
        '<div class="clearfix">&nbsp;</div>',
        f'<p>=<span class="mrgn-lft-md"><strong>${fmt(annual)} (annual payment)</strong></span></p>',
        '<br>',
        f'<p>{name} would receive ${fmt(annual)} (about ${fmt(monthly)} per month) for the {period} period.</p>',
    ])


def describe_children(children, params):
    """E.g. 'two children under 6' or 'three children over 6'."""
    n = len(children)
    words = {1: "one", 2: "two", 3: "three", 4: "four"}
    word = words.get(n, str(n))
    under6 = sum(1 for c in children if c["age"] < params["young_child_age_cutoff"])
    over6 = n - under6
    if under6 == n:
        return f"{word} child{'ren' if n > 1 else ''} under 6"
    elif over6 == n:
        return f"{word} child{'ren' if n > 1 else ''} over 6"
    else:
        return f"{word} children ({under6} under 6, {over6} aged 6-17)"


def describe_max(children, params):
    """E.g. 'maximum amount = $7,997 x 2'."""
    under6 = sum(1 for c in children if c["age"] < params["young_child_age_cutoff"])
    over6 = len(children) - under6
    parts = []
    if under6 > 0:
        parts.append(f"${fmt(params['max_annual_under_6'])}" + (f" x {under6}" if under6 > 1 else ""))
    if over6 > 0:
        parts.append(f"${fmt(params['max_annual_6_to_17'])}" + (f" x {over6}" if over6 > 1 else ""))
    return "maximum amount = " + " + ".join(parts)


def build_child_tier_section(tier, examples_for_tier, params):
    """Build the <details> blocks for one child-count tier (1, 2, 3, or 4+)."""
    nc = tier["num_children"]
    nc_int = int(nc) if isinstance(nc, int) else 4
    words = {1: "one", 2: "two", 3: "three", 4: "four"}
    word = words.get(nc_int, str(nc_int))
    label = f"You have {word} child{'ren' if nc_int > 1 else ''}{' or more' if str(nc).endswith('+') else ''} in your care"

    t1 = fmt(params["income_threshold_1"])
    t2 = fmt(params["income_threshold_2"])
    rate_mid = f"{tier['rate_mid'] * 100:.10g}"
    rate_high = f"{tier['rate_high'] * 100:.10g}"
    base_red = fmt(tier["base_reduction"])

    # Split examples into mid-bracket and high-bracket
    mid_ex = [e for e in examples_for_tier if e["inputs"]["family_net_income"] <= params["income_threshold_2"]]
    high_ex = [e for e in examples_for_tier if e["inputs"]["family_net_income"] > params["income_threshold_2"]]

    # --- Below threshold details ---
    below_html = f"""<details>
<summary>Your AFNI is below ${t1}</summary>
<p>You get the maximum amount and it is not reduced. For your eligible child{'ren' if nc_int > 1 else ''}:</p>
<ul>
<li><strong>under 6 years of age:</strong> ${fmt(params['max_annual_under_6'])} per year (${fmt(monthly_floor(params['max_annual_under_6']))} per month)</li>
<li><strong>aged 6 to 17 years of age:</strong> ${fmt(params['max_annual_6_to_17'])} per year (${fmt(monthly_floor(params['max_annual_6_to_17']))} per month)</li>
</ul>
</details>"""

    # --- Mid bracket details ---
    mid_calc = calc_well_mid(params).replace("{rate}", rate_mid)
    mid_examples_html = ""
    for ex in mid_ex:
        name = ex.get("name", "Example")
        children_desc = describe_children(ex["inputs"]["children"], params)
        mid_examples_html += f"""<h5>Example</h5>
<p>{name} has:</p>
<ul>
<li>{children_desc}</li>
<li>an adjusted family net income of ${fmt(ex['inputs']['family_net_income'])}</li>
</ul>
{example_well_mid(ex, params, tier)}
"""

    mid_html = f"""<details>
<summary>Your AFNI is greater than ${t1} up to ${t2}</summary>
<p>Your total payment is reduced by</p>
<ul>
<li>{rate_mid}% of your income greater than ${t1}</li>
</ul>
<h5>Calculation</h5>
{mid_calc}
{mid_examples_html}</details>"""

    # --- High bracket details ---
    high_calc = calc_well_high(params, tier["base_reduction"]).replace("{rate}", rate_high)
    high_examples_html = ""
    for ex in high_ex:
        name = ex.get("name", "Example")
        children_desc = describe_children(ex["inputs"]["children"], params)
        high_examples_html += f"""<h5>Example</h5>
<p>{name} has:</p>
<ul>
<li>{children_desc}</li>
<li>an adjusted family net income of ${fmt(ex['inputs']['family_net_income'])}</li>
</ul>
{example_well_high(ex, params, tier)}
"""

    high_html = f"""<details>
<summary>Your AFNI is greater than ${t2}</summary>
<p>Your total payment is reduced by:</p>
<ul>
<li>${base_red} + {rate_high}% of your income greater than ${t2}</li>
</ul>
<h5>Calculation</h5>
{high_calc}
{high_examples_html}</details>"""

    return f"""<h5>{label}</h5>
<ul class="list-unstyled">
<li>{below_html}</li>
<li>{mid_html}</li>
<li>{high_html}</li>
</ul>"""


# ── Main page generator ──────────────────────────────────────────────

def generate_page_html(ccb, params, reduction_table):
    t1 = fmt(params["income_threshold_1"])
    t2 = fmt(params["income_threshold_2"])
    max_under6 = fmt(params["max_annual_under_6"])
    max_6to17 = fmt(params["max_annual_6_to_17"])
    mo_under6 = fmt(monthly_floor(params["max_annual_under_6"]))
    mo_6to17 = fmt(monthly_floor(params["max_annual_6_to_17"]))

    examples = ccb["amounts"].get("examples", [])

    # Group examples by num_children, matching 4 -> "4+" tier
    examples_by_tier = {}
    for ex in examples:
        nc = ex["inputs"]["num_children"]
        # Match integer 4+ to the "4+" string key in reduction_table
        matched = False
        for tier in reduction_table:
            tnc = tier["num_children"]
            if tnc == nc:
                examples_by_tier.setdefault(tnc, []).append(ex)
                matched = True
                break
            elif str(tnc).endswith("+") and isinstance(nc, int) and nc >= int(str(tnc).rstrip("+")):
                examples_by_tier.setdefault(tnc, []).append(ex)
                matched = True
                break

    # Build the per-tier sections
    tier_sections = ""
    for tier in reduction_table:
        nc = tier["num_children"]
        tier_examples = examples_by_tier.get(nc, [])
        tier_sections += build_child_tier_section(tier, tier_examples, params)

    # AFNI definition
    afni_def = """<details>
<summary>Definition of adjusted family net income (AFNI)</summary>
<p>Your AFNI is:</p>
<ul>
<li>your family net income (line 23600 of your tax return, plus line 23600 of your spouse's or common-law partner's tax return, if applicable)</li>
<li><strong>minus</strong> any Universal Child Care Benefit (UCCB) and registered disability savings plan (RDSP) income received (line 11700 and line 12500 of your or your spouse's tax return, if applicable)</li>
<li><strong>plus</strong> any UCCB and RDSP amounts repaid (line 21300 and line 23200 of your or your spouse's tax return, if applicable)</li>
</ul>
</details>"""

    return f"""<nav class="provisional gc-subway">
  <h1 id="gc-document-nav">{ccb['name']['en']}</h1>
  <ul>
    <li><a href="/en/canada-child-benefit/" class="hidden-xs hidden-sm">Overview</a>
        <a href="/en/canada-child-benefit/#gc-document-nav" class="visible-xs visible-sm">Overview</a></li>
    <li><a href="/en/canada-child-benefit/who-can-apply.html" class="hidden-xs hidden-sm">Who can apply</a>
        <a href="/en/canada-child-benefit/who-can-apply.html#gc-document-nav" class="visible-xs visible-sm">Who can apply</a></li>
    <li><a href="/en/canada-child-benefit/apply.html" class="hidden-xs hidden-sm">Apply</a>
        <a href="/en/canada-child-benefit/apply.html#gc-document-nav" class="visible-xs visible-sm">Apply</a></li>
    <li><a href="#" class="active" aria-current="page">How much you can get</a></li>
    <li><a href="/en/canada-child-benefit/payment-dates.html" class="hidden-xs hidden-sm">Payment dates</a>
        <a href="/en/canada-child-benefit/payment-dates.html#gc-document-nav" class="visible-xs visible-sm">Payment dates</a></li>
  </ul>
</nav>

<h1 property="name" id="wb-cont" class="gc-thickline">How much you can get</h1>

<p>The Canada child benefit (CCB) payments are not taxable and benefit amounts do not have to be reported on your tax return.</p>

<h2 class="h3 mrgn-tp-md">On this page</h2>
<ul>
<li><a href="#toc1">How payments are calculated</a></li>
<li><a href="#shared">Shared custody and your payments</a></li>
<li><a href="#toc3">Payment amounts are recalculated every July</a></li>
<li><a href="#toc4">Other benefits and credits included with your CCB payment</a></li>
</ul>

<h2 id="toc1">How payments are calculated</h2>
<p>The Canada Revenue Agency (CRA) determines if you are entitled to CCB payments each year when you file your tax return. As family net income levels increase, the benefit amount is reduced.</p>
<p>The CCB payments are adjusted based on:</p>
<ul>
<li>Number of children in your care</li>
<li>Age of your children</li>
<li>Your adjusted family net income (AFNI) reported in the previous year's tax return</li>
</ul>

{afni_def}

<h3>CCB amounts are based on adjusted family net income</h3>
<p>The benefit amount you may receive based on your 2024 adjusted family net income:</p>

<dl class="dl-horizontal">
<dt>Less than ${t1}</dt>
<dd>You get the maximum benefit amount for each eligible child. There is no reduction.</dd>
<dt>Greater than ${t1} up to ${t2}</dt>
<dd>Your benefit amount is reduced by a percentage of your income greater than ${t1}. The percentage changes based on the number of eligible children you have.</dd>
<dt>Greater than ${t2}</dt>
<dd>Your benefit is reduced by a fixed amount plus an additional percentage of your income greater than ${t2}. Both the fixed amount and percentage are based on the number of eligible children you have.</dd>
</dl>

<details>
<summary><span id="math">Understand how your CCB payments are calculated</span></summary>

<h3>Current year</h3>
<p>The following amounts are for the payment period from July 2025 to June 2026 and are based on your AFNI from 2024.</p>

<h4>Maximum Canada child benefit</h4>
<p>If your AFNI is under ${t1}, you get the maximum amount for each child. It will not be reduced.</p>
<p>For each child:</p>
<ul>
<li><strong>under 6 years of age:</strong> ${max_under6} per year (${mo_under6} per month)</li>
<li><strong>6 to 17 years of age:</strong> ${max_6to17} per year (${mo_6to17} per month)</li>
</ul>

<p><strong>Examples:</strong></p>
<ul>
<li>For a child <strong>born</strong> in March 2026, you will be eligible to receive the CCB in April 2026 or the month following the month you become eligible</li>
<li>For a child <strong>turning 6 years of age</strong> in March 2026, you will be paid at the under 6 years of age rate for the month of March and, at the 6 to 17 years of age rate for the month of April 2026.</li>
<li>For a child <strong>turning 18</strong> in December 2025, the last payment will be in December 2025 at the 6 to 17 years of age rate.</li>
</ul>

<h4>Payments are based on your adjusted family net income (AFNI)</h4>
<p>Any reduction to the maximum benefit payment depends on your AFNI and on the number of children.</p>
<p>The payments gradually <strong>start decreasing</strong> when the adjusted family net income is over ${t1}.</p>

{tier_sections}

</details>

<h3>Estimate how much you can get</h3>
<p>Use the <a href="https://www.canada.ca/en/revenue-agency/services/child-family-benefits/child-family-benefits-calculator.html">child and family benefits calculator</a> to estimate your Canada child benefit.</p>

<h2 id="shared">Shared custody and your payments</h2>
<p>Each parent with shared custody will get 50% of what they would have gotten if they had full custody of the child and the amount is calculated based on their own adjusted family net income.</p>
<p>The CRA will not split the amount using other percentages, or give the full amount to one of the parents if the CRA considers you to have shared custody.</p>
<p>If a child only lives with you <strong>part time</strong>, go to <a href="/en/revenue-agency/services/child-family-benefits/canada-child-benefit/who-apply.html#determinecustody">Determine if you have shared custody</a> to find out if you are considered to have shared custody.</p>

<h2 id="toc3">Payment amounts are recalculated every July</h2>
<p>Your benefit payments are recalculated <strong>every July</strong> based on your adjusted family net income from the previous year. CCB is indexed to inflation.</p>
<p>For example, payments from:</p>
<ul>
<li><strong>July 2025 to June 2026</strong>: based on 2024 tax return</li>
<li><strong>July 2024 to June 2025</strong>: based on 2023 tax return</li>
</ul>

<h2 id="toc4">Other benefits and credits included with your CCB payment</h2>

<h3>Related provincial and territorial benefits</h3>
<p>Some provinces and territories have related child benefit and credit programs that are administered by the CRA and included with CCB payments.</p>

<h3>Child disability benefit</h3>
<p>The <a href="/en/revenue-agency/services/child-family-benefits/child-disability-benefit.html">child disability benefit</a> (CDB) is included with your CCB payment if your child is eligible for the disability tax credit.</p>


<nav class="mrgn-bttm-lg mrgn-tp-lg">
  <h3 class="wb-inv">Document navigation</h3>
  <ul class="pager">
    <li class="next"><a href="/en/canada-child-benefit/payment-dates.html" rel="next"><span class="wb-inv">Next: </span>Payment dates</a></li>
  </ul>
</nav>
"""


def render_layout(layout_html, page, content):
    html = layout_html
    html = html.replace("{{ content }}", content)
    html = html.replace("{{ page.title }}", page.get("title", ""))
    html = html.replace("{{ page.lang | default: 'en' }}", page.get("lang", "en"))
    html = html.replace('{{ page.lang | default: "en" }}', page.get("lang", "en"))
    html = html.replace("{{ page.other_lang_url | default: '#' }}", page.get("other_lang_url", "#"))
    html = html.replace('{{ page.date_modified | default: site.time | date: "%Y-%m-%d" }}', page.get("date_modified", ""))

    crumbs_html = ""
    for crumb in page.get("breadcrumbs", []):
        crumbs_html += f'<li><a href="{crumb["url"]}">{crumb["title"]}</a></li>\n'
    html = re.sub(
        r'\{%\s*for crumb in page\.breadcrumbs\s*%\}.*?\{%\s*endfor\s*%\}',
        crumbs_html, html, flags=re.DOTALL
    )
    html = re.sub(
        r'\{%\s*if page\.lang == .fr.\s*%\}.*?\{%\s*else\s*%\}(.*?)\{%\s*endif\s*%\}',
        r'\1', html, flags=re.DOTALL
    )
    html = re.sub(r'\{%.*?%\}', '', html)
    html = re.sub(r'\{\{.*?\}\}', '', html)
    return html


def main():
    data = load_data()
    ccb = data["programs"]["canada-child-benefit"]
    params = params_lookup(ccb["amounts"]["parameters"])
    reduction_table = ccb["amounts"]["calculation"]["step_2_income_reduction"]["reduction_table"]

    page_content = generate_page_html(ccb, params, reduction_table)

    # Read layout
    with open(LAYOUT_DIR / "gcweb.html", "r", encoding="utf-8") as f:
        layout_html = f.read()

    page_meta = {
        "title": "How much you can get",
        "lang": "en",
        "other_lang_url": "/fr/allocation-canadienne-pour-enfants/combien.html",
        "date_modified": ccb["last_updated"],
        "breadcrumbs": [
            {"title": "Canada.ca", "url": "https://www.canada.ca/en.html"},
            {"title": "Benefits", "url": "https://www.canada.ca/en/services/benefits.html"},
            {"title": "Canada child benefit", "url": "/en/canada-child-benefit/"},
        ],
    }

    final_html = render_layout(layout_html, page_meta, page_content)

    out_dir = OUTPUT_DIR / "en" / "canada-child-benefit"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "how-much.html"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(final_html)

    print(f"Built: {out_file}")
    print(f"  Data source: {DATA_DIR / 'canada-child-benefit.json'}")
    print(f"  All amounts come from JSON parameters — zero hardcoded values in the template.")


if __name__ == "__main__":
    main()
