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