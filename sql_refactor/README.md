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

## Limitation
This repo is under development which contains some limitations.

Limitations of the `sql_parser`:
1. `MERGE` statement is not supported yet
1. `CREATE [TEMPORARY] FUNCTION` is not supported yet
1. Function call without `()` is not supported.
   
   For instance: `TIMESTAMP '2021-01-01'` can not be parsed, expected `TIMESTAMP('2021-01-01')`
1. `DECLARE` statement is not supported yet

Limitations of the `sql_refactor`:
1. Has been tested on non-scripting SQL, and it works fine.
1. For the scripting SQL, only works if the query only contains `CREATE TEMP TABLE` + main select