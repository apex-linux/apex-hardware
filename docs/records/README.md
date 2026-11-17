# Acceptance records

Records of acceptance runs on an installed Apex system. The M1 exit is a
record here from the M7400QC in which every row is `PASS` (or `SKIP` for
hardware the machine lacks).

A run of every row writes two files into `~/apex-acceptance/` on the
machine, named `<date>-<os id>-<version>`:

*   `.md`: the summary, the system facts, the printed output, and every
    row's evidence: the automated check, the after-resume measurement, and
    each guided step with the person's answer.
*   `.json`: the same, for scripts (`schema` 1).

Copy both files here unchanged, in one pull request per run, titled after
the record, for example "Record the 2026-11-20 acceptance run on Apex 45".
The run book in [acceptance.md](../acceptance.md) says how.

Records from before Apex, measured on the previous system, are in
[baselines/](../baselines/).
