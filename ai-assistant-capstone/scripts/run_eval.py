"""Run the eval suite against a live or local assistant endpoint."""
import argparse, requests, yaml, json, sys

parser = argparse.ArgumentParser()
parser.add_argument("--base-url", default="http://localhost:8000")
parser.add_argument("--suite", default="eval/suite.yaml")
args = parser.parse_args()

with open(args.suite) as f:
    suite = yaml.safe_load(f)

print(f"Running {suite['suite_name']} against {args.base_url}")
print(f"{len(suite['test_cases'])} test cases\n")

# Upload a sample document first (for RAG test cases)
with open("sample_docs/test.txt", "rb") as f:
    resp = requests.post(f"{args.base_url}/documents", files={"file": f})
    print(f"Uploaded sample doc: {resp.json()}")

# Run each test case by posting to /eval
resp = requests.post(f"{args.base_url}/eval", json={"suite_yaml": yaml.dump(suite)})
result = resp.json()

print(f"\nResults:")
for r in result["results"]:
    status = "✓" if r["passed"] else "✗"
    print(f"  {status} {r['id']}: {r.get('summary', '')}")

summary = result["summary"]
print(f"\nSummary: {summary['passed']}/{summary['total']} passed")
print(f"Retrieval hit rate: {summary.get('retrieval_hit_rate', 'N/A')}")

sys.exit(0 if summary["passed"] == summary["total"] else 1)
