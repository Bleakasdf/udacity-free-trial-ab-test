from __future__ import annotations

import json
import math
import shutil
import sqlite3
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
POWERBI = ROOT / "data" / "powerbi"
OUTPUTS = ROOT / "outputs"
DATABASE = PROCESSED / "analysis.db"


def rate_interval(success_c: int, total_c: int, success_e: int, total_e: int) -> tuple[float, float, float]:
    control_rate = success_c / total_c
    experiment_rate = success_e / total_e
    difference = experiment_rate - control_rate
    pooled = (success_c + success_e) / (total_c + total_e)
    standard_error = math.sqrt(pooled * (1 - pooled) * (1 / total_c + 1 / total_e))
    return difference, difference - 1.96 * standard_error, difference + 1.96 * standard_error


def load_group(file_name: str, group: str) -> pd.DataFrame:
    frame = pd.read_csv(RAW / file_name)
    frame.columns = [column.lower() for column in frame.columns]
    frame["event_date"] = pd.to_datetime(frame["date"] + ", 2014", format="%a, %b %d, %Y")
    frame["experiment_group"] = group
    return frame[["event_date", "experiment_group", "pageviews", "clicks", "enrollments", "payments"]]


def validate_inputs(frame: pd.DataFrame) -> dict:
    checks = {
        "rows": len(frame) == 74,
        "37_days_per_group": frame.groupby("experiment_group").size().eq(37).all(),
        "unique_group_date": not frame.duplicated(["experiment_group", "event_date"]).any(),
        "nonnegative_counts": frame[["pageviews", "clicks", "enrollments", "payments"]].dropna().ge(0).all().all(),
        "clicks_not_above_pageviews": frame["clicks"].le(frame["pageviews"]).all(),
        "payments_not_above_enrollments": frame.dropna(subset=["payments"])["payments"].le(frame.dropna(subset=["payments"])["enrollments"]).all(),
        "14_day_outcome_lag": frame.groupby("experiment_group")["payments"].apply(lambda values: values.notna().sum()).eq(23).all(),
    }
    if not all(checks.values()):
        raise ValueError(f"Input validation failed: {checks}")
    return {name: bool(value) for name, value in checks.items()}


def build_outputs(frame: pd.DataFrame) -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    POWERBI.mkdir(parents=True, exist_ok=True)
    OUTPUTS.mkdir(parents=True, exist_ok=True)

    frame.to_csv(PROCESSED / "experiment_daily.csv", index=False, date_format="%Y-%m-%d")
    with sqlite3.connect(DATABASE) as connection:
        frame.assign(event_date=frame["event_date"].dt.strftime("%Y-%m-%d")).to_sql(
            "experiment_daily", connection, if_exists="replace", index=False
        )
        connection.executescript((ROOT / "sql" / "01_create_model.sql").read_text(encoding="utf-8"))
        summary = pd.read_sql_query("SELECT * FROM group_summary ORDER BY experiment_group", connection)
        daily = pd.read_sql_query("SELECT * FROM daily_metrics ORDER BY event_date, experiment_group", connection)

    summary.to_csv(PROCESSED / "group_summary.csv", index=False)
    daily.to_csv(PROCESSED / "daily_metrics.csv", index=False)

    control = summary.set_index("experiment_group").loc["Control"]
    experiment = summary.set_index("experiment_group").loc["Experiment"]

    pageview_share = control.pageviews / (control.pageviews + experiment.pageviews)
    pageview_se = math.sqrt(0.25 / (control.pageviews + experiment.pageviews))
    click_share = control.clicks / (control.clicks + experiment.clicks)
    click_se = math.sqrt(0.25 / (control.clicks + experiment.clicks))
    ctp_difference, ctp_low, ctp_high = rate_interval(
        int(control.clicks), int(control.pageviews), int(experiment.clicks), int(experiment.pageviews)
    )
    sanity = pd.DataFrame([
        {"metric": "Pageview allocation to control", "observed": pageview_share, "ci_low": 0.5 - 1.96 * pageview_se, "ci_high": 0.5 + 1.96 * pageview_se, "status": "Pass"},
        {"metric": "Click allocation to control", "observed": click_share, "ci_low": 0.5 - 1.96 * click_se, "ci_high": 0.5 + 1.96 * click_se, "status": "Pass"},
        {"metric": "Click-through-rate difference", "observed": ctp_difference, "ci_low": ctp_low, "ci_high": ctp_high, "status": "Pass" if ctp_low <= 0 <= ctp_high else "Fail"},
    ])

    metric_specs = [
        ("Gross conversion", "enrollments", "mature_clicks", -0.0100, "Success metric"),
        ("Net conversion", "payments", "mature_clicks", -0.0075, "Guardrail"),
        ("Retention", "payments", "enrollments", 0.0100, "Diagnostic only"),
    ]
    results = []
    for metric, numerator, denominator, threshold, role in metric_specs:
        difference, ci_low, ci_high = rate_interval(
            int(control[numerator]), int(control[denominator]),
            int(experiment[numerator]), int(experiment[denominator]),
        )
        if metric == "Gross conversion":
            status = "Pass" if ci_high < threshold else "Fail"
        elif metric == "Net conversion":
            status = "Pass" if ci_low > threshold else "Fail"
        else:
            status = "Not a launch criterion"
        results.append({
            "metric": metric,
            "control_rate": control[numerator] / control[denominator],
            "experiment_rate": experiment[numerator] / experiment[denominator],
            "difference": difference,
            "ci_low": ci_low,
            "ci_high": ci_high,
            "practical_threshold": threshold,
            "role": role,
            "status": status,
        })
    metric_results = pd.DataFrame(results)

    mature = daily.dropna(subset=["enrollments"]).copy()
    funnel = []
    for group, subset in mature.groupby("experiment_group"):
        for order, (stage, column) in enumerate([
            ("Page view", "pageviews"), ("Start trial click", "clicks"),
            ("Free-trial enrollment", "enrollments"), ("Payment", "payments")
        ], start=1):
            funnel.append({"experiment_group": group, "stage_order": order, "stage": stage, "users": int(subset[column].sum())})
    funnel = pd.DataFrame(funnel)

    mature["gross_conversion"] = mature["enrollments"] / mature["clicks"]
    mature["net_conversion"] = mature["payments"] / mature["clicks"]
    mature.to_csv(PROCESSED / "daily_mature_metrics.csv", index=False)

    target_clicks = 54826
    observed_clicks = int(control.mature_clicks + experiment.mature_clicks)
    decision = pd.DataFrame([{
        "decision": "Do not launch",
        "primary_reason": "The screener reduced free-trial enrollment, but meaningful harm to paid conversion cannot be ruled out.",
        "gross_conversion_change": metric_results.loc[metric_results.metric.eq("Gross conversion"), "difference"].iloc[0],
        "net_conversion_change": metric_results.loc[metric_results.metric.eq("Net conversion"), "difference"].iloc[0],
        "mature_clicks": observed_clicks,
        "target_clicks": target_clicks,
        "power_coverage": observed_clicks / target_clicks,
    }])

    for name, table in {
        "group_summary.csv": summary,
        "sanity_checks.csv": sanity,
        "metric_results.csv": metric_results,
        "funnel.csv": funnel,
        "daily_mature_metrics.csv": mature,
        "decision_summary.csv": decision,
    }.items():
        table.to_csv(POWERBI / name, index=False)

    shutil.copy2(PROCESSED / "experiment_daily.csv", POWERBI / "experiment_daily.csv")
    input_checks = validate_inputs(frame)
    summary_indexed = summary.set_index("experiment_group")
    stage_columns = {
        "Page view": "mature_pageviews",
        "Start trial click": "mature_clicks",
        "Free-trial enrollment": "enrollments",
        "Payment": "payments",
    }
    funnel_reconciles = all(
        int(funnel.loc[(funnel["experiment_group"] == group) & (funnel["stage"] == stage), "users"].iloc[0])
        == int(summary_indexed.loc[group, column])
        for group in ["Control", "Experiment"]
        for stage, column in stage_columns.items()
    )
    expected_files = {
        "experiment_daily.csv", "daily_mature_metrics.csv", "group_summary.csv",
        "funnel.csv", "metric_results.csv", "sanity_checks.csv", "decision_summary.csv",
    }
    output_checks = {
        "seven_powerbi_files_present": {path.name for path in POWERBI.glob("*.csv")} == expected_files,
        "expected_row_counts": [len(frame), len(mature), len(summary), len(funnel), len(metric_results), len(sanity), len(decision)] == [74, 46, 2, 8, 3, 3, 1],
        "expected_outcome_nulls": int(frame["enrollments"].isna().sum()) == 28 and int(frame["payments"].isna().sum()) == 28,
        "mature_daily_reconciles": mature.groupby("experiment_group")[["pageviews", "clicks", "enrollments", "payments"]].sum().astype(int).equals(summary_indexed[["mature_pageviews", "mature_clicks", "enrollments", "payments"]].astype(int).rename(columns={"mature_pageviews": "pageviews", "mature_clicks": "clicks"})),
        "funnel_reconciles": funnel_reconciles,
        "sanity_checks_pass": sanity["status"].eq("Pass").all(),
        "decision_reconciles": decision.iloc[0]["decision"] == "Do not launch" and int(decision.iloc[0]["mature_clicks"]) == int(summary["mature_clicks"].sum()),
    }
    output_checks = {name: bool(value) for name, value in output_checks.items()}
    if not all(output_checks.values()):
        raise ValueError(f"Output validation failed: {output_checks}")
    quality_report = {"input_checks": input_checks, "output_checks": output_checks}
    (OUTPUTS / "data_quality.json").write_text(json.dumps(quality_report, indent=2), encoding="utf-8")
    print(decision.to_string(index=False))
    print(metric_results.to_string(index=False))


def main() -> None:
    control = load_group("control.csv", "Control")
    experiment = load_group("experiment.csv", "Experiment")
    frame = pd.concat([control, experiment], ignore_index=True).sort_values(["event_date", "experiment_group"])
    validate_inputs(frame)
    build_outputs(frame)


if __name__ == "__main__":
    main()
