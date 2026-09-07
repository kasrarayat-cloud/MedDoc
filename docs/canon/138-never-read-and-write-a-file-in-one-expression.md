# NEVER READ AND WRITE A FILE IN ONE EXPRESSION — THE WRITE'S `open` TRUNCATES FIRST

**Ratified 2026-09-07.** A one-line idiom that destroyed a ruling's body and left
no trace.

```python
open(P, 'w').write(open(P).read().rstrip() + row)   # ⚠️ DESTROYS P
```

Python evaluates the **outer** `open(P, 'w')` first — it is the object whose
`.write` is about to be called — and opening for write **truncates immediately**.
Only then does the inner `open(P).read()` run, against a file that is now empty.

**The result is not an error.** The append succeeds, the script exits 0, and the
file contains exactly the appended fragment. A ruling archive became its own
one-line index row with the entire ruling gone.

## ⚠️ WHY IT SURVIVED REVIEW AND A COMMIT

Every downstream check still passed:

- the head/archive **row-identity** gate compares the ROW, and the row was there;
- `head N == archives N` counts ROWS, and the count was right;
- the file existed, was tracked, was committed, and `git status` was clean.

**It was found only by reading the file** — `head -4` showed two blank lines
where a title should be. Measured across the range afterwards: **exactly one
file** was hit; the siblings had been written with two statements and were
intact.

## THE RULE

> **Read into a variable. Write from the variable. Two statements, always.**

```python
t = open(P, encoding='utf-8').read().rstrip() + '\n\n' + row + '\n'
open(P, 'w', encoding='utf-8').write(t)
```

⚠️ **THE GENERAL SHAPE IS EVALUATION ORDER YOU DID NOT CHOOSE.** The same trap
lives in `cmd > file` reading `file`, in `sort f > f`, and in any pipeline whose
sink opens its target before the source has been consumed. **If one expression
both reads and writes the same path, the read loses** — and the failure is
silent, total, and looks like success.
