#!/usr/bin/env bash

path=$(realpath -e "$@")

if [ $? = 0 ]; then
    echo "$path" | copy_to_clipboard.sh -
    echo "$path"
fi
