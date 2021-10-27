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
from rfmt.blocks import StackBlock as SB
from rfmt.blocks import ChoiceBlock as CB
from rfmt.blocks import WrapBlock as WB
from sql_parser.query_impl import SQLField

from .utils import with_commas

from .ident import SQLIdentifier, SQLIdentifierPath

from .query import SQLQuery
from .node import SQLNodeList
from .node import SQLNode
from .const import SQLConstant, SQLNumber, SQLString
from .types import SQLType
from .expr import SQLExpr


@dataclass(frozen=True)
class SQLFuncExpr(SQLExpr):
    names: SQLNodeList[SQLIdentifier]
    args: SQLNodeList[SQLExpr]

    def sqlf(self, compact):
        name = LB([x.sqlf(True) for x in self.names])
        compact_sql = LB([name, TB('(')] +
                         with_commas(True, self.args) +
                         [TB(')')])

        if compact:
            return compact_sql

        if not self.args:
            return compact_sql

        return CB([
            compact_sql,
            LB([
                LB([name, TB('(')]),
                WB(with_commas(False, self.args)),
                TB(')')
            ])
        ])


@dataclass(frozen=True)
class SQLCustomFuncs(SQLExpr):

    @staticmethod
    def consume(lex) -> 'Optional[SQLCustomFuncs]':
        # TODO(scannell) - add DATE, TIME, DATETIME, TIMESTAMP literals
        return (SQLCAST.consume(lex) or
                SQLDate.consume(lex) or
                SQLTime.consume(lex) or
                SQLCount.consume(lex) or
                SQLExists.consume(lex) or
                SQLInterval.consume(lex) or
                SQLAnalyticNavigation.consume(lex) or
                SQLExtract.consume(lex) or
                SQLCoalesce.consume(lex) or
                SQLApproxQuantiles.consume(lex) or
                SQLStructFunction.consume(lex))


@dataclass(frozen=True)
class SQLExists(SQLCustomFuncs):
    sql: SQLNode

    def sqlf(self, compact):
        return LB([
            TB('EXISTS('),
            self.sql.sqlf(True),
            TB(')'),
        ])

    @staticmethod
    def consume(lex) -> 'Optional[SQLExists]':
        if not lex.consume('EXISTS'):
            return None

        lex.expect('(')
        query = SQLQuery.parse(lex)
        lex.expect(')')

        return SQLExists(query)


@dataclass(frozen=True)
class SQLCount(SQLCustomFuncs):
    isdistinct: bool
    expr: SQLExpr

    def sqlf(self, compact):
        return LB([
            TB('COUNT(' + ('DISTINCT ' if self.isdistinct else '')),
            self.expr.sqlf(compact),
            TB(')'),
        ])

    @staticmethod
    def consume(lex) -> 'Optional[SQLCount]':
        if not lex.consume('COUNT'):
            return None
        lex.expect('(')
        isdistinct = bool(lex.consume('DISTINCT'))
        expr = SQLExpr.parse(lex)
        lex.expect(')')
        return SQLCount(isdistinct, expr)


@dataclass(frozen=True)
class SQLInterval(SQLCustomFuncs):
    sql_node: SQLNode

    def sqlf(self, compact):
        return LB([
            TB('INTERVAL('),
            self.sql_node.sqlf(compact),
            TB(')'),
        ])

    @staticmethod
    def consume(lex) -> 'Optional[SQLInterval]':
        if not lex.consume('INTERVAL'):
            return None

        if lex.consume('('):
            sql_node = (SQLString.consume(lex) or
                        lex.error('expected string'))
            lex.expect(')')
        else:
            sql_node = (SQLString.consume(lex) or
                        lex.error('expected string'))

        return SQLInterval(sql_node)


@dataclass(frozen=True)
class SQLExtract(SQLCustomFuncs):
    name: str
    part: SQLIdentifier
    expr: SQLExpr
    timezone: Optional[SQLConstant]

    def sqlf(self, compact):
        if self.timezone:
            return LB([
                TB(self.name), TB('('), self.part.sqlf(compact),
                TB(' '), TB('FROM'), TB(' '),
                self.expr.sqlf(compact),
                TB(' '), TB('AT'), TB(' '), TB('TIME'), TB(' '), TB('ZONE'), TB(' '),
                self.timezone.sqlf(compact),
                TB(')')
            ])
        else:
            return LB([
                TB(self.name), TB('('), self.part.sqlf(compact),
                TB(' '), TB('FROM'), TB(' '),
                self.expr.sqlf(compact), TB(')')
            ])

    @staticmethod
    def consume(lex) -> 'Optional[SQLExtract]':
        if not lex.consume('EXTRACT'):
            return None
        lex.expect('(')
        daypart = SQLIdentifier.parse(lex)
        lex.expect('FROM')
        date_expr = SQLExpr.parse(lex)
        timezone = None
        if lex.consume('AT'):
            lex.expect('TIME ZONE')
            timezone = SQLString.parse(lex)
        lex.expect(')')

        return SQLExtract('EXTRACT', daypart, date_expr, timezone)


@dataclass(frozen=True)
class SQLCAST(SQLCustomFuncs):
    name: str
    expr: SQLExpr
    type: SQLType

    def sqlf(self, compact):
        return LB([
            TB(self.name), TB('('), self.expr.sqlf(compact),
            TB(' '), TB('AS'), TB(' '),
            self.type.sqlf(compact), TB(')')
        ])

    @staticmethod
    def consume(lex) -> 'Optional[SQLCAST]':
        name = None
        if lex.consume('CAST'):
            name = 'CAST'
        elif lex.consume('SAFE_CAST'):
            name = 'SAFE_CAST'
        else:
            return None
        lex.expect('(')
        value_expr = SQLExpr.parse(lex)
        lex.expect('AS')
        new_type = SQLType.parse(lex)
        lex.expect(')')
        return SQLCAST(name, value_expr, new_type)


@dataclass(frozen=True)
class SQLAnalyticNavigation(SQLCustomFuncs):
    name: str
    args: SQLNodeList
    opt: str

    def sqlf(self, compact):
        if len(self.args) == 1:
            return LB([
                TB(self.name + '('),
                self.args[0].sqlf(compact),
                TB(self.opt + ')')
            ])

        return LB([
            TB(self.name + '('),
            self.args[0].sqlf(compact),
            TB(', '),
            self.args[1].sqlf(compact),
            TB(self.opt + ')')
        ])

    @staticmethod
    def consume(lex) -> 'Optional[SQLAnalyticNavigation]':
        name = (lex.consume('FIRST_VALUE') or
                lex.consume('LAST_VALUE') or
                lex.consume('NTH_VALUE') or
                lex.consume('PERCENTILE_COUNT') or
                lex.consume('PERCENTILE_DISC'))
        if not name:
            return None

        lex.expect('(')

        args = []
        while True:
            args.append(SQLExpr.parse(lex))
            if not lex.consume(','):
                break

        opt = (lex.consume('RESPECT') or
               lex.consume('IGNORE'))
        if opt:
            lex.expect('NULLS')
            opt = ' ' + opt + ' NULLS'
        elif lex.consume('NULLS'):
            opt = ' NULLS'
        else:
            opt = ''

        lex.expect(')')

        return SQLAnalyticNavigation(name, SQLNodeList(args), opt)


@dataclass(frozen=True)
class SQLDate(SQLCustomFuncs):
    name: str
    args: SQLNodeList

    def sqlf(self, compact):
        return LB([
            TB(self.name), TB('('), self.args[0].sqlf(True),
            TB(', '), TB('INTERVAL'), TB(' '),
            self.args[1].sqlf(True), TB(' '), self.args[2].sqlf(True),
            TB(')')
        ])

    @staticmethod
    def consume(lex) -> 'Optional[SQLDate]':
        name = lex.consume('DATE_ADD') or lex.consume('DATE_SUB')
        if not name:
            return None
        lex.expect('(')
        date_expr = SQLExpr.parse(lex)
        lex.expect(',')
        lex.expect('INTERVAL')
        count = SQLExpr.parse(lex)
        date_part = SQLIdentifier.parse(lex)
        lex.expect(')')
        return SQLDate(name, SQLNodeList((date_expr, count, date_part)))


@dataclass(frozen=True)
class SQLTime(SQLCustomFuncs):
    name: str
    args: SQLNodeList

    def sqlf(self, compact):
        return LB([
            TB(self.name), TB('('), self.args[0].sqlf(True),
            TB(', '), TB('INTERVAL'), TB(' '),
            self.args[1].sqlf(True), TB(' '), self.args[2].sqlf(True),
            TB(')')
        ])

    @staticmethod
    def consume(lex) -> 'Optional[SQLTime]':
        name = lex.consume('TIME_ADD') or lex.consume('TIME_SUB')  or lex.consume('TIMESTAMP_ADD')  or lex.consume('TIMESTAMP_SUB')
        if not name:
            return None
        lex.expect('(')
        date_expr = SQLExpr.parse(lex)
        lex.expect(',')
        lex.expect('INTERVAL')
        count = SQLExpr.parse(lex)
        date_part = SQLIdentifier.parse(lex)
        lex.expect(')')
        return SQLTime(name, SQLNodeList((date_expr, count, date_part)))


@dataclass(frozen=True)
class SQLCoalesce(SQLCustomFuncs):
    expr: SQLNodeList[SQLNode]

    def sqlf(self, compact):
        return LB([
            TB('COALESCE('),
            LB(with_commas(compact, self.expr)),
            TB(')'),
        ])

    @staticmethod
    def consume(lex) -> 'Optional[SQLCoalesce]':
        if not lex.consume('COALESCE'):
            return None
        lex.expect('(')

        expr = []
        while True:
            expr.append(SQLConstant.parse(lex) or SQLIdentifierPath.parse(lex))
            if not lex.consume(','):
                break
        lex.expect(')')

        expr = SQLNodeList(expr)
        return SQLCoalesce(expr)


@dataclass(frozen=True)
class SQLApproxQuantiles(SQLCustomFuncs):
    expr: SQLNode
    number: int
    offset: Optional[int]

    def sqlf(self, compact):
        if self.offset:
            return LB([
                TB('APPROX_QUANTILES('),
                self.expr.sqlf(compact), TB(','), TB(' '),
                self.number.sqlf(compact),
                TB(')'),
                TB('[OFFSET('), TB(' '),
                self.offset.sqlf(compact),
                TB(')]')
            ])
        else:
            return LB([
                TB('APPROX_QUANTILES('),
                self.expr.sqlf(compact), TB(','), TB(' '),
                self.number.sqlf(compact),
                TB(')'),
            ])

    @staticmethod
    def consume(lex) -> 'Optional[SQLApproxQuantiles]':
        if not lex.consume('APPROX_QUANTILES'):
            return None
        lex.expect('(')

        expr = SQLIdentifierPath.parse(lex)

        lex.expect(',')
        number = SQLNumber.parse(lex)

        lex.expect(')')

        offset = None
        if lex.consume('['):
            lex.expect('OFFSET')
            lex.consume('(')
            offset = SQLNumber.parse(lex)
            lex.consume(')')
            lex.expect(']')

        return SQLApproxQuantiles(expr, number, offset)

@dataclass(frozen=True)
class SQLStructFunction(SQLCustomFuncs):
    expr: SQLNodeList[SQLNode]

    def sqlf(self, compact):
        return LB([
            TB('STRUCT('),
            SB(with_commas(compact, self.expr)),
            TB(')'),
        ])

    @staticmethod
    def consume(lex) -> 'Optional[SQLStructFunction]':
        if not lex.consume('STRUCT'):
            return None
            
        lex.expect('(')
        expr = []
        while True:
            expr.append(SQLField.parse(lex))
            if not lex.consume(','):
                break
        lex.expect(')')

        expr = SQLNodeList(expr)
        return SQLStructFunction(expr)
