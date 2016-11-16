#!/usr/bin/env python3
import argparse
import sys
import json


skip_keys = frozenset(('QUOTE', 'SPACE', '00-SOURCE'))


def fmap(f, val):
    if isinstance(val, list):
        return [fmap(f, x) for x in val]
    else:
        return f(val)


def space(val):
    return val.replace(' ', '#SPACE#')


def transform(j):
    return {
        k: v if k in skip_keys else fmap(space, v)
        for k, v in j.items()
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument('source', nargs='?', type=argparse.FileType(mode='r'), default=sys.stdin)
    a = p.parse_args()

    j = json.load(fp=a.source)
    j_ = transform(j)
    json.dump(j_, sys.stdout, indent=2, sort_keys=True)


if __name__ == '__main__':
    main()
