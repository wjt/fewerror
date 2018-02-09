#!/bin/bash
# vim: sts=4 sw=4 et
set -e
set -x
cd $(dirname "$0")
PARENT="$(readlink -f ..)"

if [[ "$#" -ge 1 ]]; then
    git remote update
    git checkout -qf $1
    exec flock $PARENT/update.lock "$0"
else
    pipenv install
    pipenv run python -m textblob.download_corpora
    #sudo systemctl restart fewerror-twitter
fi
