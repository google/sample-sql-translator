from sql_parser import query
from sql_parser.dml import SQLCreate
from sql_parser.ident import SQLIdentifier, SQLIdentifierPath, SQLWildcardPath
from sql_parser.query import SQLAlias, SQLNamedTable
from sql_parser.node import SQLNode, SQLNodeList
from sql_parser.query_impl import SQLField, SQLFrom, SQLJoin, SQLOrderedQuery, SQLSelect, SQLSetOp, SQLSubSelect, SQLWithSelect

from sql_parser import parse

import copy


class Refactor:

    COMMENT_COLUMN_NOT_FOUND = "[WARNING] Could not find column in knowledge: {}"
    COMMENT_TABLE_NOT_FOUND = "[WARNING] Could not find table in knowledge: {}"

    def __init__(self, knowledge:dict):
        self._knowledge = knowledge
        self.parsed = []

    def result(self):
        if self.parsed:
            sql = ""
            for parsed in self.parsed[:-1]:
                sql += '{}\n;\n\n'.format(parsed.as_sql())
            sql += self.parsed[-1].as_sql()
            return sql

    def refactor(self, sql, parse_only=False):
        self.parsed = []
        sql_commands = sql.strip('\n').split(';')
        for command in sql_commands:
            if command in ('', '\n'):
                continue
            parsed = parse(command)
            self.parsed.append(parsed)
            if not parse_only:
                self._refactor(parsed)

    def _refactor(self, parsed, tables=None):
        if isinstance(parsed, SQLWithSelect):
            self._refactor_with_select(parsed)
        elif isinstance(parsed, SQLSelect):
            self._refactor_select(parsed)
        elif isinstance(parsed, SQLFrom):
            self._refactor_from(parsed)
        elif isinstance(parsed, SQLNamedTable):
            self._refactor_named_table(parsed)
        elif isinstance(parsed, SQLJoin):
            self._refactor_join(parsed, tables)
        elif isinstance(parsed, SQLField):
            self._refactor_field(parsed, tables)
        elif isinstance(parsed, SQLIdentifierPath):
            self._refactor_identifier_path(parsed, tables)
        elif isinstance(parsed, SQLCreate):
            self._refactor_create(parsed)
        elif isinstance(parsed, SQLSetOp):
            if parsed.op in ('UNION', 'UNION ALL'):
                self._refactor_union(parsed)
            else:
                self._refactor_node(parsed, tables)
        elif isinstance(parsed, SQLNode):
            self._refactor_node(parsed, tables)

    def _refactor_with_select(self, parsed:SQLWithSelect):
        cte_tables = [table.value for table in parsed.tables]
        for i, cte in enumerate(parsed.sqls):
            self._refactor(cte)

            # Add CTE into current knowledge
            column_knowledge = {}

            if isinstance(cte.select, SQLSetOp) and cte.select.op in ('UNION', 'UNION ALL'):
                select_statement = cte.select.left
            elif isinstance(cte.select, SQLOrderedQuery):
                select_statement = cte.select.query
            else:
                select_statement = cte.select

            for field in select_statement.fields:
                if isinstance(field.expr, SQLWildcardPath):
                    continue
                if field.alias:
                    column_knowledge[field.alias.alias.value] = None
                else:
                    column_knowledge[field.expr.names[-1].value] = None
            self._knowledge[cte_tables[i]] = {
                'new_table' : None,
                'column_knowledge' : column_knowledge,
                'preserved' : True
            }

        self._refactor(parsed.select)

        # delete unused cte knowledge
        for cte_table in cte_tables:
            self._knowledge.pop(cte_table)


    def _refactor_select(self, parsed:SQLSelect):
        old_tables, not_found_tables = self._get_tables_and_alias(parsed.from_tables)
        
        for table in not_found_tables:
            parsed.comments.append(self.COMMENT_TABLE_NOT_FOUND.format(table))

        self._refactor(parsed.from_tables)
        
        index = 0
        while True:
            if index == len(parsed.fields):
                break
            field = parsed.fields[index]
            
            # Wildcard
            if isinstance(field.expr, SQLWildcardPath):
                if len(old_tables) == 1 or len(field.expr.names) == 0:
                    column_knowledge = self._get_column_knowledge(old_tables)
                    if len(column_knowledge) == 0:
                        index += 1
                        continue
                    # Omit columns in EXCEPT
                    except_ids = [column_id.value for column_id in field.expr.except_ids]
                    column_names = []
                    for id in column_knowledge.keys():
                        if id not in except_ids:
                            column_names.append(id)
                    
                    columns = [ 
                                SQLField(
                                    SQLIdentifierPath(
                                        SQLNodeList([SQLIdentifier(column_name)])
                                    ), None, []
                                )
                                for column_name in column_names
                            ]
                else:
                    table_alias = field.expr.names[0].value
                    table = None
                    for t, a in old_tables.items():
                        if a == table_alias:
                            table = t
                            break
                    column_knowledge = self._get_column_knowledge({table: table_alias})
                    
                    if len(column_knowledge) == 0:
                        index += 1
                        continue

                    # Omit columns in EXCEPT
                    except_ids = [column_id.value for column_id in field.expr.except_ids]
                    column_names = []
                    for id in column_knowledge.keys():
                        if id not in except_ids:
                            column_names.append(id)

                    columns = [ SQLField(
                                    SQLIdentifierPath(SQLNodeList(
                                        [SQLIdentifier(table_alias), SQLIdentifier(column_name)])
                                    ), None, []
                                )
                                for column_name in column_names
                            ]
                
                # Insert new column list from wildcard to fields
                if index == 0:
                    parsed.fields = SQLNodeList(columns) + parsed.fields[index+1:]
                else:
                    parsed.fields = parsed.fields[:index] + SQLNodeList(columns) + parsed.fields[index+1:]
                field = parsed.fields[index]

            # Identifier Path
            self._refactor(field, old_tables)
            
            index += 1

        if parsed.where_expr is not None:
            self._refactor(parsed.where_expr, old_tables)
        
    def _refactor_from(self, parsed:SQLFrom):
        if parsed is None:
            return

        tables = {}
        if isinstance(parsed.base, SQLNamedTable):
            table_id = parsed.base.table.names[0].value
            alias = None if parsed.base.alias is None else parsed.base.alias.alias.value
            tables[table_id] = alias
            self._refactor(parsed.base)
        elif isinstance(parsed.base, SQLSubSelect):
            sub_select = parsed.base
            self._refactor(sub_select)
            if sub_select.alias:
                table_alias = sub_select.alias.alias.value
                table_name = table_alias
            else:
                table_alias = '*base'
                table_name = ''
            
            # Collect column knowledge
            column_knowledge = {}

            if isinstance(sub_select.query.select, SQLSetOp) and sub_select.query.select.op in ('UNION', 'UNION ALL'):
                select_statement = sub_select.query.select.left
            elif isinstance(sub_select.query.select, SQLOrderedQuery):
                select_statement = sub_select.query.select.query
            else:
                select_statement = sub_select.query.select

            for field in select_statement.fields:
                if field.alias:
                    column_knowledge[field.alias.alias.value] = None
                else:
                    column_knowledge[field.expr.names[-1].value] = None
            additional_knowledge = {
                table_name : {
                    'new_table' : table_name,
                    'column_knowledge' : column_knowledge,
                    'preserved' : True
                }
            }
            self._knowledge = dict(self._knowledge, **additional_knowledge)

        for join_item in parsed.joins:
            if isinstance(join_item.table, SQLNamedTable):
                table_id = join_item.table.table.names[0].value
                alias = None if join_item.table.alias is None else join_item.table.alias.alias.value
                tables[table_id] = alias
            elif isinstance(join_item.table, SQLSubSelect):
                sub_select = join_item.table
                self._refactor(sub_select, tables)
                if sub_select.alias:
                    table_alias = sub_select.alias.alias.value
                    table_name = table_alias
                else:
                    table_alias = '*base'
                    table_name = ''
                
                # Collect column knowledge
                column_knowledge = {}

                if isinstance(sub_select.query.select, SQLSetOp) and sub_select.query.select.op in ('UNION', 'UNION ALL'):
                    select_statement = sub_select.query.select.left
                elif isinstance(sub_select.query.select, SQLOrderedQuery):
                    select_statement = sub_select.query.select.query
                else:
                    select_statement = sub_select.query.select
                    
                for field in select_statement.fields:
                    if isinstance(field.expr, SQLWildcardPath):
                        continue
                    if field.alias:
                        column_knowledge[field.alias.alias.value] = None
                    else:
                        column_knowledge[field.expr.names[-1].value] = None
                additional_knowledge = {
                    table_name : {
                        'new_table' : table_name,
                        'column_knowledge' : column_knowledge,
                        'preserved' : True
                    }
                }
                self._knowledge = dict(self._knowledge, **additional_knowledge)
                tables[table_name] = table_alias
            self._refactor(join_item, tables)

    def _refactor_named_table(self, parsed:SQLNamedTable):
        table_id = parsed.table.names[-1].value
        if table_id in self._knowledge.keys():
            if not self._knowledge[table_id]['preserved']:
                table_id = self._knowledge[table_id]['new_table']
        parsed.table.names[-1].value = '`' + table_id.strip('`') + '`'

    def _refactor_field(self, parsed:SQLField, tables:dict):
        if isinstance(parsed.expr, SQLIdentifierPath):
            if len(tables) == 0: # no tables found in knowledge
                return

            first_name = parsed.expr.names[0].value
            relevant_tables = tables
            
            # check whether first_name is table's alias
            for table_id, alias in tables.items():
                if alias == first_name:
                    alias = alias if alias else table_id
                    relevant_tables = {table_id : alias}
                    break
            
            column_knowledge = self._get_column_knowledge(relevant_tables)

            old_column_name = parsed.expr.names[-1].value

            if old_column_name not in column_knowledge.keys():
                parsed.comments.append(self.COMMENT_COLUMN_NOT_FOUND.format(old_column_name))
                return
                
            new_column_name_path = column_knowledge[old_column_name].split('.')
            new_column_name = new_column_name_path[-1]
            new_column_name_identifier_path = [SQLIdentifier(name) for name in new_column_name_path]
            parsed.expr.names = SQLNodeList(new_column_name_identifier_path)

            # add alias for column
            if parsed.alias is None:
                if old_column_name != new_column_name:
                    parsed.alias = SQLAlias(SQLIdentifier(old_column_name))
            elif new_column_name == parsed.alias.alias.value:
                parsed.alias = None

        else:
            self._refactor(parsed.expr, tables)

    def _refactor_join(self, parsed:SQLJoin, tables:dict):
        if isinstance(parsed.table, SQLNamedTable):
            self._refactor(parsed.table)
        if parsed.join_expr:
            self._refactor(parsed.join_expr, tables)

    def _refactor_identifier_path(self, parsed:SQLIdentifierPath, tables):
        if tables is None:
            return
        
        first_name = parsed.names[0].value
        relevant_tables = tables

        # check whether first_name is table's alias
        for table_id, alias in tables.items():
            if alias == first_name:
                alias = alias if alias else table_id
                relevant_tables = {table_id : alias}
                break
        
        column_knowledge = self._get_column_knowledge(relevant_tables)
        old_column_name = parsed.names[-1].value
        if old_column_name not in column_knowledge.keys():
            return
        new_column_name_path = column_knowledge[old_column_name].split('.')
        new_column_name_identifier_path = [SQLIdentifier(name) for name in new_column_name_path]
        parsed.names = SQLNodeList(new_column_name_identifier_path)

    def _refactor_create(self, parsed:SQLCreate):
        self._refactor(parsed.query)

        # Add CTE into current knowledge
        cte_table = parsed.table.table.names[-1].value
        column_knowledge = {}

        select_statement = parsed.query.select
        while True:
            if isinstance(select_statement, SQLSelect):
                break
            if isinstance(select_statement, SQLSetOp) and select_statement.op in ('UNION', 'UNION ALL'):
                select_statement = select_statement.left
            elif isinstance(select_statement, SQLOrderedQuery):
                select_statement = select_statement.query
            elif isinstance(select_statement, SQLSubSelect):
                select_statement = select_statement.query.select
            else:
                break

        for field in select_statement.fields:
            if field.alias:
                column_knowledge[field.alias.alias.value] = None
            else:
                column_knowledge[field.expr.names[-1].value] = None
        self._knowledge[cte_table] = {
            'new_table' : None,
            'column_knowledge' : column_knowledge,
            'preserved' : True
        }

    def _refactor_union(self, parsed:SQLSetOp):
        self._refactor(parsed.left)
        self._refactor(parsed.right)

    def _refactor_node(self, parsed:SQLNode, tables:dict=None):
        for _, val in parsed.children():
            self._refactor(val, tables)

    def _get_tables_and_alias(self, from_tables:SQLFrom) -> dict:
        tables = {}
        not_found_tables = []

        if from_tables is None:
            return tables, not_found_tables
            
        if isinstance(from_tables.base, SQLNamedTable):
            table_id = from_tables.base.table.names[-1].value
            if table_id in self._knowledge.keys():
                tables[table_id] = None if from_tables.base.alias is None \
                                    else from_tables.base.alias.alias.value
            else:
                not_found_tables.append(table_id)
        elif isinstance(from_tables.base, SQLSubSelect):
            if from_tables.base.alias:
                table_id = from_tables.base.alias.alias.value
                table_alias = table_id
            else:
                table_id = ''
                table_alias = '*base'
            tables[table_id]  = table_alias

        for join_item in from_tables.joins:
            if isinstance(join_item.table, SQLNamedTable):
                table_id = join_item.table.table.names[-1].value
                if table_id in self._knowledge.keys():
                    tables[table_id] = None if join_item.table.alias is None \
                                        else join_item.table.alias.alias.value
                else:
                    not_found_tables.append(table_id)
            elif isinstance(join_item.table, SQLSubSelect):
                if join_item.table.alias:
                    table_id = join_item.table.alias.alias.value
                    table_alias = table_id
                else:
                    table_id = ''
                    table_alias = '*base'
                tables[table_id]  = table_id

        
        not_found_tables = set(not_found_tables)
        return tables, not_found_tables

    def _get_column_knowledge(self, tables:dict):
        column_knowledge = {}
        for table, alias in tables.items():
            if table not in self._knowledge.keys():
                continue
            column_knowledge_from_table = copy.copy(self._knowledge[table]['column_knowledge'])
            if self._knowledge[table]['preserved']:
                column_knowledge_from_table = {
                                                old_column : old_column
                                                for old_column, _ in column_knowledge_from_table.items()
                                            }
            if alias and alias[0] != '*':
                    column_knowledge_from_table = {
                                                    old_column : '{}.{}'.format(alias, new_column)
                                                    for old_column, new_column in column_knowledge_from_table.items()
                                                }
            column_knowledge.update(column_knowledge_from_table)
            
        return column_knowledge
