#!/usr/bin/env python3

import math
import shutil
import platform
import subprocess
from argparse import ArgumentParser
from enum import Enum
from pathlib import Path

# see: https://askubuntu.com/questions/249387/df-h-used-space-avail-free-space-is-less-than-the-total-size-of-home
# see: https://unix.stackexchange.com/questions/7950/reserved-space-for-root-on-a-filesystem-why
ROOT_RESERVED: float = 0.00 # 0.05

MIN_TERMINAL_WIDTH: int = 100
NAME_MAX_LEN: int = 10
PATH_MAX_LEN: int = 25
SHOW_REMAINDER_FLOAT_AS_PARTIAL_BLOCK: bool = True

LINE_SIZE_APPROX: int = 38  # approximate size of a line without name and path

TIMEOUT_SECONDS: int = 2


class DeviceType(Enum):
    LOCAL = 1
    ADB = 2


class Partition:
    # size and usedSize is in bytes
    def __init__(
        self, name: str = "", path: Path = Path(), size: int = 0, usedSize: int = 0
    ) -> None:
        self.name: str = name
        self.path: Path = path
        self.size: int = size

        if path == "/" or path == "/home":
            self.usedSize: int = usedSize + int(ROOT_RESERVED * self.size)
        else:
            self.usedSize: int = usedSize

    # size is in kbytes
    @classmethod
    def from_percentage(
        cls,
        name: str = "",
        path: Path = Path(),
        size: int = 0,
        usedPercentage: float = 0,
    ) -> None:
        usedSize: int = int(usedPercentage * size / 100)
        cls(name, path, size, usedSize)

    # progress is normalized
    def print(self, terminalWidth: int):
        progress: float
        try:
            progress = self.usedSize / self.size
        except:
            progress = 0.0

        width = max(0, terminalWidth - PATH_MAX_LEN - NAME_MAX_LEN - LINE_SIZE_APPROX)

        free = f"{formatBytes(self.size - self.usedSize):>6} free"

        size = f"{formatBytes(self.size):>6}"

        usedPercentage = f"{round(progress*100, 1):>5}"

        # 0 <= progress <= 1
        progress = min(1, max(0, progress))
        whole_width = max(0, math.floor(progress * width))

        part_char = "▁"
        if SHOW_REMAINDER_FLOAT_AS_PARTIAL_BLOCK:
            remainder_width = max(0, math.fmod(progress * width, 1))
            part_chars = "▂▃▄▅▆"
            part_width = math.floor(remainder_width * len(part_chars))
            part_char = part_chars[part_width]

        if (width - whole_width - 1) < 0:
            part_char = ""

        bar: str | None = (
            "▇" * whole_width + part_char + "▁" * (width - whole_width - 1)
            if terminalWidth >= MIN_TERMINAL_WIDTH
            else None
        )

        name: str = (
            self.name
            if len(self.name) <= NAME_MAX_LEN
            else self.name[: NAME_MAX_LEN - 1] + "…"
        )
        path_str = str(self.path)
        path: str = (
            path_str
            if len(path_str) <= PATH_MAX_LEN
            else path_str[: PATH_MAX_LEN - 1] + "…"
        )
        size_combined: str = (
            f"{size} {bar} [{free}]" if (bar != None) else f"{size} [{free}]"
        )
        pad: str = "  "
        line = f"{pad}{name:<{NAME_MAX_LEN}}  {path:<{PATH_MAX_LEN}} [{usedPercentage}%] of {size_combined}"
        print(line)


def toBytes(size: str):
    if size[-1] in [1, 2, 3, 4, 5, 6, 7, 8, 9, 0]:
        return int(size)

    ordering = {"k": 3, "M": 6, "G": 9}
    return int(size[:-1]) * ordering[size[-1]]


def formatBytes(kBytes: float) -> str:
    orderNames = {0: "k", 3: "M", 6: "G", 9: "T"}

    order = 0
    while kBytes > 1023:
        kBytes /= 1024
        order += 3

    if order < 6:
        kBytes = int(kBytes)
    else:
        kBytes = round(kBytes, 1)

    return str(kBytes) + orderNames[order]


def adb_devices():
    devices = (
        subprocess.run(
            "adb devices | tail -n+2 | head -n-1 | awk -F ' ' '{print $1}'",
            shell=True,
            stdout=subprocess.PIPE,
        )
        .stdout.decode("utf-8")
        .rstrip()
    )
    return devices.split("\n")


def print_parts(parts: list[Partition], longestNameLength: int, longestPathLength: int):
    global NAME_MAX_LEN
    global PATH_MAX_LEN

    terminalWidth, _ = shutil.get_terminal_size((80, 20))
    availableWidth = terminalWidth - LINE_SIZE_APPROX

    if terminalWidth <= MIN_TERMINAL_WIDTH:
        NAME_MAX_LEN = max(
            LINE_SIZE_APPROX // 2, min(availableWidth // 2, longestNameLength)
        )
        PATH_MAX_LEN = max(
            LINE_SIZE_APPROX // 2, min(availableWidth // 2, longestPathLength)
        )
    else:
        NAME_MAX_LEN = longestNameLength
        PATH_MAX_LEN = longestPathLength

    # parts = sorted(parts, key=lambda part: (1 - ROOT_one, env=None, universal_newlinesRESERVED) - part.usedSize/part.size)
    parts = sorted(parts, key=lambda part: part.name)
    for part in parts:
        part.print(terminalWidth)


def print_storage_info(device_type: DeviceType):
    # get list of filesystems
    commands: list[str] = []
    device_names: list[str] = []
    if device_type == DeviceType.LOCAL:
        commands.append("df | tail -n+2 | sort -k1")
        device_names.append(platform.node())
    elif device_type == DeviceType.ADB:
        devices_adb = adb_devices()
        if len(devices_adb) == 0 or (len(devices_adb) == 1 and devices_adb[0] == ""):
            print("No Android device connected")
            return

        for device in adb_devices():
            commands.append(
                f"adb -s {device} shell df | grep -iE 'fuse|/storage/' | sort -k1"
            )
            device_names.append(f"{device} (adb device)")

    title_string = lambda s: f"\033[1;47;30mStorage information for [{s}]:\033[0m"

    lines: list[str] = []
    for device, command in zip(device_names, commands):
        print(title_string(device))

        try:
            run = subprocess.run(
                command, shell=True, capture_output=True, timeout=TIMEOUT_SECONDS
            )
        except subprocess.TimeoutExpired as e:
            print(f"[Error: timeout of {e.timeout}s is reached]\n")
            continue
        except Exception as e:
            print(f"[Error: {e}]\n")
            continue

        result: str = ""
        if run.returncode != 0:
            print(f"[Error: command exited with return code {run.returncode}]\n")
            continue
        else:
            result = run.stdout.decode("utf-8").rstrip()

        lines = result.split("\n")
        if len(lines) == 0:
            print(f"[Error: empty output]\n")
            continue
        elif len(lines[0].split()) != 6:
            # 'df' command returns 6 columns of data per line
            print(f"[Error: output is not correct (column size: {len(lines[0])})]\n")
            continue

        parts = []
        longestNameLength = 0
        longestPathLength = 0
        for line in lines:
            line = line.split()
            # 0: name | 1: size | 2: used | 3: avail | 4: percentage | 5: mount
            #                name     path           size          used size
            part = Partition(line[0], Path(line[5]), int(line[1]), int(line[1]) - int(line[3]))
            parts.append(part)

            longestNameLength = (
                len(part.name)
                if len(part.name) > longestNameLength
                else longestNameLength
            )

            longestPathLength = (
                len(str(part.path))
                if len(str(part.path)) > longestPathLength
                else longestPathLength
            )

        print_parts(parts, longestNameLength, longestPathLength)
        print()


def main():
    arg_parser = ArgumentParser()

    arg_parser.add_argument(
        "mode",
        help="query mode",
        choices=["local", "adb", "both"],
        default="both",
        nargs="?",
    )

    args = arg_parser.parse_args()

    match args.mode:
        case "local":
            print_storage_info(DeviceType.LOCAL)
        case "adb":
            print_storage_info(DeviceType.ADB)
        case "both":
            print_storage_info(DeviceType.LOCAL)
            print_storage_info(DeviceType.ADB)


if __name__ == "__main__":
    main()
