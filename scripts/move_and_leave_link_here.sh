#!/usr/bin/env bash

mv_then_ln() {
    local target_file="$1";
    local destination_dir="$2";

    if ! [[ -f "$target_file" ]]; then
        echo "target file does not exist"
        return 1;
    fi

    if ! [[ -d "$destination_dir" ]]; then
        echo "destination is not a directory or does not exist"
        return 1;
    fi

    mv "$target_file" "$destination_dir"
    ln -s "$destination_dir/$(basename "$target_file")" .
}

if [[ "$#" -ne 2 ]]; then
    echo "Usage: mv_then_ln <target_file> <destination_dir>"
    exit 1;
fi

mv_then_ln "$1" "$2"
