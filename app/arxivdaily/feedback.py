"""Daily GitHub checkbox issues and explicit feedback counts; no ranking changes."""
from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
import os
import re

import httpx

from .models import ProcessingError, fingerprint, iso, parse_time
from .render import markdown_text


class FeedbackError(ProcessingError):
    pass


class GitHubFeedbackClient:
    def __init__(self, settings, client=None):
        self.repository = settings["repository"] or os.environ.get("GITHUB_REPOSITORY", "")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", self.repository):
            raise FeedbackError("feedback_repository_missing")
        self.token = os.environ.get(settings["token_env"], "")
        self.delete_token_env = settings["delete_token_env"]
        self.delete_token = os.environ.get(self.delete_token_env, "")
        if not self.token:
            raise FeedbackError("feedback_token_missing")
        self.client = client or httpx.Client(timeout=30, follow_redirects=False)

    def _request(self, method, path, *, delete=False, missing_ok=False, **kwargs):
        token = self.delete_token if delete else self.token
        if not token:
            raise FeedbackError(f"feedback_delete_token_missing: configure {self.delete_token_env} to delete saved issues")
        try:
            response = self.client.request(method, "https://api.github.com" + path,
                headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json"}, **kwargs)
        except httpx.HTTPError:
            raise FeedbackError("feedback_github_transport_failed") from None
        if missing_ok and response.status_code in (404, 410):
            return None
        if not response.is_success:
            raise FeedbackError(f"feedback_github_http_{response.status_code}")
        try:
            data = response.json()
        except ValueError:
            raise FeedbackError("feedback_github_invalid_json") from None
        if isinstance(data, dict) and data.get("errors"):
            raise FeedbackError("feedback_github_graphql_failed: check issue deletion permission")
        return data

    def find(self, marker):
        page = 1
        while True:
            rows = self._request("GET", f"/repos/{self.repository}/issues", params={
                "state": "all", "per_page": 100, "page": page, "sort": "created", "direction": "desc"})
            for row in rows:
                if ("pull_request" not in row and marker in (row.get("body") or "")
                        and row.get("user", {}).get("login", "").casefold() in {
                            "github-actions[bot]", self.repository.split("/")[0].casefold()}):
                    return row
            if len(rows) < 100:
                return None
            page += 1

    def get(self, number):
        return self._request("GET", f"/repos/{self.repository}/issues/{number}", missing_ok=True)

    def create(self, title, body):
        return self._request("POST", f"/repos/{self.repository}/issues", json={"title": title, "body": body})

    def update(self, number, body):
        return self._request("PATCH", f"/repos/{self.repository}/issues/{number}", json={"body": body})

    def close(self, number):
        return self._request("PATCH", f"/repos/{self.repository}/issues/{number}", json={"state": "closed"})

    def delete(self, node_id):
        self._request("POST", "/graphql", delete=True, json={
            "query": "mutation($id: ID!) { deleteIssue(input: {issueId: $id}) { clientMutationId } }",
            "variables": {"id": node_id}})


def issue_marker(day):
    return f"<!-- arxivdaily-feedback:{day} -->"


def paper_block(key, row):
    return "\n\n".join([
        f"<!-- arxivdaily-paper:{key} -->",
        "### " + markdown_text(row["title_zh"]), markdown_text(row["title"]),
        f"[arXiv {key}]({row['url']})",
        f"- [ ] 👍 对我有用 <!-- vote:{key}:like -->\n- [ ] 👎 对我无用 <!-- vote:{key}:dislike -->",
    ])


def parse_votes(body, keys):
    """Only the known paper's two marked checkbox lines are ballots."""
    result = {}
    for key in keys:
        checks = {}
        for vote in ("like", "dislike"):
            matches = re.findall(r"^\s*- \[([ xX])\] [^\r\n]*<!-- vote:" + re.escape(key) + ":" + vote + r" -->\s*$", body, re.MULTILINE)
            checks[vote] = matches
        if any(len(values) != 1 for values in checks.values()):
            result[key] = "invalid"
        else:
            selected = [vote for vote, values in checks.items() if values[0].lower() == "x"]
            result[key] = selected[0] if len(selected) == 1 else "conflict" if selected else "pending"
    return result


def tally_feedback(feedback):
    """Rebuild from paper ballots, so retries, changed votes and resends cannot add votes."""
    ballots = {}
    for day, issue in sorted(feedback["issues"].items()):
        for key, row in issue["papers"].items():
            # A later unreviewed resend does not erase an earlier explicit vote.
            if row["vote"] != "pending" or key not in ballots:
                ballots[key] = row
    combinations, keywords = {}, {}
    for row in ballots.values():
        vote = row["vote"]
        if vote not in ("like", "dislike"):
            continue
        trace = row["rule_trace"]
        seen_combinations, seen_keywords = set(), set()
        for clause in trace.get("clauses", []):
            context = {"rules_fingerprint": trace["rules_fingerprint"], "source": trace["source"],
                       "route": clause["route"], "groups": sorted(clause["groups"])}
            combo_key = fingerprint(context)
            if combo_key not in seen_combinations:
                combinations.setdefault(combo_key, {**context, "like": 0, "dislike": 0})[vote] += 1
                seen_combinations.add(combo_key)
            for group, hits in clause["keywords"].items():
                for hit in hits:
                    unit = {**context, "group": group, "keyword": hit["keyword"]}
                    keyword_key = fingerprint(unit)
                    if keyword_key not in seen_keywords:
                        keywords.setdefault(keyword_key, {**unit, "like": 0, "dislike": 0})[vote] += 1
                        seen_keywords.add(keyword_key)
    return {"combinations": list(combinations.values()), "keywords": list(keywords.values()),
            "rated_papers": sum(row["vote"] in ("like", "dislike") for row in ballots.values())}


def render_feedback_summary(feedback):
    counts = feedback["counts"]
    lines = ["# 论文反馈计数", "", f"已评价论文：{counts['rated_papers']} 篇（按基础 arXiv ID 去重）。",
             "", "仅记录显式赞踩，不评分、不调整筛选。每个命中组合及其具体词分别计数，跨行不可相加当作论文总数。",
             "旧记录补算与实际历史命中分开统计；不同规则版本分开统计。", "", "## 组合", "",
             "| 规则版本 / 来源 | 路线 | AND 组合 | 👍 | 👎 |", "| --- | --- | --- | ---: | ---: |"]
    for row in counts["combinations"]:
        lines.append(f"| {row['rules_fingerprint'][:12]} / {row['source']} | {markdown_text(row['route'])} | {markdown_text(' + '.join(row['groups']))} | {row['like']} | {row['dislike']} |")
    lines += ["", "## 具体关键词（保留组合上下文）", "", "| 规则版本 / 来源 | 路线 / AND 组合 | 组 | 词或短语 | 👍 | 👎 |",
              "| --- | --- | --- | --- | ---: | ---: |"]
    for row in counts["keywords"]:
        lines.append(f"| {row['rules_fingerprint'][:12]} / {row['source']} | {markdown_text(row['route'] + ' / ' + ' + '.join(row['groups']))} | {markdown_text(row['group'])} | {markdown_text(row['keyword'])} | {row['like']} | {row['dislike']} |")
    return "\n".join(lines) + "\n"


class Feedback:
    def __init__(self, settings, client):
        self.settings, self.client = settings, client

    def _state(self, state):
        feedback = state.setdefault("feedback", {"repository": self.client.repository, "issues": {}})
        if feedback["repository"] != self.client.repository:
            raise FeedbackError("feedback_repository_changed: retain the original repository for existing issues")
        return feedback

    @staticmethod
    def _save(feedback, checkpoint):
        feedback["counts"] = tally_feedback(feedback)
        checkpoint()

    def ensure_daily(self, state, day, items, now, checkpoint):
        feedback = self._state(state)
        entry = feedback["issues"].setdefault(day, {"created_at": iso(now), "papers": {}, "status": "open"})
        if entry["status"] in {"closed", "deleted"}:
            raise FeedbackError("feedback_day_already_finalized")
        for item in items:
            if item.translation is None:
                raise FeedbackError("feedback_chinese_title_missing")
            entry["papers"].setdefault(item.paper.base_id, {
                "title": item.paper.title, "title_zh": item.translation.title_zh,
                "url": item.paper.url, "rule_trace": deepcopy(item.rule_trace), "vote": "pending"})
        # Persist intended membership before creating/updating the remote issue.
        self._save(feedback, checkpoint)
        self._ensure_issue(entry, day)
        self._save(feedback, checkpoint)
        return entry["url"]

    def _ensure_issue(self, entry, day):
        marker = issue_marker(day)
        remote = self.client.get(entry["number"]) if entry.get("number") else self.client.find(marker)
        if entry.get("number") and remote is None:
            raise FeedbackError("feedback_issue_missing")
        if remote is None:
            body = marker + f"\n\n# 论文反馈 · {day}\n\n每篇勾选一个选项，勾选后自动保存；未评价可留空，两项都选不计数。下次日报运行收集。\n"
        else:
            body = remote.get("body") or ""
            if marker not in body:
                raise FeedbackError("feedback_issue_marker_missing")
        for key, row in entry["papers"].items():
            if f"<!-- arxivdaily-paper:{key} -->" not in body:
                body += "\n\n" + paper_block(key, row)
        if remote is None:
            remote = self.client.create(f"[论文反馈] {day}", body)
        elif body != remote.get("body"):
            remote = self.client.update(remote["number"], body)
        entry.update(number=remote["number"], node_id=remote["node_id"],
                     url=f"https://github.com/{self.client.repository}/issues/{remote['number']}")
        return remote

    def sync(self, state, now, day, checkpoint):
        feedback = self._state(state)
        errors = []
        for issue_day, entry in feedback["issues"].items():
            if entry["status"] in {"closed", "deleted"}:
                continue
            try:
                remote = self.client.get(entry["number"]) if entry.get("number") else self.client.find(issue_marker(issue_day))
                if remote is None:
                    if entry.get("cleanup_pending") and entry.get("cleanup_action", "delete") == "delete":
                        entry["status"] = "deleted"
                        self._save(feedback, checkpoint)
                        continue
                    if not entry.get("number"):
                        if not entry["papers"]:
                            continue
                        # Retry a failed creation from the durable paper/title/trace snapshot.
                        remote = self._ensure_issue(entry, issue_day)
                        self._save(feedback, checkpoint)
                    else:
                        raise FeedbackError("feedback_issue_missing")
                if issue_marker(issue_day) not in (remote.get("body") or ""):
                    raise FeedbackError("feedback_issue_marker_missing")
                if any(f"<!-- arxivdaily-paper:{key} -->" not in (remote.get("body") or "") for key in entry["papers"]):
                    # An interrupted same-day append may have saved membership only.
                    remote = self._ensure_issue(entry, issue_day)
                    self._save(feedback, checkpoint)
                entry.update(number=remote["number"], node_id=remote["node_id"],
                             url=f"https://github.com/{self.client.repository}/issues/{remote['number']}")
                votes = parse_votes(remote.get("body") or "", entry["papers"])
                for key, vote in votes.items():
                    entry["papers"][key]["vote"] = vote
                entry["last_read_at"] = iso(now)
                complete = bool(votes) and all(v in ("like", "dislike") for v in votes.values())
                expired = now >= parse_time(entry["created_at"]) + timedelta(days=self.settings["max_wait_days"])
                # Today's issue can still receive another batch; close the day first.
                cleanup = issue_day < day and (complete or expired)
                if cleanup:
                    entry["cleanup_pending"] = "complete" if complete else "expired"
                    entry["cleanup_action"] = self.settings["cleanup_action"]
                else:
                    entry.pop("cleanup_pending", None)
                    entry.pop("cleanup_action", None)
                self._save(feedback, checkpoint)  # Publish even partial feedback, before any cleanup.
                if cleanup:
                    # Do not finalize votes edited while the checkpoint was publishing.
                    latest = self.client.get(entry["number"])
                    if latest is not None and latest.get("body") != remote.get("body"):
                        continue
                    if entry["cleanup_action"] == "close":
                        if latest is None:
                            raise FeedbackError("feedback_issue_missing")
                        if latest.get("state") != "closed":
                            self.client.close(entry["number"])
                        entry["status"] = "closed"
                        entry["closed_at"] = iso(now)
                    else:
                        if latest is not None:
                            self.client.delete(entry["node_id"])
                        entry["status"] = "deleted"
                        entry["deleted_at"] = iso(now)
                    self._save(feedback, checkpoint)
            except FeedbackError as exc:
                errors.append(f"feedback:{issue_day}:{exc}")
        self._save(feedback, checkpoint)
        return errors
