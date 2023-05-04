#!/usr/bin/env bash

swap_files()
{
    # _swap_files "$1" "$2" "$3"
}

_swap_files()
{
    local target="$1"
    local destination="$2"
    local lookup_dir="$3"

    if [[ -d "$target" || -d "$destination" ]]; then
        echo "Currently no support for directory"
        rmdir "$temp_dir"
        return
    fi

    # destination is symlink
    if [[ -f "$target" && -L "$destination" ]]; then
        local real_file="$target"
        local link="$destination"
        local link_real_path="$(readlink -f "$link")"

        if [[ "$real_file" -ef "$link_real_path" ]]; then
            _swap_link_with_target "$link" "$real_file"
        else
            echo "not matching"
        fi

    # both are regular && not symlink
    elif [[ -f "$target" && -f "$destination" ]]; then
        _swap_file_with_file "$target" "$destination"
    fi

}

# <real_file> <real_file>
# return: echo target file in new destination
_swap_file_with_file()
{
    local target="$1"
    local destination="$2"

    local temp_dir="$(mktemp -d)"

    mv "$target" "$temp_dir/"
    mv "$destination" "$(dirname "$target")"
    mv "$temp_dir/${target##*/}" "$(dirname "$destination")"

    rmdir "$temp_dir"
}

# <link> <link_target> <lookup_dir>
_swap_link_with_target()
{
    local link_position="$1"
    local link_target="$2"

    _swap_file_with_file "$link_position" "$link_target"

    local link_position_new="$(dirname "$link_target")/${link_position##*/}"
    local link_target_new="$(dirname "$link_position")/${link_target##*/}"

    echo "new pos   : $link_position_new"
    echo "new target: $link_target_new"

    ln -sf "$link_target_new" "$link_position_new"
}

if [[ -z "$1" || "$1" == "-h" ]]; then
    echo "Usage: $0 <target> <destination> [lookup_dir]"
    echo
    echo "This script will swap location of <target> and <destination>"
    echo "If one of the file is symlink of the other one, this script will also"
    echo "try to relink them."
    echo
    echo "In addition, if you're sure one or both of the file must be linked"
    echo "somewhere, you can add third argument on to where to look said link."
    echo "Then, this script will relink them for you."
else
    swap_files "$1" "$2" "$3"
fi
