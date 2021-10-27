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


from dataclasses import dataclass
from typing import Optional

from rfmt.blocks import LineBlock as LB
from rfmt.blocks import TextBlock as TB

from .node import SQLNode, SQLNodeList

from .ident import SQLIdentifierPath
from .ident import SQLIdentifier


@dataclass(frozen=True)
class SQLAlias(SQLNode):
    alias: SQLIdentifier

    def sqlf(self, compact):
        return LB([TB('AS '), self.alias.sqlf(True)])

    @staticmethod
    def consume(lex) -> 'Optional[SQLAlias]':
        if lex.consume('AS'):
            return SQLAlias(SQLIdentifier.parse(lex))
        alias = SQLIdentifier.consume(lex)
        if not alias:
            return None
        return SQLAlias(alias)


@dataclass(frozen=False)
class SQLTableSource(SQLNode):

    @staticmethod
    def parse(lex) -> 'SQLTableSource':
        from .query_impl import SQLSubSelect
        from .expr_funcs import SQLFuncExpr

        if lex.consume('UNNEST'):
            lex.expect('(')
            name = SQLIdentifier('UNNEST')
            arg = SQLFuncExpr.parse(lex) or SQLIdentifierPath.parse(lex) 
            lex.expect(')')
            alias = SQLAlias.consume(lex)
            expr = SQLFuncExpr(SQLNodeList([name]), SQLNodeList([arg]))
            return SQLFunctionTable(expr, alias)
        
        if lex.consume('('):
            table = SQLQuery.parse(lex)
            lex.expect(')')
            alias = SQLAlias.consume(lex)
            return SQLSubSelect(table, alias)

        # Named Table (read-context)
        return SQLNamedTable.parse(lex, False)


@dataclass(frozen=False)
class SQLNamedTable(SQLTableSource):
    table: SQLIdentifierPath
    alias: Optional[SQLAlias] = None
    is_write: bool = False

    def sqlf(self, compact):
        expr = self.table.sqlf(compact)
        if self.alias is not None:
            expr = LB(
                [expr, TB(' '), self.alias.sqlf(True)])
        return expr

    @staticmethod
    def parse(lex, is_write=False) -> 'SQLNamedTable':
        table_name = SQLIdentifierPath.parse(lex)
        alias = SQLAlias.consume(lex)
        return SQLNamedTable(table_name, alias, is_write)

    @staticmethod
    def parse_no_alias(lex, is_write=False) -> 'SQLNamedTable':
        table_name = SQLIdentifierPath.parse(lex)
        return SQLNamedTable(table_name, None, is_write)


@dataclass(frozen=True)
class SQLQuery(SQLTableSource):

    @staticmethod
    def parse(lex) -> 'SQLQuery':
        from .query_impl import SQLWithSelect
        return SQLWithSelect.parse(lex)

    @staticmethod
    def consume(lex) -> 'Optional[SQLQuery]':
        from .query_impl import SQLWithSelect
        return SQLWithSelect.consume(lex)

@dataclass(frozen=True)
class SQLFunctionTable(SQLTableSource):
    from .expr import SQLExpr

    expr: SQLExpr
    alias: Optional[SQLAlias] = None
    is_write: bool = False

    def sqlf(self, compact):
        expr = self.expr.sqlf(compact)
        if self.alias is not None:
            expr = LB(
                [expr, TB(' '), self.alias.sqlf(True)])
        return expr