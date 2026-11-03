"""CPT Studio GI round 4 proof harness (package P0 of the round-4 plan). Synthetic data only; nothing here sends.

Every tool reads a cpt-studio tree (``--tree DIR``, default: the tree this harness is in) offline: no network (sockets
refuse to connect), no database (a connection attempt raises), the provider disabled, no credentials file. Two trees are
compared from git refs (``--base REF --head REF``): each ref is exported with ``git archive`` into a scratch directory
and read in a process of its own; no worktree is ever changed. Run each tool from the cpt-studio directory with the
CPT Studio virtualenv's python and PYTHONDONTWRITEBYTECODE=1:

  H1  python -m ops.gi4.replay   --fixtures | --inputs DIR  [--tree DIR | --base REF --head REF] [--controls]
      Offline replay of the regression encounters (h4-01..h4-06, h2-08, h2-10) in every member state, scored against
      the manifests (HARD = safety, SOFT = the author's provisional expectations). --controls runs the positive
      controls: the base against itself is equal, and each of three planted mutations differs.
  H2  python -m ops.gi4.freeze   --base REF --head REF [--corpus FILE.jsonl ...] [--declare FILE]
      The request-side freeze: (a) sha256 of every cue pattern context.py and sections.py read, and sections.layout
      identity over the corpus; (b) the date channel per text and member state (NEW-SEND, NEW-TAKE, NEW-HELD,
      SEND->ASK; gate NEW-SEND = NEW-TAKE = 0); (c) request bytes; (d) the analyze stage's mention counts.
  H3  python -m ops.gi4.corpus   write OUT.jsonl | review | judge [--tree DIR | --base REF --head REF]
      The generated corpus with PROVISIONAL truth tables (gen.py, seeds.py, truth.py).
  H4  python -m ops.gi4.battery  [--tree DIR | --base REF --head REF] [--declare FILE]
      The assess battery: synthetic provider answers through jobs._assess_child, judged against each row's truth.
  H5  tests/test_gi4_state.py (Django tests: the throwaway test database only).
  H6  python -m ops.gi4.mutants  --base REF [--only NAME ...]
      One killing mutant per guard, applied to a sealed export, sha256 printed after apply and after restore.
  H7  python -m ops.gi4.cost     [--tree DIR] [--sizes 25000,50000,100000,200000,400000]
      Doubling cost probes of the readers and of the analyze and assess children under the stage limits.

The regression inputs (the retained live texts, states and manifests) are local files that CI cannot read: a tool that
needs them takes their directory as ``--inputs DIR`` and skips with a message when it is absent. The committed tests
read the small derived fixtures in tests/fixtures/gi4/ instead (synthetic documents and retained provider answers).

This package must stay import-light: ``unittest discover -s ops`` imports it, so nothing here imports Django or the
service at import time.
"""
