#!/usr/bin/env python3

import json
import os
import sys

if __name__ == "__main__":
    GITHUB_EVENT_PATH = os.environ["GITHUB_EVENT_PATH"]

    with open(GITHUB_EVENT_PATH) as event_info_file:
        event = json.load(event_info_file)

    print("loaded event info: %s" % event)
