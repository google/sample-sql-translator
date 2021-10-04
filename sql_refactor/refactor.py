from sql_parser.ident import SQLIdentifier, SQLIdentifierPath
from sql_parser.query import SQLAlias, SQLNamedTable
from sql_parser.node import SQLNode, SQLNodeList
from sql_parser.query_impl import SQLField, SQLFrom, SQLJoin, SQLSelect

from sql_parser import parse

import copy


class Refactor:

    COMMENT_COLUMN_NOT_FOUND = "[WARNING] Could not find column in knowledge: {}"
    COMMENT_TABLE_NOT_FOUND = "[WARNING] Could not find table in knowledge: {}"

    def __init__(self, knowledge:dict):
        self._knowledge = knowledge
        self.parsed = None

    def result(self):
        if self.parsed:
            return self.parsed.as_sql()

    def refactor(self, sql):
        self.parsed = parse(sql)
        self._refactor(self.parsed)

    def _refactor(self, parsed, tables=None):
        if isinstance(parsed, SQLSelect):
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
        elif isinstance(parsed, SQLNode):
            self._refactor_node(parsed, tables)

    def _refactor_select(self, parsed:SQLSelect):
        old_tables, not_found_tables = self._get_tables_and_alias(parsed.from_tables)
        
        for table in not_found_tables:
            parsed.comments.append(self.COMMENT_TABLE_NOT_FOUND.format(table))

        self._refactor(parsed.from_tables)
        
        for field in parsed.fields:
            self._refactor(field, old_tables)

        if parsed.where_expr is not None:
            self._refactor(parsed.where_expr, old_tables)
        
    def _refactor_from(self, parsed:SQLFrom):
        tables = {}
        if isinstance(parsed.base, SQLNamedTable):
            table_id = parsed.base.table.names[0].value
            alias = None if parsed.base.alias is None else parsed.base.alias.alias.value
            tables[table_id] = alias

        self._refactor(parsed.base)

        for join_item in parsed.joins:
            if isinstance(join_item.table, SQLNamedTable):
                table_id = join_item.table.table.names[0].value
                alias = None if join_item.table.alias is None else join_item.table.alias.alias.value
                tables[table_id] = alias

            self._refactor(join_item, tables)

    def _refactor_named_table(self, parsed:SQLNamedTable):
        table_id = parsed.table.names[-1].value
        if table_id in self._knowledge.keys():
            if not self._knowledge[table_id]['preserved']:
                table_id = self._knowledge[table_id]['new_table']
        parsed.table.names[-1].value = '`' + table_id + '`'

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
        new_column_name_path = column_knowledge[old_column_name].split('.')
        new_column_name_identifier_path = [SQLIdentifier(name) for name in new_column_name_path]
        parsed.names = SQLNodeList(new_column_name_identifier_path)

    def _refactor_node(self, parsed:SQLNode, tables:dict=None):
        for _, val in parsed.children():
            self._refactor(val, tables)

    def _get_tables_and_alias(self, from_tables:SQLFrom) -> dict:
        tables = {}
        not_found_tables = []

        if isinstance(from_tables.base, SQLNamedTable):
            table_id = from_tables.base.table.names[-1].value
            if table_id in self._knowledge.keys():
                tables[table_id] = None if from_tables.base.alias is None \
                                    else from_tables.base.alias.alias.value
            else:
                not_found_tables.append(table_id)
        
        for join_item in from_tables.joins:
            if isinstance(join_item.table, SQLNamedTable):
                table_id = join_item.table.table.names[-1].value
                if table_id in self._knowledge.keys():
                    tables[table_id] = None if join_item.table.alias is None \
                                        else join_item.table.alias.alias.value
                else:
                    not_found_tables.append(table_id)
        
        not_found_tables = set(not_found_tables)
        return tables, not_found_tables

    def _get_column_knowledge(self, tables:dict):
        column_knowledge = {}
        for table, alias in tables.items():
            column_knowledge_from_table = copy.copy(self._knowledge[table]['column_knowledge'])
            if self._knowledge[table]['preserved']:
                column_knowledge_from_table = {
                                                old_column : old_column
                                                for old_column, _ in column_knowledge_from_table.items()
                                            }
            if alias:
                    column_knowledge_from_table = {
                                                    old_column : '{}.{}'.format(alias, new_column)
                                                    for old_column, new_column in column_knowledge_from_table.items()
                                                }
            column_knowledge.update(column_knowledge_from_table)
            
        return column_knowledge
