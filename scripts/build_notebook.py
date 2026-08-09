from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks" / "udacity_ab_test.ipynb"


def markdown(source: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": source.splitlines(True)}


def code(source: str) -> dict:
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": source.splitlines(True)}


cells = [
    markdown("""# Udacity free-trial readiness screener

**Business question:** Should Udacity launch a readiness screen before the free trial?

**Answer:** **Do not launch yet.** The screen reduces free-trial enrollments, but the experiment does not rule out meaningful harm to paid conversion.
"""),
    markdown("""## 1. Decision framework

- **Success metric — Gross conversion:** reduce trial enrollments by at least 1 percentage point.
- **Guardrail — Net conversion:** paid conversion must not fall by more than 0.75 percentage points.
- **Diagnostic — Retention:** payments per enrollment; useful for interpretation, not a launch criterion.
- Enrollment and payment outcomes are available for only the first 23 days because they require a 14-day maturity window.
"""),
    code("""from pathlib import Path
import sqlite3
import pandas as pd

ROOT = Path.cwd().parent if Path.cwd().name == 'notebooks' else Path.cwd()
DB = ROOT / 'data' / 'processed' / 'analysis.db'
POWERBI = ROOT / 'data' / 'powerbi'
"""),
    markdown("## 2. Data quality and experiment health"),
    code("""daily = pd.read_csv(ROOT / 'data' / 'processed' / 'experiment_daily.csv')
quality = pd.Series({
    'Rows': len(daily),
    'Days per group': daily.groupby('experiment_group').size().min(),
    'Duplicate group-dates': daily.duplicated(['experiment_group', 'event_date']).sum(),
    'Mature days per group': daily.groupby('experiment_group')['payments'].count().min(),
})
print(quality.to_string())
"""),
    code("""sanity = pd.read_csv(POWERBI / 'sanity_checks.csv')
print(sanity.to_string(index=False, formatters={
    'observed': '{:.3%}'.format, 'ci_low': '{:.3%}'.format, 'ci_high': '{:.3%}'.format
}))
"""),
    markdown("All pre-treatment checks pass: traffic is balanced and the click-through-rate difference is compatible with random variation."),
    markdown("## 3. SQL model and mature funnel"),
    code("""query = '''
SELECT experiment_group, mature_pageviews, mature_clicks, enrollments, payments,
       gross_conversion, net_conversion, retention
FROM group_summary
ORDER BY experiment_group;
'''
with sqlite3.connect(DB) as connection:
    summary = pd.read_sql_query(query, connection)
print(summary.to_string(index=False, formatters={
    'gross_conversion': '{:.2%}'.format,
    'net_conversion': '{:.2%}'.format,
    'retention': '{:.2%}'.format,
}))
"""),
    markdown("The screener acts between the trial click and enrollment. Therefore the main comparison uses mature clicks as the denominator for both trial and paid conversion."),
    markdown("## 4. Metric effects and uncertainty"),
    code("""results = pd.read_csv(POWERBI / 'metric_results.csv')
print(results.to_string(index=False, formatters={
    'control_rate': '{:.2%}'.format, 'experiment_rate': '{:.2%}'.format,
    'difference': '{:+.2%}'.format, 'ci_low': '{:+.2%}'.format,
    'ci_high': '{:+.2%}'.format, 'practical_threshold': '{:+.2%}'.format,
}))
"""),
    markdown("""## 5. Decision

1. Gross conversion fell by **2.06 pp**; its confidence interval is entirely beyond the **−1.00 pp** practical target. The screen successfully filters trial enrollments.
2. Net conversion fell by **0.49 pp**, but its 95% CI is **−1.16 to +0.19 pp**. Because the lower bound crosses the **−0.75 pp** guardrail, meaningful harm to paid conversion cannot be excluded.
3. Only **34,553 of 54,826** required mature clicks were observed (about **63%** of the planned information).

**Recommendation:** do not launch the screen to all users. Continue the experiment to the planned sample size or test a less restrictive message, then launch only if the paid-conversion guardrail passes.
"""),
]


def execute_code_cells(items: list[dict]) -> None:
    namespace = {"__name__": "__notebook__"}
    count = 0
    old_cwd = Path.cwd()
    try:
        import os
        os.chdir(ROOT)
        for cell in items:
            if cell["cell_type"] != "code":
                continue
            count += 1
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                exec(compile("".join(cell["source"]), f"cell_{count}", "exec"), namespace)
            cell["execution_count"] = count
            output = stream.getvalue()
            if output:
                cell["outputs"] = [{"name": "stdout", "output_type": "stream", "text": output.splitlines(True)}]
    finally:
        os.chdir(old_cwd)


execute_code_cells(cells)
notebook = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}
NOTEBOOK.parent.mkdir(parents=True, exist_ok=True)
NOTEBOOK.write_text(json.dumps(notebook, indent=1, ensure_ascii=False), encoding="utf-8")
print(NOTEBOOK)
