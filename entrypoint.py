#!/usr/bin/env python3

import json
import os
import subprocess
import sys

import git

def error(msg: str) -> None:
    print(f"[error]: {msg}")

def info(msg: str) -> None:
    print(f"[info]: {msg}")

def checkout_component(component_name, repo, branch_name, checkout_dir):
    info(f"Checking out branch '{branch_name}' from repo '{repo}' for component '{component_name}'")
    git.Repo.clone_from(f"https://github.com/{repo}.git", os.path.join(checkout_dir, component_name), branch=branch_name, depth=1)

def checkout_overridden_components(overridden_components):
    for (component, (repo, branch)) in overridden_components.items():
        checkout_component(component, repo, branch, ".")

def get_component_version(component_dir):
    cmd = ["xmlstarlet", "sel", "-t", "-v", "/_:project/_:version", os.path.join(component_dir, "pom.xml")]
    info(f"Getting component version, running command {cmd}")
    version = subprocess.check_output(cmd)
    info(f"Got version for component {component_dir}: {version}")

def build_component(component_dir):
    cmd = ["mvn", "-f", os.path.join(component_dir, "pom.xml"), "install", "-D", "skipTests"]
    info(f"Running command {cmd}")
    result = subprocess.run(cmd)
    info(f"Build finished with return code {result.returncode}")
    get_component_version(component_dir)

# Build the component for this PR, but first build any other overridden components
# and use them.  We need to build the components in a specific order such that
# dependencies are built before the components that use them
def build_components(overridden_components):
    if "jitsi-utils" in overridden_components:
        info("Building jitsi-utils")
        build_component("jitsi-utils")
    # others....
    if "jitsi-videobridge" in overridden_components:
        pass

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
    info(f"Parsed comment body '{comment_body}'")
    # TEMP - hard code comment body to test
    comment_body = """deps:
    use jitsi-utils bbaldino/jitsi-utils outcome
    """
    # END TEMP

    if not comment_body.startswith("deps"):
        info("Not a deps comment, ignoring")
        sys.exit(0)

    overridden_components = dict()
    # Separate each line, ignoring the first one ('deps:')
    lines = [line.strip() for line in comment_body.split("\n")[1:]]
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
    build_component("jitsi-utils")
    # We need to:
    # build and install all components, in a specific order.  For now we'll support the jvb path, so this
    #   order should work:
    #   1) jitsi-utils
    #   2) jicoco
    #   3) rtp
    #   4) jmt
    #   5) jvb

