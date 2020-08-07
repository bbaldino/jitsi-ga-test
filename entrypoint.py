#!/usr/bin/env python3

import json
import os
import sys

def error(msg: str) -> None:
    print(f"[error]: {msg}")

def info(msg: str) -> None:
    print(f"[info]: {msg}")

if __name__ == "__main__":
    GITHUB_EVENT_PATH = os.environ["GITHUB_EVENT_PATH"]

    with open(GITHUB_EVENT_PATH) as event_info_file:
        event = json.load(event_info_file)

    info("loaded event info: %s" % event)
    pr_comment = event.get("issue", {}).get("pull_request", None)
    if pr_comment == None:
        info("Event is not a PR comment")
        # TODO: this should just be a 'quit', not a fail or success.  Is this right?
        sys.exit(0)

    comment_body = event.get("comment").get("body")
    info(f"Parsed comment body {comment_body}")

