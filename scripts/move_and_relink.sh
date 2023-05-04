#!/usr/bin/env bash

# rename or move file/directory also relink all symbolic link that points to it
mv_ln() {
    if [[ -L "$1" ]]; then      # if it is a symlink, dont bother about relinking
        [[ -z "$2" ]] && return
        mv "$1" "$2"
    elif [[ -n "$1" ]]; then
        local name="${1%/}"       # read first parameter then remove trailing slash
        local new_name="${2%/}"   # read second parameter then remove trailing slash

        local dir="$3"            # optional parameter: where to search links
        [[ -z "$dir" ]] && dir="$HOME"

        local affected_links="$(find "$dir" -maxdepth 10 -type l -lname "*${name}*")"  # prevents the shell to prematurely expand wild card
        if [[ -z "$affected_links" ]]; then
            mv "$name" "$new_name"
            return;
        fi
        local links_destination="$(echo "${affected_links}" | while read link; do ls -lFh "$link"; done | tr -s " " | cut -d\  -f9- | awk -F '-> ' '{print$2}')"

        local affected_links_list
        local links_destination_list
        readarray -t affected_links_list <<< "$affected_links"
        readarray -t links_destination_list <<< "$links_destination"

        echo "Modification will be applied to these files:"
        for i in ${!affected_links_list[@]}; do
            echo -e "\t ${affected_links_list[i]}   :->   ${links_destination_list[i]/$name/\\033[34m$new_name\\033[0m}"        # add highlighting
        done | column -s ':' -t -l2

        local ans
        read -p "Continue [Y/n]? " ans

        case $ans in
            '')  ;&
            'y') ;&
            'Y') ;;
            *) echo "Aborted"; return ;;
        esac

        echo "Moving file/directory"
        mv "$name" "$new_name"

        # relink the symlinks
        echo "Relinking"
        for i in ${!affected_links_list[@]}; do
            local link="${affected_links_list[i]}"
            local target="${links_destination_list[i]/$name/$new_name}"

            rm "$link"
            ln -s "${target%/}" "${link%/}"
        done
        echo "Done"
    else
        echo "usage: mv_ln <from> <to>"
        echo "from is the directory suspected to be inside some symbolic link"
    fi
}

if [[ $1 == "-h" || -z "$1" ]]; then
    echo "Usage: $0 <target> <destination> [lookup_dir]"
    echo
    echo "lookup_dir: Directory on which to look for symlinks of target (maxdepth = 10)"
    echo "            By default, it will search from \$HOME directory"
    echo "            Expect a long time if you have many files"
else
    mv_ln "$1" "$2" "$3"
fi
