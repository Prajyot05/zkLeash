# Submission checklist

This draft is not on arXiv and has not been submitted anywhere. Uploading needs the authors' arXiv account. Do not claim a submission that has not happened.

## Before posting the preprint

1. Re-run the arXiv search in `docs/RELATED_WORK.md`. If a paper now covers stateful zkVM risk checks for agents, rewrite the introduction before you post.
2. Replace `bench/heldout.json` with cases written by someone who has not read `LeashExecutor.sol`.
3. Put author names and the institution on `paper/main.tex`.
4. Run `make test` and confirm `bench/results/summary.json` still matches the table.
5. If Succinct credits arrived, add a short "Groth16 confirmation" subsection with real proof latency. Until then, leave the execute-mode caveat in the abstract.

## Where to send it, after the preprint

Check the current call for papers. The plan's targets were IEEE ICBC, IEEE Blockchain, the Financial Cryptography DeFi and WTSC workshops, the ACM CCS DeFi Security workshop, and AsiaCCS workshops. Journals if a conference does not fit: IEEE Access, Blockchain: Research and Applications, Computers & Security. If the department requires a Scopus-indexed venue, confirm the indexing of the specific edition, not the series name.

## What the draft already contains

`paper/main.tex` is the paper. It reports the Foundry suite, the 60-trial harness, the McNemar figures, and the EWMA gas samples. It states what was not measured.
