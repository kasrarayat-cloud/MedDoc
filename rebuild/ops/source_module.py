"""Load a script BY ITS SOURCE, never from a compiled cache.

⚠️ THE HAZARD, MEASURED RATHER THAN ASSUMED. `importlib.util.spec_from_file_location` +
`spec.loader.exec_module` is a SourceFileLoader, and a SourceFileLoader will serve `__pycache__` whenever
the cached header's recorded source mtime AND size still match the file. A mutation proof — edit a
constant, run the suite, restore the file — restores both: same size, and the write lands inside the same
one-second mtime granularity. So the run after the restore can execute the version from BEFORE it.

Measured on this host with CPython 3.12:

    1st load                 : ORIGINAL   (writes __pycache__)
    after mutate, default    : ORIGINAL   ← the file on disk says MUTATED
    after mutate, dont_write : ORIGINAL   ← sys.dont_write_bytecode only stops WRITING
    after mutate, compile()  : MUTATED

⚠️ **IT COST A WRONG ANSWER IN THE SESSION THAT FOUND IT.** A proof that a wrong `SHIPPED` constant makes
an activation test fail reported a failure that came from a STALE activator, not from the constant under
test — a green-looking confirmation of a check that was reading yesterday's file. That is the same family
as the canon's "a mutation proof asserts its own application" and "…its own restoration", and it is the
third sibling: **a proof must also assert it is reading what it restored.** Nothing warns; there is no
error, no mtime complaint, no message. The loader is behaving exactly as documented.

`compile()` on the text takes no cache and cannot be stale.
"""
import types


def load(name, path):
    """Execute `path` as a throwaway module named `name`, reading the source text every time."""
    module = types.ModuleType(name)
    module.__file__ = str(path)
    with open(path, 'r', encoding='utf-8') as handle:
        source = handle.read()
    exec(compile(source, str(path), 'exec'), module.__dict__)
    return module
