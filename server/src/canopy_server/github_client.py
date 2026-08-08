"""The v1 GitHub executor — a thin typed client over the REST API (builder-connectors.md §6).

``kind: "native"``: the control plane speaks to api.github.com directly via httpx; no external
MCP server binary, no SDK. The constructor takes an httpx transport so tests (and CI) run the
entire connector path against an in-memory double with zero network and zero credentials — the
mock-provider doctrine (risk IM-2) applied to connectors.

Tokens are **call-scoped**: resolved from the Secret Store by the caller, passed per call,
never stored on the client, never written anywhere.
"""

from __future__ import annotations

from typing import Any

import httpx

_API = "https://api.github.com"


class GitHubError(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        super().__init__(f"github: {status} {message}")


class GitHubClient:
    def __init__(self, transport: httpx.BaseTransport | None = None, base_url: str = _API):
        self._client = httpx.Client(
            base_url=base_url, transport=transport, timeout=20.0,
            headers={"Accept": "application/vnd.github+json",
                     "X-GitHub-Api-Version": "2022-11-28"},
        )

    def _req(self, method: str, path: str, token: str, **kw) -> Any:
        r = self._client.request(
            method, path, headers={"Authorization": f"Bearer {token}"}, **kw
        )
        if r.status_code >= 400:
            detail = ""
            try:
                detail = r.json().get("message", "")
            except Exception:  # noqa: BLE001 - error bodies are best-effort
                detail = r.text[:200]
            raise GitHubError(r.status_code, detail)
        return r.json() if r.content else None

    # ------------------------------------------------------------------ reads
    def get_repo(self, token: str, owner: str, repo: str) -> dict:
        return self._req("GET", f"/repos/{owner}/{repo}", token)

    def list_issues(
        self, token: str, owner: str, repo: str, *,
        state: str = "open", labels: list[str] | None = None, since: str | None = None,
        per_page: int = 50,
    ) -> list[dict]:
        params: dict[str, Any] = {"state": state, "per_page": per_page,
                                  "sort": "updated", "direction": "asc"}
        if labels:
            params["labels"] = ",".join(labels)
        if since:
            params["since"] = since
        issues = self._req("GET", f"/repos/{owner}/{repo}/issues", token, params=params)
        # The issues endpoint interleaves PRs; a trigger fires on issues only.
        return [i for i in issues if "pull_request" not in i]

    def get_issue(self, token: str, owner: str, repo: str, number: int) -> dict:
        return self._req("GET", f"/repos/{owner}/{repo}/issues/{number}", token)

    # ----------------------------------------------------------------- writes
    def create_pr(
        self, token: str, owner: str, repo: str, *,
        title: str, body: str, head: str, base: str,
    ) -> dict:
        return self._req(
            "POST", f"/repos/{owner}/{repo}/pulls", token,
            json={"title": title, "body": body, "head": head, "base": base},
        )


def issue_template_vars(issue: dict) -> dict[str, str]:
    """The template vocabulary (standing-orgs.md §3): straight substitution, no expressions."""
    return {
        "title": issue.get("title", ""),
        "number": str(issue.get("number", "")),
        "url": issue.get("html_url", ""),
        "body": issue.get("body") or "",
        "labels": ", ".join(lbl.get("name", "") for lbl in issue.get("labels", [])),
        "author": (issue.get("user") or {}).get("login", ""),
    }


def render_template(template: str, variables: dict[str, str]) -> str:
    out = template
    for k, v in variables.items():
        out = out.replace("{{" + k + "}}", v)
    return out


TEMPLATE_VARS = ("title", "number", "url", "body", "labels", "author")
