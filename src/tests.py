import itertools

from query_language import query, expr, group, multi_group

expressions = [
"palavra1",
"palavra1 E palavra2",
"palavra1 ou palavra2",
"palavra1 ou palavra2 E palavra3",
"palavra1 E palavra2 ou palavra3 E palavra4",
]
# expr.run_tests(expressions)

groups = [f"({e})" for e in expressions]
# group.run_tests(groups)

multi_groups = [
"(palavra1 e (palavra2 ou palavra3))",
"(palavra1 e (palavra2 ou palavra3) ou palavra4)",
"(palavra1 e (palavra2 ou palavra3) ou (palavra4 e palavra5))",
"(palavra1 e (palavra2 ou palavra3) ou (palavra4 e palavra5) e palavra6)",
"(palavra1 e (palavra2 ou palavra3) ou (palavra4 e palavra5) e palavra6 ou palavra7)",
"(palavra1 e (palavra2 ou palavra3) ou (palavra4 e palavra5) e palavra6 ou (palavra7 e palavra8))",
"((palavra1 e (palavra2 ou palavra3)) ou (palavra1 e (palavra2 ou palavra3) ou (palavra4 e palavra5) e palavra6))",
]
# multi_group.run_tests(multi_groups)

everything = itertools.chain(
    itertools.product(expressions, groups, multi_groups),
    itertools.product(expressions, multi_groups, groups),
    itertools.product(groups, expressions, multi_groups),
    itertools.product(groups, multi_groups, expressions),
    itertools.product(multi_groups, groups, expressions),
    itertools.product(multi_groups, expressions, groups),
)
query.run_tests([
    *expressions,
    *groups,
    *multi_groups,
    *[" e ".join(e) for e in everything]
])
