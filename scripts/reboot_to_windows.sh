#!/bin/bash

windows_title=$(grep -i windows /boot/grub2/grub.cfg | cut -d "'" -f 2)
sudo grub-reboot "$windows_title" && sudo reboot
