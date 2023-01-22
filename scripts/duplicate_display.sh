#!/usr/bin/env bash

run_vnc ()
{
    local width=$1
    local height=$2
    local offset=$3

    local dimension=$(xdpyinfo | grep dimension | tr -s ' ' | cut -d\  -f3)
    echo -e "\nstarting vnc at ${dimension}"

    # x11vnc -clip "${width}x${height}${offset}" -repeat -passwd password #-unixpw #-vencrypt nodh:only -ssl
    x11vnc -clip 1920x1080+0+0 -repeat -passwd password
}

run_vnc
