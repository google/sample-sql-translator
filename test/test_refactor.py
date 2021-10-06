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
                            },
                            'preserved' : False
                        },
                        'table_b':
                        {
                            'new_table' : 'new_table_b',
                            'column_knowledge':
                            {
                                'column_1' : 'new_column_1b',
                                'column_2b' : 'new_column_2b',
                            },
                            'preserved' : False
                        },
                        'table_c':
                        {
                            'new_table' : 'new_table_c',
                            'column_knowledge':
                            {
                                'column_1c' : 'new_column_1c',
                            },
                            'preserved' : False
                        },
                        'table_d':
                        {
                            'new_table' : None,
                            'column_knowledge': 
                            {
                                'column_1' : None,
                                'column_2' : None,
                            },
                            'preserved' : True
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

    def test_join(self):
        # LEFT JOIN ON
        sql = """
        SELECT 
        CAST(a.column_1 AS STRING) AS new_column_1,
        column_2,
        b.column_1 AS column_1b,
        column_2b,
        FROM table_a AS a
        LEFT JOIN table_b AS b ON a.column_1 = b.column_1
        WHERE 
        CAST(b.column_1 AS STRING) = "column_name"
        """

        reference = """
        SELECT 
        CAST(a.new_column_1 AS STRING) AS new_column_1,
        a.new_column_2 AS column_2,
        b.new_column_1b AS column_1b,
        b.new_column_2b AS column_2b,
        FROM new_table_a AS a
        LEFT JOIN new_table_b AS b ON a.new_column_1 = b.new_column_1b
        WHERE 
        CAST(b.new_column_1b AS STRING) = 'column_name'
        """

        self._assert_equal_sql(sql, reference)

        # CROSS JOIN
        sql = """
        SELECT 
        column_1, column_1c
        FROM table_a, table_c
        WHERE 
        CAST(column_1 AS STRING) = "column_name"
        """

        reference = """
        SELECT 
        new_column_1 AS column_1,
        new_column_1c AS column_1c
        FROM new_table_a, new_table_c
        WHERE 
        CAST(new_column_1 AS STRING) = "column_name"
        """

        self._assert_equal_sql(sql, reference)

        # LEFT JOIN USING
        sql = """
        SELECT 
        CAST(a.column_1 AS STRING) AS new_column_1,
        column_2,
        b.column_1 AS column_1b,
        column_2b,
        FROM table_a AS a
        LEFT JOIN table_b AS b USING(column_1)
        WHERE 
        CAST(b.column_1 AS STRING) = "column_name"
        """

        reference = """
        SELECT 
        CAST(a.new_column_1 AS STRING) AS new_column_1,
        a.new_column_2 AS column_2,
        b.new_column_1b AS column_1b,
        b.new_column_2b AS column_2b,
        FROM new_table_a AS a
        LEFT JOIN new_table_b AS b ON a.new_column_1 = b.new_column_1b
        WHERE 
        CAST(b.new_column_1b AS STRING) = 'column_name'
        """

        self._assert_equal_sql(sql, reference)

    def test_preserved(self):
        sql = """
        SELECT column_1, column_2
        FROM table_d
        """

        reference = """
        SELECT column_1, column_2
        FROM table_d
        """

        self._assert_equal_sql(sql, reference)

    def test_with(self):
        sql = """
        WITH cte_a AS(
            SELECT column_1, column_2
            FROM table_a
        )
        SELECT column_1, column_2 FROM cte_a
        """

        reference = """
        WITH cte_a AS(
            SELECT new_column_1 AS column_1, new_column_2 AS column_2
            FROM new_table_a
        )
        SELECT column_1, column_2 FROM cte_a
        """

        self._assert_equal_sql(sql, reference)

        sql = """
        WITH cte_a AS(
            WITH cte_a AS(
                SELECT column_1 AS c1, column_2
                FROM table_a
            )
            SELECT c1 AS column_1, column_2
            FROM cte_a
        )
        SELECT column_1, column_2 FROM cte_a
        """

        reference = """
        WITH cte_a AS(
            WITH cte_a AS(
                SELECT new_column_1 AS c1, new_column_2 AS column_2
                FROM new_table_a
            )
            SELECT c1 AS column_1, column_2
            FROM cte_a
        )
        SELECT column_1, column_2 FROM cte_a
        """

        self._assert_equal_sql(sql, reference)
