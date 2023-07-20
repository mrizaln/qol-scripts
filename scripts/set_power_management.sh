#!/usr/bin/env bash

case "$1" in
    on)
        xset s on
        xset s blank
        xset +dpms
        systemctl --user start xidlehook-suspend.service
        ;;
    off)
        xset s off
        xset s noblank
        xset -dpms
        systemctl --user stop xidlehook-suspend.service
        ;;
    status)
        ;;
    *)
         echo "Usage: $0 [on|off|status]"
        exit 0
        ;;
esac

xset -q | grep -A2 "DPMS"
echo -e "\n"
systemctl --no-pager --user status xidlehook-suspend.service
