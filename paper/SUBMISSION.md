# Submission checklist

This draft is not on arXiv and has not been submitted anywhere. Uploading needs the authors' arXiv account. Do not claim a submission that has not happened.

The paper is `zkLeash_IEEE_paper_v3.docx` at the repository root. `make paper` regenerates it from `zkLeash_IEEE_paper_revised.docx` and the files in `bench/results`, so the numbers in the text always come from the last run. `paper/REVIEW.md` lists what was wrong with the previous version and what changed. `paper/main.tex` is an older draft and is not kept in sync.

## Before posting the preprint

1. Fill in the highlighted placeholders in the docx: the five author e-mails, the guide's name in the acknowledgment, and the AI-use disclosure (IEEE requires one; edit the drafted sentence to say what was actually used). Mark the corresponding author.
2. Open the docx in Word and check the page count (the revision is estimated at about 6.5 of the 8 pages) and that the equations render. Word, not Pages, is the reference renderer.
3. Re-run the arXiv search in `docs/RELATED_WORK.md`. If a paper now covers stateful zkVM risk checks for agents, rewrite the introduction before you post.
4. Check reference [3]: the paper cites it as FC 2026. Replace with the proceedings entry (LNCS volume and pages) once it is published, or cite only the arXiv version.
5. Replace `bench/heldout.json` with cases written by someone who has not read `LeashExecutor.sol`.
6. Run `make reproduce` (and `make sp1-cycles` if the SP1 toolchain is installed) and confirm the regenerated docx matches the version you submit.
7. If Succinct credits arrive, add a short "Groth16 confirmation" subsection with real proving time and verifier gas. Until then, keep the sentence in the abstract that the guest was executed in SP1 but not proved.

## Where to send it, after the preprint

Check the current call for papers. The plan's targets were IEEE ICBC, IEEE Blockchain, the Financial Cryptography DeFi and WTSC workshops, the ACM CCS DeFi Security workshop, and AsiaCCS workshops. Journals if a conference does not fit: IEEE Access, Blockchain: Research and Applications, Computers & Security. If the department requires a Scopus-indexed venue, confirm the indexing of the specific edition, not the series name. Keep the paper at eight pages or fewer until the venue is chosen.

## What the paper contains

The Foundry suite (20 tests and an invariant), the 225-trial randomized harness with deny reasons and Clopper-Pearson intervals, the salami loss curves, the EWMA gas from calldata and from storage plus the trade-path gas, and SP1 executor cycle counts with a byte-for-byte comparison against native execution. It states what was not measured: no Groth16 proof, no live model, synthetic prices, and a scripted attacker.
