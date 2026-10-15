# Submission checklist

This draft is not on arXiv and has not been submitted anywhere. Uploading needs the authors' arXiv account. Do not claim a submission that has not happened.

The paper is `zkLeash_IEEE_paper_v3.docx` at the repository root. `make paper` regenerates it from that docx (or from `zkLeash_IEEE_paper_revised.docx` if it is still present) and the files in `bench/results`, so the numbers in the text always come from the last run. `paper/REVIEW.md` lists what was wrong with the first IEEE draft. `paper/main.tex` is an older draft and is not kept in sync.

## Before posting the preprint

1. Fill in the highlighted placeholders in the docx: the five author e-mails, the guide's name in the acknowledgment, and the AI-use disclosure (IEEE requires one; edit the drafted sentence to say what was actually used). Mark the corresponding author.
2. Open the docx in Word and check the page count (the revision is estimated at about 6.5 of the 8 pages) and that the equations render. Word, not Pages, is the reference renderer.
3. Re-run the arXiv search in `docs/RELATED_WORK.md`. If a paper now covers stateful zkVM risk checks for agents, rewrite the introduction before you post.
4. Reference [3] is the arXiv preprint (2503.16248). The arXiv record had no journal reference on Oct 15, 2026. If a Financial Cryptography proceedings version appears, replace the citation with the LNCS volume and pages.
5. Replace `bench/heldout.json` with cases written by someone who has not read `LeashExecutor.sol`.
6. Run `make reproduce` (and `make sp1-cycles` if the SP1 toolchain is installed) and confirm the regenerated docx matches the version you submit.
7. If Succinct credits arrive, add a short "Groth16 confirmation" subsection with real proving time and verifier gas. Until then, keep the abstract's split: the 250 decisions are native runs of the guest crate, and the SP1 executor was used only for the calm cycle sweep.

## Where to send it, after the preprint

Check the current call for papers and keep the manuscript inside that call's page limit. A realistic target is IEEE ICBC, the IEEE Blockchain conference, or the Financial Cryptography DeFi or WTSC workshop, plus the ACM CCS DeFi Security workshop and AsiaCCS workshops if their calls fit. This evaluation does not support IEEE S&P, ACM CCS, USENIX Security, NDSS, or the Financial Cryptography main track: there is no Groth16 proof, no measured verification gas, no live model, and no attacker who has not read the executor. IEEE Access is plausible only after one real Groth16 run, with proving time and verifier gas, is in the paper. Other journals if a conference does not fit: Blockchain: Research and Applications, Computers & Security. If the department requires a Scopus-indexed venue, confirm the indexing of the specific edition, not the series name.

## What the paper contains

The Foundry suite (20 tests and an invariant), the 250-trial harness with structural trials kept out of the measured rate, the daily-notional baseline, the August 2024 ETH-USDT replay, Clopper-Pearson intervals, the salami loss curves, EWMA gas from calldata and from storage, and SP1 executor cycle counts. It states what was not measured: no Groth16 proof, no live model (the Ollama panel is `bench/model_panel.py`), and a scripted attacker. The randomized prices are synthetic; the crash replay is one real window.
