#!/bin/bash

main()
{
    local time_flag=""
    local reverse_flag=""
    local do_clear=false

    for arg in ${@}; do
        if [[ "$arg" == "-t" ]]; then
            time_flag="-t"
        fi
        if [[ "$arg" == "-r" ]]; then
            reverse_flag="-r"
        fi
        if [[ "$arg" == "-c" ]]; then
            do_clear=true
        fi
    done

    while read -u 10 f; do                  # 10 is an arbitrary integer used as a file descriptor, u can change it any time
        [[ $do_clear == true ]] && clear
        catimg -r 2 -H "$((ROWS))" "$f"         # $COLUMNS is a feature of bash that returns the width of terminal in use
        echo "$PWD/$f"
        read dummy
    done 10< <(ls $time_flag $reverse_flag | grep -iE "png|jpg|jpeg|webp")
}

if ! command -v catimg &> /dev/null; then
    echo "catimg is not installed"
    exit 1
fi

if [[ "$1" == "-h" || "$1" == "--help" ]]; then
    echo "Usage: catimg_all [-t] [-r] [-c]"
    echo "  -t: Sort by time"
    echo "  -r: Reverse the order"
    echo "  -c: Clear the screen before showing each image"
    exit 0
fi

main "$@"
