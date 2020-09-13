# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
#     Unless required by applicable law or agreed to in writing, software
#     distributed under the License is distributed on an "AS IS" BASIS,
#     WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#     See the License for the specific language governing permissions and
#     limitations under the License.
#


from collections import namedtuple

from sql_parser.node import SQLNode
from sql_parser.query import SQLNamedTable
from sql_parser.query_impl import SQLWithSelect
from sql_parser.parser import SQLScript

from .graph import minimise_graph


class TableDependency(namedtuple('TableDependency', ['dest', 'src'])):
    pass


class TableOperation(namedtuple('TableOperation', ['table', 'is_write'])):
    pass


def tables(expr):
    ops = set()

    if isinstance(expr, SQLNamedTable):
        ops.add(TableOperation(str(expr.table), expr.is_write))
        return ops

    if isinstance(expr, SQLWithSelect):
        ops.update(tables(expr.select))
        ops.difference_update(expr.tables)
        return ops

    if isinstance(expr, SQLScript):
        for cmd in expr.commands:
            dest = set()
            src = set()
            for table_op in tables(cmd):
                if table_op.is_write:
                    dest.add(table_op.table)
                else:
                    src.add(table_op.table)
            if dest or src:
                ops.add(TableDependency(tuple(dest), tuple(src)))
        return ops

    if isinstance(expr, SQLNode):
        for _, child in expr.children():
            ops.update(tables(child))

    return ops


def tables_to_graph(ops, minimise=True):

    # Convert to a graph
    dgraph = dict()
    for cmd in ops:
        for dest in cmd.dest:
            if dest not in dgraph:
                dgraph[dest] = set()
            for src in cmd.src:
                if src != dest:
                    dgraph[dest].add(src)

    if minimise:
        dgraph = minimise_graph(dgraph)

    return dgraph
