#!/bin/bash
# vim: sts=4 sw=4 et
set -e
set -x
cd $(dirname "$0")

if [[ "$#" -ge 1 ]]; then
    git remote update
    git checkout -qf $1
    exec "$0"
else
    PARENT="$(readlink -f ..)"
    ENV_DIR=$(mktemp -d -p "$PARENT" env.XXXXXXXXXX)
    PYTHON3="$(which python3)"

    mkvirtualenv --python="$PYTHON3" "$ENV_DIR"

    $ENV_DIR/bin/pip install --upgrade pip wheel
    $ENV_DIR/bin/pip install -r requirements.txt
    $ENV_DIR/bin/python -m textblob.download_corpora

    ln -s --force $ENV_DIR $PARENT/env
    sudo systemctl restart fewerror-twitter
fi
