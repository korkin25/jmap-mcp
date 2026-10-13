#!/usr/bin/env python3
"""Verify fork admission settings and optionally activate GitHub Actions."""
import argparse
import json
from pathlib import Path
import subprocess


def api(path, *, body=None):
    command = ["gh", "api", path]
    if body is not None:
        command += ["--method", "PUT", "--input", "-"]
    result = subprocess.run(command, input=json.dumps(body) if body is not None else None,
                            text=True, capture_output=True, check=True)
    return json.loads(result.stdout) if result.stdout.strip() else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--activate", action="store_true", help="Activate workflows after owner gates pass")
    args = parser.parse_args()
    policy = json.loads((Path(__file__).resolve().parents[1] / ".github/repository-policy.json").read_text())
    repo = "repos/" + policy["repository"]
    if api("user")["login"] != policy["only_write_collaborator"]:
        raise SystemExit("Use the repository owner's GitHub credentials")
    approval = api(repo + "/actions/permissions/fork-pr-contributor-approval")
    if approval["approval_policy"] != policy["approval_policy"]:
        raise SystemExit("Owner must configure all_external_contributors before activation")
    writers = []
    page = 1
    while True:
        users = api(repo + f"/collaborators?per_page=100&page={page}")
        writers.extend(u["login"] for u in users if u["permissions"].get("push")
                       or u["permissions"].get("admin") or u["permissions"].get("maintain"))
        if len(users) < 100:
            break
        page += 1
    if sorted(writers) != [policy["only_write_collaborator"]]:
        raise SystemExit("Owner must review write/admin collaborators before activation")
    permissions = api(repo + "/actions/permissions/workflow")
    for key in ("default_workflow_permissions", "can_approve_pull_request_reviews"):
        if permissions[key] != policy[key]:
            raise SystemExit(f"Owner must review workflow permission: {key}")
    if args.activate:
        # A new fork can report enabled=true while no workflows are registered.
        # Reapplying this declarative setting initializes the inherited workflows.
        api(repo + "/actions/permissions", body=policy["actions"])
    actual = api(repo + "/actions/permissions")
    if any(actual[key] != value for key, value in policy["actions"].items()):
        raise SystemExit("Actions settings differ from repository-policy.json")
    workflows = api(repo + "/actions/workflows")["workflows"]
    active = {w["path"] for w in workflows if w["state"] == "active"}
    required = {".github/workflows/ci.yml", ".github/workflows/release.yml"}
    if not required <= active:
        raise SystemExit("Workflows not active; use --activate after verifying owner gates")
    print("Owner, approval, token permissions and active CI/release workflows verified")


if __name__ == "__main__":
    main()
