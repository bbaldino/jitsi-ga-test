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
    # others....
    if "jitsi-videobridge" in overridden_components:
        info("Building jitsi-videobridge")
        build_component("./jitsi-videobridge", overridden_versions)


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

    pr = load_pr(event["issue"]["pull_request"]["url"])
    comments_url = pr["comments_url"]
    comments = get_pr_comments(comments_url)
    info(f"got comments {json.dumps(comments)}")

    deps_comment = next((comment for comment in comments if comment["author_association"] == "OWNER" and comment["body"].startswith("deps:")), "")

    info("Found deps comment: {}".format(deps_comment["body"]))

    overridden_components = dict()
    # Separate each line, ignoring the first one ('deps:')
    lines = [line.strip() for line in deps_comment["body"].split("\n")[1:]]
    for line in lines:
        try:
            print(line)
            print(line.split(" "))
            # The expected format is "use <component name> <repo> <branch>
            # Where:
            # component name is something like 'jitsi-videobridge' or 'jicofo'
            # repo is owner/repo name, e.g.: 'bbaldino/jitsi-videobridge'
            # branch is the branch name, e.g.: my_cool_feature
            (_, component, repo, branch) = line.split(" ")
            info(f"Will use branch {branch} from repo {repo} for component {component}")
            overridden_components[component] = (repo, branch)
        except ValueError as err:
            info(f"invalid line: {err}")

    checkout_overridden_components(overridden_components)
    print(os.listdir("."))
    print(os.listdir("./jitsi-utils"))
    build_components(overridden_components)
    # We need to:
    # build and install all components, in a specific order.  For now we'll support the jvb path, so this
    #   order should work:
    #   1) jitsi-utils
    #   2) jicoco
    #   3) rtp
    #   4) jmt
    #   5) jvb

