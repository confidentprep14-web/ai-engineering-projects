"""Console table printing and JSON report writing."""
import json


def print_results_table(results: list, dimensions: list) -> None:
    """Print a table: rows = test cases, columns = dimensions + overall PASS."""
    dim_names = [d["name"] for d in dimensions]
    headers = ["Test Case"] + dim_names + ["PASS"]

    col_width = {h: len(h) for h in headers}
    rows = []
    for r in results:
        row = [r["id"]]
        for name in dim_names:
            score_info = r["scores"].get(name)
            if score_info is None:
                cell = "-"
            else:
                mark = "✓" if score_info["passed"] else "✗"
                cell = f"{score_info['score']}/5 {mark}"
            row.append(cell)
        row.append("✓" if r["passed"] else "✗")
        rows.append(row)
        for h, cell in zip(headers, row):
            col_width[h] = max(col_width[h], len(cell))

    header_line = "  ".join(h.ljust(col_width[h]) for h in headers)
    print(header_line)
    print("─" * len(header_line))
    for row in rows:
        print("  ".join(cell.ljust(col_width[h]) for h, cell in zip(headers, row)))


def save_json_report(suite_result: dict, output_path: str) -> None:
    """Write the suite result as indented JSON. Warns (does not raise) on
    write failure, so a bad --output path doesn't abort an otherwise-good run.
    """
    try:
        with open(output_path, "w") as f:
            json.dump(suite_result, f, indent=2)
    except OSError as exc:
        print(f"Warning: could not write report to '{output_path}': {exc}")


def print_diff_table(prompt_a_results: dict, prompt_b_results: dict) -> None:
    """Side-by-side comparison: test case | prompt A | prompt B | winner."""
    headers = ["Test Case", "Prompt A", "Prompt B", "Winner"]
    rows = []

    a_by_id = {r["id"]: r for r in prompt_a_results["results"]}
    b_by_id = {r["id"]: r for r in prompt_b_results["results"]}

    for tc_id in a_by_id:
        a = a_by_id[tc_id]
        b = b_by_id.get(tc_id, {})
        a_mark = "✓" if a["passed"] else "✗"
        b_mark = "✓" if b.get("passed") else "✗"

        a_total = sum(s["score"] for s in a["scores"].values())
        b_total = sum(s["score"] for s in b.get("scores", {}).values())
        if a_total > b_total:
            winner = "A"
        elif b_total > a_total:
            winner = "B"
        else:
            winner = "tie"

        rows.append([tc_id, f"{a_mark} ({a_total})", f"{b_mark} ({b_total})", winner])

    col_width = {h: len(h) for h in headers}
    for row in rows:
        for h, cell in zip(headers, row):
            col_width[h] = max(col_width[h], len(cell))

    header_line = "  ".join(h.ljust(col_width[h]) for h in headers)
    print(header_line)
    print("─" * len(header_line))
    for row in rows:
        print("  ".join(cell.ljust(col_width[h]) for h, cell in zip(headers, row)))
