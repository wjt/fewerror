import collections
import collections.abc
import errno
import os


def reverse_inits(xs):
    for i in range(len(xs), 0, -1):
        yield xs[:i]


class OrderedSet(collections.abc.MutableSet):
    def __init__(self, it=()):
        super(OrderedSet, self).__init__()

        self._map = collections.OrderedDict((x, None) for x in it)

    def __contains__(self, elem):
        return elem in self._map

    def __iter__(self):
        yield from self._map

    def __len__(self):
        return len(self._map)

    def add(self, elem):
        self._map[elem] = None

    def discard(self, elem):
        self._map.pop(elem, None)

    def __repr__(self):
        return '{}(({}))'.format(
            self.__class__.__name__,
            ', '.join(map(repr, self)))

    def __str__(self):
        return '{' + ', '.join(map(str, self)) + '}'


def mkdir_p(path):
    # how many times must I write this function?
    try:
        os.makedirs(path)
    except OSError as e:
        if e.errno != errno.EEXIST or not os.path.isdir(path):
            raise
