import collections
import errno
import os


def iflatmap(f, ys):
    for y in ys:
        for x in f(y):
            yield x


def reverse_inits(xs):
    for i in range(len(xs), 0, -1):
        yield xs[:i]


class OrderedSet(collections.OrderedDict):
    def add(self, elem):
        self[elem] = None

    def remove(self, elem):
        del self[elem]

    def discard(self, elem):
        self.pop(elem, None)


def mkdir_p(path):
    # how many times must I write this function?
    try:
        os.makedirs(path)
    except OSError as e:
        if e.errno != errno.EEXIST or not os.path.isdir(path):
            raise
