#!/usr/bin/env bash

# use: <fun> <len> <sep>
draw_line()
{
    local num=$1
    local char=$2

    i=0
    while [[ $i -lt $1 ]]; do
        echo -n "$2"
        i=$((i+1))
    done
}

find_max_len()
{
    echo "$1" | \
        awk -v max=-1 '
            {l = length}
            l > max {max = l}
            END {if (max >= 0) printf "%s", l}'
}

surround()
{
    local str="$1"
    local sep="$2"
    echo "$str" | awk -v len=$(find_max_len "$str") -v sep="$sep" '{ printf("%s %s%*s\n", sep, $0, len-length($0), sep) }'
}

insert_left()
{
    local str="$1"
    local ins="$2"
    echo "$str" | awk -v len=$(find_max_len "$str") -v ins="$ins" '{ printf("%s%s\n", ins, $0) }'
}

locate -b --regex '\.git$' \
    | while read f; do
        if [[ -d "$f" ]]; then
            path=$(dirname "$f")
            output=$(git -C "$path" -c color.status=always status 2> /dev/null)
            if [[ ${#output} -eq 0 ]]; then continue; fi

            output=$(insert_left "$output" "    ")
            len="${#path}"
            str_len=$(find_max_len "$output")
            # if [[ $str_len -gt $len ]]; then len=$str_len; fi


            echo -n '┏'; draw_line $((len + 6)) "━"; echo '┓'
            echo "┃   $path   ┃";
            # echo -n '┖'; draw_line $((len + 6)) "─"; echo '┚'
            echo -n '┞'; draw_line $((len + 6)) "─"; echo '┦'

            # echo $(find_max_len "$output")
            # surround "$output" "|"
            echo "$output"

            echo -n '┗'; draw_line $((len + 6)) "━"; echo '┛'

            echo -ne "\n\n"
        fi
    done \
        | less -R
