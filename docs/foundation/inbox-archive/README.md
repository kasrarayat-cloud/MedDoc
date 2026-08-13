# Retired inbox entries

Entries move here once a session's log shows they were delivered — **archived,
never deleted**. The record of what a session was told at launch is part of the
record of what it did.

Confirm delivery before retiring:

    grep -l "<the entry's timestamp>" docs/foundation/logs/*.log

One file per entry, named `<UTC-date>-<slug>.md`, carrying the entry verbatim
and the log it was found in.
