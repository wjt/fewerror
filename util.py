import collections
from six.moves import range


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
