import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PROGRAM = os.path.join(ROOT, "feeds", "github", "board-feed-github")
FAKE_GH = os.path.join(HERE, "fake_gh.py")

SHA = "a" * 40
SUBSET_KEYWORDS = {
    "type",
    "properties",
    "required",
    "additionalProperties",
    "items",
    "minItems",
    "maxItems",
    "minLength",
    "maxLength",
    "pattern",
    "minimum",
    "maximum",
    "enum",
}
ANNOTATIONS = {"description", "default", "title", "examples"}


def stamp(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def pull_request(number, **changes):
    old = stamp(datetime.now(timezone.utc) - timedelta(days=2))
    node = {
        "url": "https://github.com/acme/app/pull/%d" % number,
        "number": number,
        "title": "Add feature %d" % number,
        "updatedAt": old,
        "isDraft": False,
        "reviewDecision": None,
        "headRefOid": SHA,
        "repository": {"nameWithOwner": "acme/app"},
        "labels": {"nodes": []},
        "commits": {"nodes": [{"commit": {"committedDate": old}}]},
        "timelineItems": {"nodes": []},
    }
    node.update(changes)
    return node


def page(*nodes):
    return {"data": {"search": {"pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": list(nodes)}}}


class ProgramTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.temp)
        self.bin = os.path.join(self.temp, "bin")
        os.mkdir(self.bin)
        self.log = os.path.join(self.temp, "gh.log")
        self.pages = os.path.join(self.temp, "pages.json")

    def install_gh(self):
        target = os.path.join(self.bin, "gh")
        shutil.copy(FAKE_GH, target)
        os.chmod(target, 0o755)

    def serve(self, *pages):
        with open(self.pages, "w") as handle:
            json.dump(list(pages), handle)

    def run_program(self, *args, stdin="", **env):
        environment = dict(os.environ)
        environment.pop("FAKE_GH_AUTH", None)
        environment.pop("FAKE_GH_FAIL", None)
        environment.update(
            PATH=self.bin + os.pathsep + environment.get("PATH", ""),
            FAKE_GH_LOG=self.log,
            FAKE_GH_PAGES=self.pages,
        )
        environment.update(env)
        return subprocess.run(
            [sys.executable, PROGRAM] + list(args),
            input=stdin,
            capture_output=True,
            text=True,
            timeout=30,
            env=environment,
        )

    def gh_calls(self):
        if not os.path.exists(self.log):
            return []
        with open(self.log) as handle:
            return [json.loads(line) for line in handle]

    def list_items(self, options=None, **env):
        options = {"query": "is:open review-requested:@me"} if options is None else options
        result = self.run_program("list-pull-requests", stdin=json.dumps(options), **env)
        self.assertEqual(result.returncode, 0, result.stderr)
        return [json.loads(line) for line in result.stdout.splitlines()]


class DescribeTest(ProgramTest):
    def schema_keywords(self, schema, found):
        found.update(schema)
        for child in schema.get("properties", {}).values():
            self.schema_keywords(child, found)
        if isinstance(schema.get("items"), dict):
            self.schema_keywords(schema["items"], found)
        return found

    def test_describe_is_protocol_one_and_declares_the_action(self):
        result = self.run_program("describe")
        self.assertEqual(result.returncode, 0, result.stderr)
        document = json.loads(result.stdout)
        self.assertEqual(document["protocol"], 1)
        action = document["actions"]["list-pull-requests"]
        self.assertEqual(action["fields"], ["url", "title", "updatedAt", "status", "labels"])
        self.assertEqual(action["options"]["required"], ["query"])

    def test_the_options_schema_uses_only_the_keywords_the_board_reads(self):
        document = json.loads(self.run_program("describe").stdout)
        schema = document["actions"]["list-pull-requests"]["options"]
        used = self.schema_keywords(schema, set())
        self.assertEqual(used - SUBSET_KEYWORDS - ANNOTATIONS, set())


class DoctorTest(ProgramTest):
    def test_gh_missing_fails_as_not_installed(self):
        result = self.run_program("doctor", PATH=self.bin)
        self.assertEqual(result.returncode, 1)
        self.assertIn("not installed", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_gh_not_logged_in_fails(self):
        self.install_gh()
        result = self.run_program("doctor", FAKE_GH_AUTH="fail")
        self.assertEqual(result.returncode, 1)
        self.assertIn("not logged in", result.stderr)

    def test_gh_logged_in_passes(self):
        self.install_gh()
        result = self.run_program("doctor")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "gh found and logged in")


class VerbTest(ProgramTest):
    def test_unknown_verb_or_action_exits_two_with_usage(self):
        for args in (["nope"], ["check", "nope"], ["check"], [], ["describe", "extra"]):
            with self.subTest(args=args):
                result = self.run_program(*args)
                self.assertEqual(result.returncode, 2)
                self.assertIn("usage:", result.stderr)


class CheckTest(ProgramTest):
    def test_invalid_options_fail(self):
        table = {
            "bad repository name": {"query": "x", "repositories": ["not a repo"]},
            "repository without owner": {"query": "x", "repositories": ["app"]},
            "empty repositories": {"query": "x", "repositories": []},
            "empty query": {"query": ""},
            "blank query": {"query": "   "},
            "query with a newline": {"query": "a\nb"},
            "query too long": {"query": "x" * 257},
            "missing query": {"repositories": ["acme/app"]},
            "unknown option": {"query": "x", "colour": "red"},
            "settle above the limit": {"query": "x", "settleMinutes": 121},
            "settle below zero": {"query": "x", "settleMinutes": -1},
            "settle is a boolean": {"query": "x", "settleMinutes": True},
            "not an object": ["x"],
        }
        for name, options in table.items():
            with self.subTest(name):
                result = self.run_program("check", "list-pull-requests", stdin=json.dumps(options))
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertNotEqual(result.stderr.strip(), "")

    def test_the_action_rechecks_its_options_before_calling_gh(self):
        self.install_gh()
        result = self.run_program("list-pull-requests", stdin=json.dumps({"query": ""}))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(self.gh_calls(), [])

    def test_invalid_json_fails(self):
        result = self.run_program("check", "list-pull-requests", stdin="{")
        self.assertEqual(result.returncode, 1)

    def test_valid_options_pass_without_calling_gh(self):
        self.install_gh()
        options = {"query": "is:open", "repositories": ["acme/app", "a.b/c_d-e"], "settleMinutes": 0}
        result = self.run_program("check", "list-pull-requests", stdin=json.dumps(options))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.gh_calls(), [])


class ListPullRequestsTest(ProgramTest):
    def setUp(self):
        super().setUp()
        self.install_gh()

    def test_an_item_carries_key_title_repo_and_the_declared_fields(self):
        self.serve(page(pull_request(7, labels={"nodes": [{"name": "bug"}, {"name": "ui"}]})))
        [item] = self.list_items()
        self.assertEqual(item["key"], "https://github.com/acme/app/pull/7")
        self.assertEqual(item["title"], "acme/app#7 Add feature 7")
        self.assertEqual(item["repo"], "acme/app")
        self.assertEqual(item["version"], SHA)
        self.assertEqual(
            sorted(item["fields"]), ["labels", "status", "title", "updatedAt", "url"]
        )
        self.assertEqual(item["fields"]["url"], item["key"])
        self.assertEqual(item["fields"]["title"], "Add feature 7")
        self.assertEqual(item["fields"]["labels"], "bug, ui")
        self.assertNotIn("notBefore", item)

    def test_control_characters_and_backslashes_in_text_become_single_spaces(self):
        dirty = "Fix\tthe\nbug\x1b[0m \\ now ok"
        self.serve(page(pull_request(1, title=dirty, labels={"nodes": [{"name": "a\nb"}]})))
        [item] = self.list_items()
        self.assertEqual(item["fields"]["title"], "Fix the bug [0m now ok")
        self.assertEqual(item["title"], "acme/app#1 Fix the bug [0m now ok")
        self.assertEqual(item["fields"]["labels"], "a b")

    def test_a_review_request_is_part_of_the_version(self):
        requested = "2026-11-20T09:30:00Z"
        self.serve(
            page(
                pull_request(1),
                pull_request(2, timelineItems={"nodes": [{"createdAt": requested}]}),
            )
        )
        first, second = self.list_items()
        self.assertEqual(first["version"], SHA)
        self.assertEqual(second["version"], SHA + "@" + requested)

    def test_not_before_only_for_a_head_younger_than_the_settle_time(self):
        young = stamp(datetime.now(timezone.utc) - timedelta(minutes=2))
        self.serve(
            page(
                pull_request(1, commits={"nodes": [{"commit": {"committedDate": young}}]}),
                pull_request(2),
            )
        )
        fresh, old = self.list_items()
        waits_until = datetime.strptime(fresh["notBefore"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        expected = datetime.strptime(young, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) + timedelta(minutes=10)
        self.assertEqual(waits_until, expected)
        self.assertNotIn("notBefore", old)

    def test_a_settle_window_shorter_than_the_head_age_never_waits(self):
        young = stamp(datetime.now(timezone.utc) - timedelta(minutes=2))
        commits = {"nodes": [{"commit": {"committedDate": young}}]}
        self.serve(page(pull_request(1, commits=commits)))
        [immediate] = self.list_items({"query": "x", "settleMinutes": 0})
        self.assertNotIn("notBefore", immediate)
        [short] = self.list_items({"query": "x", "settleMinutes": 1})
        self.assertNotIn("notBefore", short)

    def test_status_follows_draft_then_review_decision(self):
        self.serve(
            page(
                pull_request(1, isDraft=True, reviewDecision="APPROVED"),
                pull_request(2, reviewDecision="CHANGES_REQUESTED"),
                pull_request(3, reviewDecision="APPROVED"),
                pull_request(4, reviewDecision="REVIEW_REQUIRED"),
                pull_request(5),
            )
        )
        statuses = [item["fields"]["status"] for item in self.list_items()]
        self.assertEqual(statuses, ["draft", "changes-requested", "approved", "open", "open"])

    def test_items_that_are_not_pull_requests_are_skipped(self):
        self.serve(
            page(
                {},
                {"url": "https://github.com/acme/app/issues/3", "title": "An issue"},
                {"url": "https://example.com/acme/app/pull/4", "title": "Elsewhere"},
                pull_request(5),
            )
        )
        keys = [item["key"] for item in self.list_items()]
        self.assertEqual(keys, ["https://github.com/acme/app/pull/5"])

    def test_every_page_of_the_answer_is_listed_and_a_repeat_is_dropped(self):
        self.serve(page(pull_request(1), pull_request(2)), page(pull_request(2), pull_request(3)))
        keys = [item["key"].rsplit("/", 1)[1] for item in self.list_items()]
        self.assertEqual(keys, ["1", "2", "3"])

    def test_no_pull_requests_print_nothing_and_succeed(self):
        self.serve(page())
        result = self.run_program("list-pull-requests", stdin=json.dumps({"query": "x"}))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_the_search_adds_is_pr_and_the_repositories_and_passes_them_as_arguments(self):
        self.serve(page())
        self.list_items({"query": "is:open review-requested:@me", "repositories": ["acme/app", "acme/infra"]})
        [call] = self.gh_calls()
        self.assertEqual(call[:3], ["api", "graphql", "--paginate"])
        self.assertIn("q=is:open review-requested:@me is:pr repo:acme/app repo:acme/infra", call)
        self.assertTrue(any(argument.startswith("query=query(") for argument in call))

    def test_is_pr_is_not_added_twice(self):
        self.serve(page())
        self.list_items({"query": "IS:PR review-requested:@me"})
        [call] = self.gh_calls()
        self.assertIn("q=IS:PR review-requested:@me", call)

    def test_a_failing_gh_exits_one_with_its_reason_and_nothing_on_stdout(self):
        self.serve(page(pull_request(1)))
        result = self.run_program(
            "list-pull-requests",
            stdin=json.dumps({"query": "x"}),
            FAKE_GH_FAIL="HTTP 401: Bad credentials\nsecond line",
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr.strip(), "HTTP 401: Bad credentials")

    def test_a_graphql_error_or_unreadable_answer_exits_one_with_nothing_on_stdout(self):
        answers = {
            "graphql errors": [{"data": None, "errors": [{"message": "boom"}]}],
            "no search": [{"data": {}}],
        }
        for name, pages in answers.items():
            with self.subTest(name):
                self.serve(*pages)
                result = self.run_program("list-pull-requests", stdin=json.dumps({"query": "x"}))
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
