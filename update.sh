#! /usr/bin/env sh

path="./index.html"

cd $(dirname $0)

test -n "$1" && {
    path="$1"
    test -d "$path" && {
        path="$path/index.html"
    }
}

python grep.py
python search.py "$path"

