# SQL Refactor
This library contains a class, `Refactor`, for refactoring a SQL with a given knowledge of tables and column names mapping.

## Structur of the knowledge
The knowledge is a dictionary containing the mapping of `old_table`-`new_table` and corresponding `old_column`-`new_column`.

The structure of the knowledge:
```json
{
    "old_table_name":
    {
        "new_table": "new_table_name",
        "column_knowledge":
        {
            "column_1" : "new_column_1",
            "column_2" : "new_column_2",

        }
        "preserved" : boolean
    },
    .
    .
    .
}
```

## How to use

Code sample:
```py
from sql_refactor import Refactor

# refer to Structure of Knowledge
knowledge = KNOWLEDGE

refactor = Refactor(knowledge)
refactor.refactor('''SELECT column_1, column_2 FROM old_table_name''')

new_query = refactor.result()
```

Result:
```sql
SELECT
  new_column_1 AS column_1,
  new_column_2 AS column_2
FROM
  `new_table_name`
```
