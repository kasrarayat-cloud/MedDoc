END = lines_with(SRC, "INNER_SENTENCE_END = re.compile(", 2)
old = r"|[\u3002\uff0e\uff01\uff1f\uff61](?=\S)"
assert END.count(old) == 1
new = END.replace(old, "")
compile(SRC.replace(END, new), "mutant-generation.py", "exec")
MUTANTS = [("FD a CJK stop is not a sentence end (valid replacement)", [(END, new)])]
