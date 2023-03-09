#!/usr/bin/env python3

import math
import shutil
import subprocess

MIN_TERMINAL_WIDTH: int = 80
ROOT_RESERVED: float = 0.05     # see: https://askubuntu.com/questions/249387/df-h-used-space-avail-free-space-is-less-than-the-total-size-of-home
                                # see: https://unix.stackexchange.com/questions/7950/reserved-space-for-root-on-a-filesystem-why
NAME_MAX_LEN: int = 10
PATH_MAX_LEN: int = 25


class Partition:
    # size and usedSize is in bytes
    def __init__(self, name: str = "", path: str = "", size: int = 0, usedSize: int = 0) -> None:
        self.name: str = name
        self.path: str = path
        self.size: int = size
        self.usedSize: int = usedSize + int(ROOT_RESERVED*self.size)

    # size is in kbytes
    @classmethod
    def from_percentage(cls, name: str = "", path: str = "", size: int = 0, usedPercentage: float = 0) -> None:
        usedSize: int = int(usedPercentage * size / 100)
        cls(name, path, size, usedSize)

    # progress is normalized
    def print(self, terminalWidth: int):
        try:
            progress = self.usedSize / self.size
        except:
            progress = 0

        width = terminalWidth - PATH_MAX_LEN - NAME_MAX_LEN - 35

        free = self.size - self.usedSize
        free = f"{formatBytes(free):>6} free"

        size = f"{formatBytes(self.size):>6}"

        usedPercentage = f"{round(progress*100, 1):>4}"

        # 0 <= progress <= 1
        progress = min(1, max(0, progress))
        whole_width = math.floor(progress * width)
        remainder_width = (progress * width) % 1
        part_chars = "▂▃▄▅▆"
        part_width = math.floor(remainder_width * len(part_chars))
        # part_char = part_chars[part_width]
        part_char = "▁"

        if (width - whole_width - 1) < 0:
            part_char = ""
        bar = "▇" * whole_width + part_char + "▁" * (width - whole_width - 1) if terminalWidth >= MIN_TERMINAL_WIDTH else '-'

        name: str = self.name if len(self.name) <= NAME_MAX_LEN else self.name[:NAME_MAX_LEN-1] + "…"
        path: str = self.path if len(self.path) <= PATH_MAX_LEN else self.path[:PATH_MAX_LEN-1] + "…"
        line = f"{name:<{NAME_MAX_LEN}}  {path:<{PATH_MAX_LEN}}  {usedPercentage}% of {size} {bar} {free}"
        print(line)


def toBytes(size: str):
    if size[-1] in [1, 2, 3, 4, 5, 6, 7, 8, 9, 0]:
        return int(size)

    ordering = {'k': 3, 'M': 6, 'G': 9}
    return int(size[:-1]) * ordering[size[-1]]


def formatBytes(kBytes: float) -> str:
    orderNames = {0: "k", 3: "M", 6: "G", 9: "T"}

    order = 0
    while (kBytes > 1023):
        kBytes /= 1024
        order += 3

    if (order < 6):
        kBytes = int(kBytes)
    else:
        kBytes = round(kBytes, 1)

    return str(kBytes) + orderNames[order]


def test():
    part = Partition("/dev/sda6", "/home", 123987, 123000)
    terminalWidth, _ = shutil.get_terminal_size((80, 20))
    part.print(terminalWidth)


def main():
    # get list of filesystems
    command = "df 2> /dev/null | tail -n+2 | sort -k1"
    result = subprocess\
        .run(command, shell=True, stdout=subprocess.PIPE)\
        .stdout\
        .decode("utf-8")\
        .rstrip()
    lines = result.split('\n')

    terminalWidth, _ = shutil.get_terminal_size((80, 20))

    # 0 5 1 4
    parts = []
    longestNameLength = 0
    longestPathLength = 0
    for line in lines:
        line = line.split()
        #                name     path     size          used size
        part = Partition(line[0], line[5], int(line[1]), int(line[2]))
        parts.append(part)
        longestNameLength = len(part.name) if len(part.name) > longestNameLength else longestNameLength
        longestPathLength = len(part.path) if len(part.path) > longestPathLength else longestPathLength

    global NAME_MAX_LEN
    global PATH_MAX_LEN

    if terminalWidth <= MIN_TERMINAL_WIDTH:
        NAME_MAX_LEN = MIN_TERMINAL_WIDTH//3 if longestNameLength > MIN_TERMINAL_WIDTH//3 else longestNameLength
        PATH_MAX_LEN = MIN_TERMINAL_WIDTH//3 if longestPathLength > MIN_TERMINAL_WIDTH//3 else longestPathLength
    else:
        NAME_MAX_LEN = longestNameLength
        PATH_MAX_LEN = longestPathLength

    # parts = sorted(parts, key=lambda part: (1 - ROOT_RESERVED) - part.usedSize/part.size)
    parts = sorted(parts, key=lambda part: part.name)
    for part in parts:
        part.print(terminalWidth)


if __name__ == "__main__":
#    test()
    main()
