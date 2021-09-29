18d17
< from typing import List
27c26
< from .ident import SQLIdentifier, SQLIdentifierPath
---
> from .ident import SQLIdentifier
32c31
< from .const import SQLConstant, SQLString
---
> from .const import SQLString
43,44d41
<         for name in self.names:
<             name.value = name.value.upper()
78,80c75
<                 SQLExtract.consume(lex) or
<                 SQLCeiling.consume(lex) or
<                 SQLCoalesce.consume(lex))
---
>                 SQLExtract.consume(lex))
292,340d286
< 
< @dataclass(frozen=True)
< class SQLCeiling(SQLCustomFuncs):
<     expr: SQLExpr
< 
<     def sqlf(self, compact):
<         return LB([
<             TB('CEILING('),
<             self.expr.sqlf(compact),
<             TB(')'),
<         ])
< 
<     @staticmethod
<     def consume(lex) -> 'Optional[SQLCeiling]':
<         if not lex.consume('CEILING'):
<             return None
<         lex.expect('(')
<         expr = SQLExpr.parse(lex)
<         lex.expect(')')
<         return SQLCeiling(expr)
< 
< 
< @dataclass(frozen=True)
< class SQLCoalesce(SQLCustomFuncs):
<     expr: SQLNodeList[SQLNode]
< 
<     def sqlf(self, compact):
<         return LB([
<             TB('COALESCE('),
<             LB(with_commas(compact, self.expr)),
<             TB(')'),
<         ])
< 
<     @staticmethod
<     def consume(lex) -> 'Optional[SQLCoalesce]':
<         if not lex.consume('COALESCE'):
<             return None
<         lex.expect('(')
< 
<         expr = []
<         while True:
<             expr.append(SQLConstant.parse(lex) or SQLIdentifierPath.parse(lex))
<             if not lex.consume(','):
<                 break
<         lex.expect(')')
< 
<         expr = SQLNodeList(expr)
<         return SQLCoalesce(expr)
< 
