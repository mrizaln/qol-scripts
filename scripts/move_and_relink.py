#!/usr/bin/env python3

import subprocess
from typing import List, Tuple
from pathlib import Path
from argparse import ArgumentParser
from enum import Enum


DEFAULT_MAX_DEPTH = 5


class LinkType(Enum):
    EXACT = 1
    STARTS_WITH = 2


# using find because it's faster than python's os.walk or pathlib.glob
def get_potential_links(search_dir: Path, max_depth: int, name: str) -> List[str]:
    cmd = f"find {search_dir} -maxdepth {max_depth} -type l -lname '*{name}*'"  # TODO: better query
    run = subprocess.run(cmd, shell=True, capture_output=True)
    result = run.stdout.decode("utf-8").rstrip().split("\n")
    return [] if result == [""] else result


# returns the common parent and the count to reach it for left and right
def find_common_parent(left: Path, right: Path) -> Tuple[Path, int, int]:
    left_parts = left.parts
    right_parts = right.parts

    common_parts = []
    for l, r in zip(left_parts, right_parts):
        if l == r:
            common_parts.append(l)
        else:
            break

    left_up_depth = len(left_parts) - len(common_parts)
    right_up_depth = len(right_parts) - len(common_parts)

    return Path(*common_parts), left_up_depth, right_up_depth


def link_match_target(link: Path, target: Path) -> None | LinkType:
    if target.is_dir():
        print(f"{link} -> {link.resolve()} | {target} -> {target.resolve()}")
        parent, _, _ = find_common_parent(link.resolve(), target.resolve())
        return LinkType.STARTS_WITH if parent.samefile(target) else None

    # read the link once in case it's a symlink to a symlink (to a symlink ...) that points to the target
    realpath = link.parent / link.readlink()
    if realpath.is_symlink() and not target.is_symlink():  # enable if target is symlink
        return None

    return LinkType.EXACT if realpath.samefile(target) else None


# TODO: 1. handle fixing links inside target directory (if target is directory)
#       2. handle fixing target itself if target is a symlink (partial work has been done)
#       3. better printing of the possible relinks
def move_and_relink(target: Path, destination: Path, search_dir: Path, depth: int):
    potential_links = get_potential_links(search_dir, depth, target.name)

    links: List[Tuple[Path, Path, LinkType]] = []  # link, realpath, link_type
    for link in potential_links:
        link = Path(link)
        link_type = link_match_target(link, target)
        if link_type is not None:
            links.append((link, link.readlink(), link_type))

    links_to_fix: List[Tuple[Path, Path, Path]] = []  # link, realpath (old), newpath
    for link, realpath, link_type in links:
        newpath = Path()
        if link.parent.samefile(destination.parent):
            newpath = Path(destination.name)
            if link_type == LinkType.STARTS_WITH:
                newpath = newpath / link.resolve().relative_to(link.parent)
        else:
            parent, link_up, _ = find_common_parent(
                link.absolute(), destination.resolve()
            )
            print(f"{parent} | {link} | {destination} | {link_up}")
            newpath = Path("../" * (link_up - 1)) / destination.resolve().relative_to(
                parent
            )
            if link_type == LinkType.STARTS_WITH:
                newpath = newpath / link.resolve().relative_to(target.resolve())

        links_to_fix.append((link, realpath, newpath))

    print(f"Rename: {target} -> {destination}")
    if len(links_to_fix) > 0:
        for link, oldpath, newpath in links_to_fix:
            print(f"link: {link}:")
            print(f"\t\t {oldpath} -> {newpath}")
    else:
        print("No links to fix")

    # confirm
    confirm = input("Proceed? (y/N): ")
    if confirm and confirm.lower()[0] == "y":
        # move target
        if target.is_symlink():
            realpath = target.resolve()
            parent, up, _ = find_common_parent(destination, realpath)
            realpath = Path("../" * (up - 1)) / realpath.relative_to(parent)  # -1 link
            destination.symlink_to(realpath)
            target.unlink()
        else:
            target.rename(destination)

        for link, oldpath, newpath in links_to_fix:
            link.unlink()
            link.symlink_to(newpath)
    else:
        print("Aborted")


def main():
    arg_parser = ArgumentParser()

    arg_parser.add_argument("target", type=str, help="Target file to be relinked")
    arg_parser.add_argument(
        "destination", type=str, help="Move destination or new name for target"
    )
    arg_parser.add_argument(
        "search_dir",
        type=str,
        help="Directory to search for links to target (default: current directory)",
        default=".",
        nargs="?",
    )
    arg_parser.add_argument(
        "-d",
        "--depth",
        type=int,
        help="Max depth to search for links (default: 5)",
        default=DEFAULT_MAX_DEPTH,
    )

    args = arg_parser.parse_args()

    target = Path(args.target)
    destination = Path(args.destination)
    search_dir = Path(args.search_dir)

    if target.is_symlink():
        print("Target cannot be a symlink (still working on it)")
        return

    if target.is_file() and destination.is_dir():
        destination = destination / target.name

    if not target.exists():
        print(f"Target {target} does not exist")
        return

    if destination.exists():
        print(f"Destination {destination} already exists")
        return

    if not search_dir.exists():
        print(f"Search directory {search_dir} does not exist")
        return

    move_and_relink(target, destination, search_dir, args.depth)


if __name__ == "__main__":
    main()
