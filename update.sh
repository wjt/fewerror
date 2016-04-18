#!/bin/sh
set -e
set -x
cd $(dirname "$0")
git remote update
git checkout -qf $1
../env/bin/pip install -r requirements.txt
sudo systemctl restart fewerror-twitter fewerror-telegram
