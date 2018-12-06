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
import unittest

from pylorax.api.bisect import insort_left


class BisectTest(unittest.TestCase):
    def test_insort_left_nokey(self):
        results = []
        for x in range(0, 10):
            insort_left(results, x)
        self.assertEqual(results, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9])

    def test_insort_left_key_strings(self):
        unsorted = ["Maggie", "Homer", "Bart", "Marge"]
        results = []
        for x in unsorted:
            insort_left(results, x, key=lambda p: p.lower())
        self.assertEqual(results, ["Bart", "Homer", "Maggie", "Marge"])

    def test_insort_left_key_dict(self):
        unsorted = [{"name":"Maggie"}, {"name":"Homer"}, {"name":"Bart"}, {"name":"Marge"}]
        results = []
        for x in unsorted:
            insort_left(results, x, key=lambda p: p["name"].lower())
        self.assertEqual(results, [{"name":"Bart"}, {"name":"Homer"}, {"name":"Maggie"}, {"name":"Marge"}])
