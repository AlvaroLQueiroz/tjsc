from pyparsing import (
    Forward,
    alphanums,
    CaselessKeyword,
    Group,
    Word,
    ZeroOrMore,
    OneOrMore,
)

connector = CaselessKeyword("E") | CaselessKeyword("OU")
word = Word(alphanums + "_-*")
expr = Group(word + ZeroOrMore(connector + word))
group = Group("(" + expr + ")")
multi_group = Forward()

multi_group <<= (
    "("
    + (expr ^ group ^ multi_group)
    + OneOrMore(
        connector
        + (group ^ multi_group)
        + ZeroOrMore(connector + (expr ^ group ^ multi_group))
    )
    + ")"
)

query = (expr ^ group ^ multi_group) + ZeroOrMore(
    connector + (expr ^ group ^ multi_group)
)
