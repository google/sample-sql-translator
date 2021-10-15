from sql_refactor import Refactor

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
            }

refactor = Refactor(knowledge)
refactor.refactor('''SELECT column_1, column_2 FROM table_a''')
new_query = refactor.result()
print(new_query)