#!/bin/bash
# vim: sts=4 sw=4 et
set -e
set -x
cd $(dirname "$0")

if [[ "$#" -gt 1 ]]; then
    git remote update
    git checkout -qf $1
fi

../env/bin/pip install --upgrade pip wheel
../env/bin/pip install -r requirements.txt
../env/bin/python -m textblob.download_corpora

sudo systemctl restart fewerror-twitter fewerror-telegram
