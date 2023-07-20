#!/usr/bin/env bash

if [ -z $1 ]; then echo "Usage: $0 <executable> [args]"; exit 1; fi

memusage -d "$1.memusage" "$@"
memusagestat -x1920 -y1080 -t "$1.memusage" -o "$1.memusage.png"
feh -g 960x540 -d --scale-down "$1.memusage.png"
