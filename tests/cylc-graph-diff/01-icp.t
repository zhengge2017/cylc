#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2017 NIWA
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#-------------------------------------------------------------------------------
# Test for "cylc graph-diff SUITE1 SUITE2 -- ICP".
. "$(dirname "$0")/test_header"

set_test_number 3

init_suite "${TEST_NAME_BASE}-1" <<'__SUITE_RC__'
[cylc]
    UTC mode = True
[scheduling]
    [[dependencies]]
        [[[R1]]]
            graph = foo => bar
[runtime]
    [[foo, bar]]
        script = true
__SUITE_RC__
SUITE_NAME1="${SUITE_NAME}"
init_suite "${TEST_NAME_BASE}-2" <<'__SUITE_RC__'
[cylc]
    UTC mode = True
[scheduling]
    [[dependencies]]
        [[[R1]]]
            graph = food => barley
[runtime]
    [[food, barley]]
        script = true
__SUITE_RC__
SUITE_NAME2="${SUITE_NAME}"

run_fail "${TEST_NAME_BASE}" \
    cylc graph-diff "${SUITE_NAME1}" "${SUITE_NAME2}" --  '20200101T0000Z'
contains_ok "${TEST_NAME_BASE}.stdout" <<__OUT__
-edge "foo.20200101T0000Z" "bar.20200101T0000Z" solid
+edge "food.20200101T0000Z" "barley.20200101T0000Z" solid
 graph
-node "bar.20200101T0000Z" "bar\n20200101T0000Z" unfilled ellipse black
-node "foo.20200101T0000Z" "foo\n20200101T0000Z" unfilled ellipse black
+node "barley.20200101T0000Z" "barley\n20200101T0000Z" unfilled ellipse black
+node "food.20200101T0000Z" "food\n20200101T0000Z" unfilled ellipse black
__OUT__
cmp_ok "${TEST_NAME_BASE}.stderr" <'/dev/null'

purge_suite "${SUITE_NAME1}"
purge_suite "${SUITE_NAME2}"
exit