import re

DECOUPLE_PARENTHESES = re.compile(r"(\S*)(\(|\))(\S*)")
WORD = re.compile(r"\w+", re.UNICODE)
ALL = r"[\s\S]*"

async def convert_pattern_to_regex(query_string: str) -> re.Pattern:
    rgx = r""
    query_string = DECOUPLE_PARENTHESES.sub(r"\1 \2 \3", query_string)

    for token in query_string.split():
        token = token.strip().lower()
        if token.startswith("*"):
            token = f"{ALL}{token[1:]}"
        elif token.endswith("*"):
            token = f"{token[:-1]}{ALL}"
        elif token == "e":
            token = ""
        elif token == "ou":
            token = "|"

        if (
            not rgx.endswith((ALL, "|", "(")) and
            not token.startswith(ALL) and
            token != "|"
        ):
            rgx += ALL + token
        else:
            rgx += token

    return re.compile(rgx, re.IGNORECASE|re.UNICODE|re.MULTILINE)


async def find_pattern_in_text(text: str, pattern: str) -> bool:
    compiled_pattern = await convert_pattern_to_regex(pattern)
    matches = compiled_pattern.findall(text)
    return len(matches) > 0


if __name__ == "__main__":
    patterns = [
        # "(palavra1 e (palavra2 ou palavra3) ou (palavra4 e palavra5) e palavra6 ou (palavra7 e palavra8))",
        # "((palavra1 e (palavra2 ou palavra3)) ou (palavra1 e (palavra2 ou palavra3) ou (palavra4 e palavra5) e palavra6))",
        "junho e (dois mil e dezenove OU 2019) E (alva* OU MONIK)",
    ]
    for pattern in patterns:
        print(convert_pattern_to_regex(pattern))
