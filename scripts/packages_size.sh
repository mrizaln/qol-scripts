#!/usr/bin/env bash

util_pretty_print() {
    printed_list=$(printf "%s, " "$@")
    echo "[${printed_list%, }]"
}

dpkg_query_function() {
    dpkg-query --show --showformat='${Installed-Size}\t${Package}\n' \
        | sort -rh \
        | head -$1 \
        | awk '{print $1/1024, $2}'
}

rpm_query_function() {
    while read size name; do
        size_in_MiB=$(echo "scale=2; $size / (1000 * 1000)" | bc)
        echo "${size_in_MiB}M ${name}";
    done < <(rpm -qa --queryformat '%{SIZE} %{NAME} \n') \
        | sort -n \
        | tail -n$1 \
        | column -s ' ' -t -o ' | ' -R1
}

# test command corresponds to what command to check before querying 
# (most of the time the command to be tested is the same as the command used for querying)
TEST_COMMANDS=(dpkg-query rpm)
COMMANDS=(dpkg_query_function rpm_query_function)

if [[ ${#TEST_COMMANDS[@]} != ${#COMMANDS[@]} ]]; then
    echo "error: TEST_COMMANDS and COMMANDS arrays must have the same length"
    echo "TEST_COMMANDS: $(util_pretty_print ${TEST_COMMANDS[@]})"
    echo "COMMANDS     : $(util_pretty_print ${COMMANDS[@]})"
    echo "please fix the script before running it again"
    exit 1
fi

if [[ -z "$1" ]]; then
    echo "usage: $0 <num_entries>"
    exit 1
elif [[ ! "$1" =~ ^[0-9]+$ ]]; then
    echo "error: $1 is not a number"
    exit 1
fi

loop_count=$(( ${#TEST_COMMANDS[@]} < ${#COMMANDS[@]} ? ${#TEST_COMMANDS[@]} - 1 : ${#COMMANDS[@]} - 1 ))
for i in `seq 0 $loop_count`; do
    echo -n "checking for ${TEST_COMMANDS[$i]}... "
    if command -v "${TEST_COMMANDS[$i]}" &> /dev/null; then
        echo "[command exists]"
        echo "processing..."
        func="${COMMANDS[$i]}"
        $func $1
        exit 0
    else
        echo "[command not exists]"
    fi
done

echo "error: no matching package manager found!"
echo -e "\tcurrenty only $(util_pretty_print ${TEST_COMMANDS[@]}) are supported"
echo -e "\tyou can add support for your package manager by editing the script"

exit 1
