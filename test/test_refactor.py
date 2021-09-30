import unittest
from sql_refactor.refactor import Refactor
from sql_parser import parse

class TestRefactor(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(TestRefactor, self).__init__(*args, **kwargs)

        knowledge = {
                        'table_a':
                        {
                            'new_table' : 'new_table_a',
                            'column_knowledge':
                            {
                                'column_1' : 'new_column_1',
                                'column_2' : 'new_column_2',
                                'column_3' : 'new_column_3',
                            }
                        }
                    }
        

        self.command = Refactor(knowledge)

    def _assert_equal_sql(self, sql, reference):
        self.command.refactor(sql)
        refactored = self.command.result()
        refactored = refactored.replace('`', '')

        reference_parsed = parse(reference)
        reference = reference_parsed.as_sql(False)

        return self.assertEqual(refactored, reference)

    def test_simple_select(self):
        sql = """
        SELECT column_1, column_2
        FROM table_a
        """

        reference = """
        SELECT new_column_1 AS column_1, new_column_2 AS column_2
        FROM new_table_a
        """

        self._assert_equal_sql(sql, reference)

    def test_select_where(self):
        sql = """
        SELECT column_1, column_2
        FROM table_a
        WHERE column_1 = 1
        """

        reference = """
        SELECT new_column_1 AS column_1, new_column_2 AS column_2
        FROM new_table_a
        WHERE new_column_1 = 1
        """

        self._assert_equal_sql(sql, reference)

    def test_column_not_found(self):
        sql = """
        SELECT column_1, column_0
        FROM table_a
        """

        reference = """
        SELECT 
            new_column_1 AS column_1, 
            -- [WARNING] Could not find column in knowledge: column_0
            column_0
        FROM new_table_a
        """

        self._assert_equal_sql(sql, reference)

    def test_table_not_found(self):
        sql = """
        SELECT column_1
        FROM table_x
        """

        reference = """
        -- [WARNING] Could not find table in knowledge: table_x
        SELECT
            column_1
        FROM table_x
        """

        self._assert_equal_sql(sql, reference)

    def test_field_function(self):
        sql = """
        SELECT 
        CAST(column_1 AS STRING) AS new_column_1, column_2
        FROM table_a
        WHERE 
        CAST(column_1 AS STRING) = "column_name"
        """

        reference = """
        SELECT
        CAST(new_column_1 AS STRING) AS new_column_1,
        new_column_2 AS column_2
        FROM
        `new_table_a`
        WHERE
        CAST(new_column_1 AS STRING) = 'column_name'
        """

        self._assert_equal_sql(sql, reference)
