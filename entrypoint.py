#!/usr/bin/env python3

import json
import os
import subprocess
import sys

from contextlib import redirect_stdout
import git
import requests

def error(msg: str) -> None:
    print(f"[error]: {msg}", flush=True)

def info(msg: str) -> None:
    print(f"[info]: {msg}", flush=True)

def fail(msg: str) -> None:
    error(msg)
    sys.exit(1)

def checkout_component(component_name, repo, branch_name, checkout_dir):
    info(f"Checking out branch '{branch_name}' from repo '{repo}' for component '{component_name}'")
    git.Repo.clone_from(f"https://github.com/{repo}.git", os.path.join(checkout_dir, component_name), branch=branch_name, depth=1)

def checkout_overridden_components(overridden_components):
    for (component, (repo, branch)) in overridden_components.items():
        checkout_component(component, repo, branch, ".")

def update_maven_deps(overridden_versions, component_dir: str) -> None:
    for (component_name, component_version) in overridden_versions.items():
        info(f"Setting {component_name} version in {component_dir} to {component_version}")
        cmd = [
            "xmlstarlet", "ed", "--inplace",
            "-u", f"/_:project/_:dependencies/_:dependency[_:artifactId='{component_name}']/_:version", "-v", f"{component_version}",
            "-u", f"/_:project/_:dependencyManagement/_:dependencies/_:dependency[_:artifactId='{component_name}']/_:version", "-v", f"{component_version}",
            os.path.join(component_dir, "pom.xml")
        ]
        info(f"Running command: {cmd}")
        result = subprocess.run(cmd, stdout=sys.stdout)
        info(f"Substitution command ran with result {result.returncode}")
        info(f"Running git diff in {component_dir} to see changes")
        info(subprocess.check_output(["git", "diff", "-w"], cwd=component_dir).decode(sys.stdout.encoding))

def get_component_version(component_dir: str) -> str:
    cmd = ["xmlstarlet", "sel", "-t", "-v", "/_:project/_:version", os.path.join(component_dir, "pom.xml")]
    info(f"Getting component version, running command {cmd}")
    version = subprocess.check_output(cmd).decode(sys.stdout.encoding)
    info(f"Got version for component {component_dir}: {version}")
    return version

def build_component(component_dir: str, overridden_versions) -> str:
    with open(f"logs/{component_dir}.log", "w") as f:
        with redirect_stdout(f):
            update_maven_deps(overridden_versions, component_dir)
            cmd = ["mvn", "-f", os.path.join(component_dir, "pom.xml"), "install", "-D", "skipTests"]
            info(f"Running command {cmd}")
            result = subprocess.run(cmd, stdout=sys.stdout)
            info(f"Build finished with return code {result.returncode}")
            if result.returncode != 0:
                fail(f"Error building {component_dir}")
            return get_component_version(component_dir)

# Build the component for this PR, but first build any other overridden components
# and use them.  We need to build the components in a specific order such that
# dependencies are built before the components that use them
def build_components(overridden_components):
    os.mkdir("logs")
    overridden_versions = dict()
    if "jitsi-utils" in overridden_components:
        info("Building jitsi-utils")
        jitsi_utils_version = build_component("./jitsi-utils", overridden_versions)
        overridden_versions["jitsi-utils"] = jitsi_utils_version
    if "jicoco" in overridden_components:
        info("Building jicoco")
        jicoco_version = build_component("./jicoco", overridden_versions)
        overridden_versions["jicoco"] = jicoco_version
    if "rtp" in overridden_components:
        info("Building rtp")
        rtp_version = build_component("./rtp", overridden_versions)
        overridden_versions["rtp"] = rtp_version
    if "jitsi-media-transform" in overridden_components:
        info("Building jitsi-media-transform")
        jmt_version = build_component("./jitsi-media-transform", overridden_versions)
        overridden_versions["jitsi-media-transform"] = jmt_version
    if "jitsi-videobridge" in overridden_components:
        info("Building jitsi-videobridge")
        build_component("./jitsi-videobridge", overridden_versions)
    # TODO: jitsi-metaconfig
    # TODO: log a warning if there's a component we don't recognize

def load_pr(url: str) -> dict:
    info("Retrieving PR information")
    pr_resp = requests.get(
        url,
        headers={
            **GH_REQUEST_HEADERS,
            # TODO: needed?
            "Accept": "application/vnd.github.shadow-cat-preview+json, application/vnd.github.sailor-v-preview+json",
        }
    )
    pr_resp.raise_for_status()
    return pr_resp.json()

def get_pr_comments(url: str) -> dict:
    info("Retrieving PR comments")
    comments_resp = requests.get(
        url,
        headers={
            **GH_REQUEST_HEADERS,
            # TODO: need accept type?
        }
    )
    comments_resp.raise_for_status()
    return comments_resp.json()

def retrieve_pr_body(event: dict) -> dict:
    if event["action"] in [ "synchronize", "opened", "edited" ]:
        return load_pr(event["pull_request"]["_links"]["self"]["href"])["body"]
    else:
        info("Unhandled event action type: {}".format(event["action"]))
        sys.exit(1)

# The expected input string are the deps lines after the 'deps:' prefix.  Each dep
# line must be formatted like so:
#   use <component name> <repo> <branch>
# Where:
#   component name is a the name of a jitsi component repo (e.g. jitsi-videobridge, jitsi-utils, etc.)
#   repo is the 'path' to a github repo to be used for that component (e.g. bbaldino/jitsi-videobridge)
#   branch is the branch name to be checked out from that repo
def parse_deps(deps: str) -> dict:
    overridden_components = dict()
    lines = [line.strip() for line in deps.split("\n")]
    for line in lines:
        try:
            (_, component, repo, branch) = line.split(" ")
            info(f"Will use branch {branch} from repo {repo} for component {component}")
            overridden_components[component] = (repo, branch)
        except ValueError as err:
            info(f"invalid line: {err}")
    return overridden_components

if __name__ == "__main__":
    GITHUB_EVENT_PATH = os.environ["GITHUB_EVENT_PATH"]
    GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]

    with open(GITHUB_EVENT_PATH) as event_info_file:
        event = json.load(event_info_file)

    info(f"loaded event info: {json.dumps(event)}")

    GH_REQUEST_HEADERS = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Content-Type": "application/json"
    }

    pr_body = retrieve_pr_body(event)
    info(f"Got pr body '{pr_body}'")
    deps = pr_body.split("deps:")[1]
    info(f"Got deps string: '{deps}'")
    overridden_components = parse_deps(deps)

    checkout_overridden_components(overridden_components)
    build_components(overridden_components)
    # TODO: build _this_ code
    # we can get the clone url and the branch name from the event, then run checkout
    # then we need to run update_maven_deps (need access to the overridden versions)
    # then we can build


