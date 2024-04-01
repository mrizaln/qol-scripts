#!/usr/bin/env bash

home="/home/mrizaln"

BASH_HIST=$home/.bash_history
BACKUP_DIR=$home/.bash_history.d
BACKUP="${BACKUP_DIR}/.bash_history.$(date +%Y%m%d_%H%M)"
MAX_BACKUP=30

backup()
{
    mkdir -p "$BACKUP_DIR"

    # file already exist    (need a .gz extension there since the backup file is compressed by gzip)
    # if $1 == --force, we skip this check
    if [[ -f "$BACKUP.gz" && "$1" != "--force" ]]; then
        echo "backup file already exist: $BACKUP.gz"
        exit 0
    fi

    if [[ "$1" == "--force" ]]; then
        rm "$BACKUP.gz"
    fi

    cp "$BASH_HIST" "$BACKUP"
    gzip "$BACKUP"

    # only make MAX_BACKUP copies
    if [[ $(ls "$BACKUP_DIR/.bash_history"* | wc -l) -ge $MAX_BACKUP ]]; then
        ls -t "$BACKUP_DIR/.bash_history"* | tail -n+${MAX_BACKUP} | \
        while read f; do
            echo removing $f
            rm "$f"
        done
    fi
}

restore()
{
    local file="$1"
    if [ -z "$file" ]; then
        file=$(ls $BACKUP_DIR/.bash_history.* -rt1 | tail -n1)
    fi

    if ! [ -e "$file" ]; then
        echo file does not exist
        exit 1
    fi

    echo "Source file: $file"
    local ans
    read -p "Are you sure you want to restore your bash history? [y/N] " ans

    case $ans in
        y | Y | yes | Yes | YES)
            ;;
        *)
            echo "Aborted"
            exit 0;
            ;;
    esac

    temp_dir=$(mktemp -d)
    cp "$file" "$temp_dir/.bash_history.gz"
    gunzip "$temp_dir/.bash_history.gz"
    rm "$BASH_HIST"
    mv "$temp_dir/.bash_history" "$BASH_HIST"
    rm -r "$temp_dir"

    echo "Restored from $file to $BASH_HIST"
}

main()
{
    if [[ $1 == "--restore" ]]; then
        restore $2
    elif [[ $1 == "--force-backup" ]]; then
        backup --force
    elif [[ $1 == "--backup" ]]; then
        backup
    else
        echo "Usage: $0 [--backup] [--restore [file]] [--force-backup]"
        exit 0
    fi
}

main "$@"
