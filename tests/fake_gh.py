#!/usr/bin/env python3
import json
import os
import sys

arguments = sys.argv[1:]

log = os.environ.get("FAKE_GH_LOG")
if log:
    with open(log, "a") as handle:
        handle.write(json.dumps(arguments) + "\n")

if arguments[:2] == ["auth", "status"]:
    if os.environ.get("FAKE_GH_AUTH") == "fail":
        sys.stderr.write("You are not logged into any GitHub hosts.\n")
        sys.exit(1)
    print("Logged in to github.com")
    sys.exit(0)

if arguments[:2] == ["api", "graphql"]:
    failure = os.environ.get("FAKE_GH_FAIL")
    if failure:
        sys.stderr.write(failure + "\n")
        sys.exit(1)
    with open(os.environ["FAKE_GH_PAGES"]) as handle:
        pages = json.load(handle)
    for page in pages:
        sys.stdout.write(json.dumps(page))
    sys.exit(0)

sys.stderr.write("fake gh: unexpected arguments %s\n" % arguments)
sys.exit(64)
