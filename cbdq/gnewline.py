#!/usr/bin/env python3
import argparse
import json
import re
import sys
import yaml


skip_keys = frozenset(('QUOTE', 'SPACE', '00-SOURCE'))
traceryish_rx = re.compile(r'#(\w+)(?:\.\w+)*#')


def fmap(f, val):
    if isinstance(val, list):
        return [fmap(f, x) for x in val]
    else:
        return f(val)


def space(val):
    return val.replace(' ', '#SPACE#')


def validate(j):
    used = {'origin'} | skip_keys
    for k, v in j.items():
        def _validate(val, k=k):
            for var in traceryish_rx.findall(val):
                if var not in j:
                    raise ValueError(k, val, var)
                used.add(var)
        fmap(_validate, v)

    unused = j.keys() - used
    if unused:
        raise ValueError(unused)


def transform(j):
    return {
        k: v if k in skip_keys else fmap(space, v)
        for k, v in j.items()
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument('source', type=argparse.FileType(mode='r'))
    p.add_argument('--verify', action='store_true')
    a = p.parse_args()

    j = yaml.load(a.source, Loader=yaml.CLoader)
    validate(j)
    j_ = transform(j)
    if a.verify:
        json.dumps(j_)
    else:
        json.dump(j_, sys.stdout, indent=2, sort_keys=True)


if __name__ == '__main__':
    main()
