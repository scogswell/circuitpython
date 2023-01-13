#! /usr/bin/env python3

# SPDX-FileCopyrightText: 2021 Scott Shawcroft
# SPDX-FileCopyrightText: 2021 microDev
#
# SPDX-License-Identifier: MIT

"""
This script is used in GitHub Actions to determine what docs/boards are
built based on what files were changed. The base commit varies depending
on the event that triggered run. Pull request runs will compare to the
base branch while pushes will compare to the current ref. We override this
for the adafruit/circuitpython repo so we build all docs/boards for pushes.

When making changes to the script it is useful to manually test it.
You can for instance run
```shell
tools/ci_set_matrix ports/raspberrypi/common-hal/socket/SSLSocket.c
```
and (at the time this comment was written) get a series of messages indicating
that only the single board raspberry_pi_pico_w would be built.
"""

import re
import os
import sys
import json
import pathlib
from concurrent.futures import ThreadPoolExecutor

tools_dir = pathlib.Path(__file__).resolve().parent
top_dir = tools_dir.parent

sys.path.insert(0, str(tools_dir / "adabot"))
sys.path.insert(0, str(top_dir / "docs"))

import build_board_info
from shared_bindings_matrix import (
    get_settings_from_makefile,
    SUPPORTED_PORTS,
    all_ports_all_boards,
)

PORT_TO_ARCH = {
    "atmel-samd": "arm",
    "broadcom": "aarch",
    "cxd56": "arm",
    "espressif": "espressif",
    "litex": "riscv",
    "mimxrt10xx": "arm",
    "nrf": "arm",
    "raspberrypi": "arm",
    "stm": "arm",
}

IGNORE = [
    "tools/ci_set_matrix.py",
    "tools/ci_check_duplicate_usb_vid_pid.py",
]

# Files in these directories never influence board builds
IGNORE_DIRS = ["tests", "docs", ".devcontainer"]

if len(sys.argv) > 1:
    print("Using files list on commandline")
    changed_files = sys.argv[1:]
    last_failed_jobs = {}
else:
    c = os.environ["CHANGED_FILES"]
    if c == "":
        print("CHANGED_FILES is in environment, but value is empty")
        changed_files = []
    else:
        print("Using files list in CHANGED_FILES")
        changed_files = json.loads(c.replace("\\", ""))

    j = os.environ["LAST_FAILED_JOBS"]
    if j == "":
        print("LAST_FAILED_JOBS is in environment, but value is empty")
        last_failed_jobs = {}
    else:
        last_failed_jobs = json.loads(j)


def set_output(name, value):
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "at") as f:
            print(f"{name}={value}", file=f)
    else:
        print(f"Would set GitHub actions output {name} to '{value}'")


def set_boards_to_build(build_all):
    # Get boards in json format
    boards_info_json = build_board_info.get_board_mapping()
    all_board_ids = set()
    port_to_boards = {}
    board_to_port = {}
    board_settings = {}
    for board_id in boards_info_json:
        info = boards_info_json[board_id]
        if info.get("alias", False):
            continue
        all_board_ids.add(board_id)
        port = info["port"]
        if port not in port_to_boards:
            port_to_boards[port] = set()
        port_to_boards[port].add(board_id)
        board_to_port[board_id] = port

    def compute_board_settings(boards):
        need = set(boards) - set(board_settings.keys())
        if not need:
            return

        def get_settings(board):
            return (
                board,
                get_settings_from_makefile(str(top_dir / "ports" / board_to_port[board]), board),
            )

        with ThreadPoolExecutor(max_workers=os.cpu_count()) as ex:
            board_settings.update(ex.map(get_settings, need))

    boards_to_build = all_board_ids

    if not build_all:
        boards_to_build = set()
        board_pattern = re.compile(r"^ports/[^/]+/boards/([^/]+)/")
        port_pattern = re.compile(r"^ports/([^/]+)/")
        module_pattern = re.compile(
            r"^(ports/[^/]+/(?:common-hal|bindings)|shared-bindings|shared-module)/([^/]+)/"
        )
        for p in changed_files:
            # See if it is board specific
            board_matches = board_pattern.search(p)
            if board_matches:
                board = board_matches.group(1)
                boards_to_build.add(board)
                continue

            # See if it is port specific
            port_matches = port_pattern.search(p)
            port = port_matches.group(1) if port_matches else None
            module_matches = module_pattern.search(p)
            if port and not module_matches:
                if port != "unix":
                    boards_to_build.update(port_to_boards[port])
                continue

            # Check the ignore list to see if the file isn't used on board builds.
            if p in IGNORE:
                continue

            if any([p.startswith(d) for d in IGNORE_DIRS]):
                continue

            # As a (nearly) last resort, for some certain files, we compute the settings from the
            # makefile for each board and determine whether to build them that way.
            if p.startswith("frozen") or p.startswith("supervisor") or module_matches:
                if port:
                    board_ids = port_to_boards[port]
                else:
                    board_ids = all_board_ids
                compute_board_settings(board_ids)
                for board in board_ids:
                    settings = board_settings[board]

                    # Check frozen files to see if they are in each board.
                    frozen = settings.get("FROZEN_MPY_DIRS", "")
                    if frozen and p.startswith("frozen") and p in frozen:
                        boards_to_build.add(board)
                        continue

                    # Check supervisor files. This is useful for limiting workflow changes to the
                    # relevant boards.
                    supervisor = settings["SRC_SUPERVISOR"]
                    if p.startswith("supervisor"):
                        if p in supervisor:
                            boards_to_build.add(board)
                            continue

                        web_workflow = settings["CIRCUITPY_WEB_WORKFLOW"]
                        while web_workflow.startswith("$("):
                            web_workflow = settings[web_workflow[2:-1]]
                        if (
                            p.startswith("supervisor/shared/web_workflow/static/")
                            and web_workflow != "0"
                        ):
                            boards_to_build.add(board)
                            continue

                    # Check module matches
                    if module_matches:
                        module = module_matches.group(2) + "/"
                        if module in settings["SRC_PATTERNS"]:
                            boards_to_build.add(board)
                            continue
                continue

            # Otherwise build it all
            boards_to_build = all_board_ids
            break

    # Split boards by architecture.
    print("Building boards:")
    arch_to_boards = {"aarch": [], "arm": [], "riscv": [], "espressif": []}
    for board in sorted(boards_to_build):
        print(" ", board)
        port = board_to_port.get(board)
        # A board can appear due to its _deletion_ (rare)
        # if this happens it's not in `board_to_port`.
        if not port:
            continue
        arch = PORT_TO_ARCH[port]
        arch_to_boards[arch].append(board)

    # Set the step outputs for each architecture
    for arch in arch_to_boards:
        # Append previous failed jobs
        if f"build-{arch}" in last_failed_jobs:
            failed_boards = last_failed_jobs[f"build-{arch}"]
            for board in failed_boards:
                if not board in arch_to_boards[arch]:
                    print(" ", board)
                    arch_to_boards[arch].append(board)
        # Set Output
        set_output(f"boards-{arch}", json.dumps(sorted(arch_to_boards[arch])))


def set_docs_to_build(build_all):
    if "build-doc" in last_failed_jobs:
        build_all = True

    doc_match = build_all
    if not build_all:
        doc_pattern = re.compile(
            r"^(?:.github/workflows/|docs|extmod/ulab|(?:(?:ports/\w+/bindings|shared-bindings)\S+\.c|conf\.py|tools/extract_pyi\.py|requirements-doc\.txt)$)|(?:-stubs|\.(?:md|MD|rst|RST))$"
        )
        for p in changed_files:
            if doc_pattern.search(p):
                doc_match = True
                break

    # Set the step outputs
    print("Building docs:", doc_match)
    set_output("build-doc", doc_match)


def check_changed_files():
    if not changed_files:
        print("Building all docs/boards")
        return True
    else:
        print("Adding docs/boards to build based on changed files")
        return False


def main():
    build_all = check_changed_files()
    set_docs_to_build(build_all)
    set_boards_to_build(build_all)


if __name__ == "__main__":
    main()
