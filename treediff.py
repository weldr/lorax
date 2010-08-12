#! /usr/bin/env python

import sys
import os


def main(src, dst, sort_by_size):
    if src.endswith("/"):
        src = src[:-1]
    if dst.endswith("/"):
        dst = dst[:-1]

    # parse the dst tree
    dst_tree = {}
    for root, dnames, fnames in os.walk(dst):
        root = root.replace(dst, "", 1)
        for fname in fnames:
            path = os.path.join(root, fname)
            try:
                dst_tree[fname].add(path)
            except KeyError:
                dst_tree[fname] = set()
                dst_tree[fname].add(path)

    # parse the src tree
    filelist = []
    for root, dnames, fnames in os.walk(src):
        root = root.replace(src, "", 1)
        for fname in fnames:
            path = os.path.join(root, fname)
            paths = dst_tree.get(fname)

            if not paths:
                # file not found
                try:
                    size = os.path.getsize(os.path.join(src, path[1:]))
                except OSError:
                    size = 0L
                filelist.append((size, path))
            else:
                # fname found
                if path in paths:
                    # exact match
                    continue
                else:
                    # partial match
                    # TODO
                    continue

    if sort_by_size:
        filelist.sort(reverse=True)

    for size, path in filelist:
        # convert size to human readable
        human = ""
        for base in ["KiB", "MiB", "GiB"]:
            size /= 1024
            if size < 1024:
                human = "{0:6.1f}{1}".format(size, base)
                break

        print("{0} {1}".format(human, path))


if __name__ == "__main__":
    try:
        src, dst = sys.argv[1], sys.argv[2]
    except IndexError:
        print("invalid arguments count")
        sys.exit(1)

    try:
        sort_by_size = sys.argv[3]
    except IndexError:
        sort_by_size = False

    main(src, dst, bool(sort_by_size))
