# A GREP THAT CANNOT DISPLAY THE FAILURE LINE IS A GREEN NOBODY READ

**Standing 2026-09-08. Owner-ruled after it hid a real defect for two rounds.**

> **A filter you wrote to make output readable is an instrument. If its pattern
> cannot match the line that says "broken", every run through it reports
> healthy — and it reports healthy in exactly the same words it would use if
> the thing were healthy.**

## THE INSTANCE

Reading vitest output across a long session, the habit was:

```bash
npm run test:unit … 2>&1 | grep -E "Tests |Test Files"
```

Which is a reasonable thing to want: two lines instead of four hundred. It was
used dozens of times and it was always green.

Vitest's summary block is:

```
 Test Files  458 passed | 2 skipped (460)
      Tests  6464 passed | 4 skipped | 2 todo (6470)
     Errors  1 error                                 ← the pattern cannot match this
```

**`Errors` contains neither `Tests ` nor `Test Files`.** A module-scope
`void main()` in an imported script had been executing a production regeneration
script on every run — a script that WRITES A FILE when given an output path,
saved only by the absence of an argument under vitest. The suite was genuinely
`6464 passed`. It was also erroring, every time, invisibly.

⚠️ **CI CAUGHT IT. THE LOCAL READING COULD NOT HAVE**, no matter how many times
it was repeated, because the instrument was incapable of showing it.

## WHY IT IS NOT "JUST BE CAREFUL"

The filter was not wrong about what it matched. It matched correctly, every
time, and answered a question — *did the tests pass?* — that was not the
question being asked, which was *is this run clean?*

> **THE WATCHED-SET FAILURE AGAIN, IN A ONE-LINE COSTUME:** a flawless
> instrument, answering correctly, about the wrong universe.

That family already has entries here for `pgrep -f`, for
`gh run list --commit`, and for a mutation proof whose marker sat on the
decorative half of a two-part edit. This is the cheapest possible member of it,
which is why it is the easiest to repeat.

## THE HABIT

1. **Read the WHOLE summary block at least once per session**, and after any
   change to what the suite loads. `tail -8` costs nothing.
2. **When filtering, match the FAILURE vocabulary explicitly**, not the success
   vocabulary — and include the words you do not expect:

   ```bash
   grep -E "Tests |Test Files|Errors|Unhandled|FAIL|×"
   ```

3. **Ask of any filter: if this run were broken in the way I am not thinking
   of, would this pattern show me?** If the answer is "only if it breaks the way
   I anticipated", the filter is checking your imagination rather than the run.
4. ⚠️ **A GREEN THROUGH A NARROW FILTER IS NOT EVIDENCE.** Do not cite it as one.
   The tell is that nothing ever looks different: a filter that has never once
   surprised you is a filter that may be incapable of surprising you.

## THE COST, HONESTLY

Nothing was lost — the script had no output path under vitest, so it wrote
nothing, and CI's unfiltered view failed the branch. **The cost it prevents is
the run where the filtered green is the LAST reading before a merge**, and the
error line it could not display was the one that mattered.
