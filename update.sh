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
    ENV_LINK=$PARENT/env
    ENV_DIR=$(mktemp -d -p "$PARENT" env.XXXXXXXXXX)
    PYTHON3="$(which python3)"

    virtualenv --python="$PYTHON3" "$ENV_DIR"

    $ENV_DIR/bin/pip install --upgrade pip wheel
    $ENV_DIR/bin/pip install -r requirements.txt
    $ENV_DIR/bin/python -m textblob.download_corpora

    OLD_ENV_DIR="$(readlink -f "$ENV_LINK")"
    ln -s -T --force "$ENV_DIR" "$ENV_LINK"
    rm -rf "$OLD_ENV_DIR"
    sudo systemctl restart fewerror-twitter
fi
