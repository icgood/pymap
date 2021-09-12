#!/bin/sh
# Check if the given file is newer than the pymap PID file. This can be used
# as a healthcheck to watch for updated certificate files.

check_file=$1
pid_file=${2:-/tmp/pymap.pid}

test -n "$check_file" || exit 0  # ignore if no file is given

stat -c "$check_file: %y" $check_file || exit 1
stat -c "$pid_file: %y" $pid_file || exit 1

test $check_file -ot $pid_file || exit 1
