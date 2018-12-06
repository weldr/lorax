#
# Copyright (C) 2018 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
def insort_left(a, x, key=None, lo=0, hi=None):
    """Insert item x in list a, and keep it sorted assuming a is sorted.

    :param a: sorted list
    :type a: list
    :param x: item to insert into the list
    :type x: object
    :param key: Function to use to compare items in the list
    :type key: function
    :returns: index where the item was inserted
    :rtype: int

    If x is already in a, insert it to the left of the leftmost x.
    Optional args lo (default 0) and hi (default len(a)) bound the
    slice of a to be searched.

    This is a modified version of bisect.insort_left that can use a
    function for the compare, and returns the index position where it
    was inserted.
    """
    if key is None:
        key = lambda i: i

    if lo < 0:
        raise ValueError('lo must be non-negative')
    if hi is None:
        hi = len(a)
    while lo < hi:
        mid = (lo+hi)//2
        if key(a[mid]) < key(x): lo = mid+1
        else: hi = mid
    a.insert(lo, x)
    return lo
