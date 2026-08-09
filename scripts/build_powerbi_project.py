from __future__ import annotations

import json
import shutil
import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "powerbi" / "project"
REPORT = PROJECT / "UdacityABTest.Report"
MODEL = PROJECT / "UdacityABTest.SemanticModel"
PAGES = REPORT / "definition" / "pages"

SCHEMA_VISUAL = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.9.0/schema.json"
INK, TEXT, BLUE, ORANGE, GREEN = "#172B4D", "#344054", "#2F6B9A", "#D9892B", "#287D5A"
BORDER, BACKGROUND = "#D9E2EC", "#F5F7FA"

TABLES = {
    "group_summary": {
        "file": "group_summary.csv",
        "columns": {"experiment_group": "string", "pageviews": "int64", "clicks": "int64", "mature_pageviews": "int64", "mature_clicks": "int64", "enrollments": "int64", "payments": "int64", "click_through_rate": "double", "gross_conversion": "double", "net_conversion": "double", "retention": "double"},
        "formats": {"click_through_rate": "0.00%", "gross_conversion": "0.00%", "net_conversion": "0.00%", "retention": "0.00%"},
        "measures": {
            "Control gross conversion": ('CALCULATE(MAX(group_summary[gross_conversion]), group_summary[experiment_group] = "Control")', "0.00%"),
            "Experiment gross conversion": ('CALCULATE(MAX(group_summary[gross_conversion]), group_summary[experiment_group] = "Experiment")', "0.00%"),
            "Control net conversion": ('CALCULATE(MAX(group_summary[net_conversion]), group_summary[experiment_group] = "Control")', "0.00%"),
            "Experiment net conversion": ('CALCULATE(MAX(group_summary[net_conversion]), group_summary[experiment_group] = "Experiment")', "0.00%"),
        },
    },
    "metric_results": {
        "file": "metric_results.csv",
        "columns": {"metric": "string", "control_rate": "double", "experiment_rate": "double", "difference": "double", "ci_low": "double", "ci_high": "double", "practical_threshold": "double", "role": "string", "status": "string"},
        "formats": {key: "0.00%" for key in ["control_rate", "experiment_rate", "difference", "ci_low", "ci_high", "practical_threshold"]},
        "measures": {
            "Gross conversion change": ('CALCULATE(MAX(metric_results[difference]), metric_results[metric] = "Gross conversion")', "+0.00%;-0.00%"),
            "Net conversion change": ('CALCULATE(MAX(metric_results[difference]), metric_results[metric] = "Net conversion")', "+0.00%;-0.00%"),
        },
    },
    "decision_summary": {
        "file": "decision_summary.csv",
        "columns": {"decision": "string", "primary_reason": "string", "gross_conversion_change": "double", "net_conversion_change": "double", "mature_clicks": "int64", "target_clicks": "int64", "power_coverage": "double"},
        "formats": {"gross_conversion_change": "0.00%", "net_conversion_change": "0.00%", "power_coverage": "0.0%"},
        "measures": {"Mature clicks": ("MAX(decision_summary[mature_clicks])", "#,##0"), "Required clicks": ("MAX(decision_summary[target_clicks])", "#,##0"), "Information coverage": ("MAX(decision_summary[power_coverage])", "0.0%")},
    },
    "sanity_checks": {
        "file": "sanity_checks.csv",
        "columns": {"metric": "string", "observed": "double", "ci_low": "double", "ci_high": "double", "status": "string"},
        "formats": {"observed": "0.000%", "ci_low": "0.000%", "ci_high": "0.000%"}, "measures": {},
    },
    "funnel": {
        "file": "funnel.csv",
        "columns": {"experiment_group": "string", "stage_order": "int64", "stage": "string", "users": "int64"},
        "formats": {}, "measures": {},
    },
    "daily_mature_metrics": {
        "file": "daily_mature_metrics.csv",
        "columns": {"event_date": "dateTime", "experiment_group": "string", "pageviews": "int64", "clicks": "int64", "enrollments": "int64", "payments": "int64", "click_through_rate": "double", "gross_conversion": "double", "net_conversion": "double", "retention": "double"},
        "formats": {"click_through_rate": "0.00%", "gross_conversion": "0.00%", "net_conversion": "0.00%", "retention": "0.00%"},
        "measures": {"Daily gross conversion": ("AVERAGE(daily_mature_metrics[gross_conversion])", "0.00%"), "Daily net conversion": ("AVERAGE(daily_mature_metrics[net_conversion])", "0.00%")},
    },
}


def write_text(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8", newline="\n")


def write_json(path, value):
    write_text(path, json.dumps(value, indent=2, ensure_ascii=False))


def literal(value):
    return {"expr": {"Literal": {"Value": value}}}


def position(x, y, width, height, z):
    return {"x": x, "y": y, "z": z, "height": height, "width": width, "tabOrder": z}


def field(table, name, kind="column"):
    key = "Measure" if kind == "measure" else "Column"
    return {key: {"Expression": {"SourceRef": {"Entity": table}}, "Property": name}}


def projection(table, name, kind="column", label=None):
    return {"field": field(table, name, kind), "queryRef": f"{table}.{name}", "nativeQueryRef": label or name.replace("_", " ").title()}


def style(title):
    return {
        "title": [{"properties": {"show": literal("true"), "text": literal(f"'{title}'"), "fontSize": literal("14D"), "fontColor": {"solid": {"color": literal(f"'{TEXT}'")}}}}],
        "background": [{"properties": {"show": literal("true"), "color": {"solid": {"color": literal("'#FFFFFF'")}}, "transparency": literal("0D")}}],
        "border": [{"properties": {"show": literal("true"), "color": {"solid": {"color": literal(f"'{BORDER}'")}}, "radius": literal("8D")}}],
        "visualHeader": [{"properties": {"show": literal("false")}}],
    }


def textbox(name, x, y, width, height, text, size=26, bold=True, color=INK):
    return {"$schema": SCHEMA_VISUAL, "name": name, "position": position(x, y, width, height, 100), "visual": {"visualType": "textbox", "objects": {"general": [{"properties": {"paragraphs": [{"textRuns": [{"value": text, "textStyle": {"fontFamily": "Segoe UI", "fontSize": f"{size}px", "fontWeight": "bold" if bold else "normal", "color": color}}]}]}}]}, "visualContainerObjects": {"background": [{"properties": {"show": literal("false")}}], "border": [{"properties": {"show": literal("false")}}]}}}


def card(name, x, y, width, table, measure, title, z):
    return {"$schema": SCHEMA_VISUAL, "name": name, "position": position(x, y, width, 140, z), "visual": {"visualType": "card", "query": {"queryState": {"Values": {"projections": [projection(table, measure, "measure")]}}}, "visualContainerObjects": style(title)}}


def table(name, x, y, width, height, fields, title, z):
    return {"$schema": SCHEMA_VISUAL, "name": name, "position": position(x, y, width, height, z), "visual": {"visualType": "tableEx", "query": {"queryState": {"Values": {"projections": [projection(*item) for item in fields]}}}, "objects": {"columnHeaders": [{"properties": {"autoSizeColumnWidth": literal("true"), "backColor": {"solid": {"color": literal("'#EAF2F8'")}}}}], "total": [{"properties": {"totals": literal("false")}}]}, "visualContainerObjects": style(title)}}


def line_chart(name, x, y, width, height, measure, title, z):
    return {"$schema": SCHEMA_VISUAL, "name": name, "position": position(x, y, width, height, z), "visual": {"visualType": "lineChart", "query": {"queryState": {"Category": {"projections": [projection("daily_mature_metrics", "event_date")]}, "Series": {"projections": [projection("daily_mature_metrics", "experiment_group")]}, "Y": {"projections": [projection("daily_mature_metrics", measure, "measure")]}}}, "objects": {"valueAxis": [{"properties": {"start": literal("0D"), "labelDisplayUnits": literal("1D")}}], "lineStyles": [{"properties": {"strokeWidth": literal("3D")}}]}, "visualContainerObjects": style(title)}}


def tmdl_table(name, spec):
    lines = [f"table {name}", ""]
    for measure, (expression, fmt) in spec["measures"].items():
        lines += [f"\tmeasure '{measure}' = {expression}", f"\t\tformatString: {fmt}", ""]
    for column, dtype in spec["columns"].items():
        col = f"'{column}'" if " " in column else column
        lines += [f"\tcolumn {col}", f"\t\tdataType: {dtype}"]
        if column in spec["formats"]:
            lines.append(f"\t\tformatString: {spec['formats'][column]}")
        lines += ["\t\tsummarizeBy: none", f"\t\tsourceColumn: {column}", ""]
    types = {"string": "type text", "int64": "Int64.Type", "double": "type number", "dateTime": "type date"}
    typed = ", ".join(f'{{"{c}", {types[t]}}}' for c, t in spec["columns"].items())
    lines += [f"\tpartition {name} = m", "\t\tmode: import", "\t\tsource =", "\t\t\tlet", f'\t\t\t\tSource = Csv.Document(File.Contents(#"DataFolder" & "\\{spec["file"]}"), [Delimiter=",", Columns={len(spec["columns"])}, Encoding=65001, QuoteStyle=QuoteStyle.Csv]),', "\t\t\t\tHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),", f'\t\t\t\tTyped = Table.TransformColumnTypes(Headers, {{{typed}}}, "en-US")', "\t\t\tin", "\t\t\t\tTyped", ""]
    return "\n".join(lines)


def page(name, display_name, visuals):
    page_dir = PAGES / name
    write_json(page_dir / "page.json", {"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json", "name": name, "displayName": display_name, "displayOption": "FitToPage", "height": 1080, "width": 1920, "objects": {"background": [{"properties": {"color": {"solid": {"color": literal(f"'{BACKGROUND}'")}}, "transparency": literal("0D")}}]}})
    for visual in visuals:
        write_json(page_dir / "visuals" / visual["name"] / "visual.json", visual)


def build(data_folder: str):
    if PROJECT.exists():
        shutil.rmtree(PROJECT)
    definition = MODEL / "definition"
    refs = "\n".join(f"ref table {name}" for name in TABLES)
    model = f'model Model\n\tculture: en-US\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n\tsourceQueryCulture: en-US\n\tdiscourageImplicitMeasures\n\nexpression DataFolder = "{data_folder}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n\n{refs}\n'
    write_text(definition / "model.tmdl", model)
    write_text(definition / "database.tmdl", "database UdacityABTest\n\tcompatibilityLevel: 1702\n\tcompatibilityMode: powerBI\n\tlanguage: 1033\n")
    for name, spec in TABLES.items():
        write_text(definition / "tables" / f"{name}.tmdl", tmdl_table(name, spec))
    write_json(MODEL / "definition.pbism", {"version": "4.2", "settings": {"qnaEnabled": True}})
    write_json(MODEL / "diagramLayout.json", {"version": "1.1.0", "diagrams": []})
    write_json(PROJECT / "UdacityABTest.pbip", {"version": "1.0", "artifacts": [{"report": {"path": "UdacityABTest.Report"}}], "settings": {"enableAutoRecovery": True}})
    write_json(REPORT / "definition.pbir", {"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json", "version": "4.0", "datasetReference": {"byPath": {"path": "../UdacityABTest.SemanticModel"}}})
    write_json(REPORT / "definition" / "version.json", {"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json", "version": "2.0.0"})
    write_json(REPORT / "definition" / "report.json", {"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.3.0/schema.json", "themeCollection": {"baseTheme": {"name": "CY24SU10", "reportVersionAtImport": {"visual": "2.1.0", "report": "3.0.0", "page": "2.0.0"}, "type": "SharedResources"}}, "settings": {"useEnhancedTooltips": True}})
    names = ["01decision0000000000", "02evidence0000000000", "03quality00000000000"]
    write_json(PAGES / "pages.json", {"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json", "pageOrder": names, "activePageName": names[0]})

    page(names[0], "Decision", [
        textbox("p1title", 40, 24, 1700, 60, "Should Udacity launch the free-trial readiness screener?"),
        textbox("p1decision", 40, 105, 1840, 90, "DO NOT LAUNCH YET", 32, True, ORANGE),
        card("p1gross", 40, 220, 440, "metric_results", "Gross conversion change", "Trial enrollment change", 200),
        card("p1net", 500, 220, 440, "metric_results", "Net conversion change", "Paid conversion change", 210),
        card("p1coverage", 960, 220, 440, "decision_summary", "Information coverage", "Planned sample reached", 220),
        card("p1clicks", 1420, 220, 460, "decision_summary", "Mature clicks", "Mature clicks observed", 230),
        textbox("p1why", 60, 410, 1760, 210, "The screener successfully reduces low-intent trial enrollments. However, the paid-conversion confidence interval crosses the -0.75 pp guardrail, so meaningful revenue harm cannot be ruled out.", 24, False),
        textbox("p1next", 60, 680, 1760, 210, "Next step: continue from 34,553 to 54,826 mature clicks or test a less restrictive message. Launch only when the paid-conversion guardrail passes.", 24, True, GREEN),
    ])
    page(names[1], "Metric evidence", [
        textbox("p2title", 40, 24, 1700, 60, "What changed, and is the change decision-ready?"),
        card("p2cgross", 40, 110, 440, "group_summary", "Control gross conversion", "Control gross conversion", 200),
        card("p2egross", 500, 110, 440, "group_summary", "Experiment gross conversion", "Experiment gross conversion", 210),
        card("p2cnet", 960, 110, 440, "group_summary", "Control net conversion", "Control net conversion", 220),
        card("p2enet", 1420, 110, 460, "group_summary", "Experiment net conversion", "Experiment net conversion", 230),
        table("p2table", 40, 290, 1840, 330, [("metric_results", "metric", "column"), ("metric_results", "role", "column"), ("metric_results", "control_rate", "column"), ("metric_results", "experiment_rate", "column"), ("metric_results", "difference", "column"), ("metric_results", "ci_low", "column"), ("metric_results", "ci_high", "column"), ("metric_results", "practical_threshold", "column"), ("metric_results", "status", "column")], "Metric results and launch rules", 300),
        table("p2funnel", 40, 650, 1840, 240, [("funnel", "stage_order", "column"), ("funnel", "stage", "column"), ("funnel", "experiment_group", "column"), ("funnel", "users", "column")], "Mature funnel counts", 310),
        textbox("p2note", 60, 920, 1760, 100, "Gross conversion passes the success rule. Net conversion fails the guardrail. Retention is diagnostic only because enrollment is affected by the treatment.", 18, False),
    ])
    page(names[2], "Experiment checks", [
        textbox("p3title", 40, 24, 1700, 60, "Can the experiment evidence be trusted?"),
        table("p3sanity", 40, 110, 1840, 300, [("sanity_checks", "metric", "column"), ("sanity_checks", "observed", "column"), ("sanity_checks", "ci_low", "column"), ("sanity_checks", "ci_high", "column"), ("sanity_checks", "status", "column")], "Randomization and pre-treatment checks", 200),
        line_chart("p3grossline", 40, 450, 900, 500, "Daily gross conversion", "Daily gross conversion (mature cohorts)", 300),
        line_chart("p3netline", 980, 450, 900, 500, "Daily net conversion", "Daily net conversion (mature cohorts)", 310),
        textbox("p3source", 50, 980, 1800, 60, "Source: Udacity A/B Testing course dataset | Experiment: Oct 11-Nov 16, 2014 | Mature outcomes: first 23 days | Payment lag: 14 days", 16, False, TEXT),
    ])
    print(PROJECT / "UdacityABTest.pbip")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-folder", default=r"C:\path\to\udacity-free-trial-ab-test\data\powerbi")
    args = parser.parse_args()
    build(args.data_folder)
