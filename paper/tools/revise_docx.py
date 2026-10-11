#!/usr/bin/env python3
"""Build zkLeash_IEEE_paper_v3.docx from zkLeash_IEEE_paper_revised.docx.

The original supplies the title, the author table (template ordinals removed), the
page setup, the styles, and the numbering definitions. The body is regenerated from
the text in this file. Every measured number is read from bench/results, so rerun
this script after `make bench gas figures`.

    python paper/tools/revise_docx.py

Inline markup in body strings: *italic*, **bold**, _{subscript}, ^{superscript}
(both may contain *italic*), and [[highlighted placeholder]].
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from xml.sax.saxutils import escape

from docx import Document
from docx.oxml import parse_xml
from docx.oxml.ns import qn
from docx.shared import Inches

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "zkLeash_IEEE_paper_revised.docx"
OUT = ROOT / "zkLeash_IEEE_paper_v3.docx"
RESULTS = ROOT / "bench" / "results"
FIG_ARCH = ROOT / "paper" / "figures" / "architecture.png"
FIG_SALAMI = RESULTS / "salami_curve.png"

NS = (
    'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
    'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"'
)
FONT = '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman" w:eastAsia="Times New Roman"/>'

# Original element indices that are kept as they are.
KEEP_HEAD = (0, 1, 2, 3)  # title, author table, spacer, single-column section break
KEEP_TAIL = (124, 125)  # two-column section break, spacer


# ---------------------------------------------------------------------------
# Runs and paragraphs.


def rpr(sz=20, b=False, i=False, sc=False, va=None, hl=False, explicit=True) -> str:
    x = FONT
    if explicit:
        x += "<w:b/><w:bCs/>" if b else '<w:b w:val="false"/><w:bCs w:val="false"/>'
        x += "<w:i/><w:iCs/>" if i else '<w:i w:val="false"/><w:iCs w:val="false"/>'
        x += "<w:smallCaps/>" if sc else '<w:smallCaps w:val="false"/>'
    else:
        x += "<w:i/><w:iCs/>" if i else ""
        x += "<w:smallCaps/>" if sc else ""
    x += f'<w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/>'
    if hl:
        x += '<w:shd w:val="clear" w:color="auto" w:fill="FFFF00"/>'
    if va:
        x += f'<w:vertAlign w:val="{va}"/>'
    return f"<w:rPr>{x}</w:rPr>"


def run(text: str, **fmt) -> str:
    parts = text.split("\t")
    body = '<w:tab/>'.join(f'<w:t xml:space="preserve">{escape(p)}</w:t>' for p in parts)
    return f"<w:r>{rpr(**fmt)}{body}</w:r>"


TOKEN = re.compile(r"(\*\*.+?\*\*|\*[^*]+?\*|_\{(?:[^{}]|\{[^{}]*\})+\}|\^\{(?:[^{}]|\{[^{}]*\})+\}|\[\[.+?\]\])")


def runs(text: str, sz=20, b=False, i=False, va=None, hl=False) -> str:
    out = []
    for tok in TOKEN.split(text):
        if not tok:
            continue
        if tok.startswith("**"):
            out.append(runs(tok[2:-2], sz, True, i, va, hl))
        elif tok.startswith("*"):
            out.append(runs(tok[1:-1], sz, b, not i, va, hl))
        elif tok.startswith("_{"):
            out.append(runs(tok[2:-1], sz, b, i, "subscript", hl))
        elif tok.startswith("^{"):
            out.append(runs(tok[2:-1], sz, b, i, "superscript", hl))
        elif tok.startswith("[["):
            out.append(runs(tok[2:-2], sz, b, i, va, True))
        else:
            out.append(run(tok, sz=sz, b=b, i=i, va=va, hl=hl))
    return "".join(out)


def P(ppr: str, content: str):
    return parse_xml(f"<w:p {NS}><w:pPr>{ppr}</w:pPr>{content}</w:p>")


BODY_PPR = '<w:spacing w:before="0" w:after="100"/><w:ind w:firstLine="288"/><w:jc w:val="both"/>'


def body(text: str):
    return P(BODY_PPR, runs(text))


def front(label: str, text: str):
    ppr = '<w:spacing w:after="120"/><w:ind w:firstLine="288"/><w:jc w:val="both"/>'
    return P(ppr, run(label, sz=18, b=True, i=True) + runs("\u2014" + text, sz=18, b=True))


def h1(text: str, numbered=True):
    num = '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="2"/></w:numPr>' if numbered else ""
    return P(f'<w:pStyle w:val="Heading1"/>{num}', run(text, sc=True, explicit=False))


def h2(text: str):
    ppr = '<w:pStyle w:val="Heading2"/><w:numPr><w:ilvl w:val="1"/><w:numId w:val="2"/></w:numPr>'
    return P(ppr, run(text, i=True, explicit=False))


def item(text: str, num_id: int, sz=20, after=60):
    ppr = (
        f'<w:pStyle w:val="ListParagraph"/><w:numPr><w:ilvl w:val="0"/><w:numId w:val="{num_id}"/></w:numPr>'
        f'<w:spacing w:after="{after}"/><w:jc w:val="both"/>'
    )
    return P(ppr, runs(text, sz=sz))


def ref(text: str):
    return item(text, 6, sz=16, after=40)


def caption(text: str):
    return P('<w:spacing w:after="120"/><w:jc w:val="both"/>', runs(text, sz=16))


def table_title(number: str, title: str):
    return [
        P('<w:keepNext/><w:spacing w:after="0"/><w:jc w:val="center"/>', run(f"Table {number}", sz=16, sc=True, explicit=False)),
        P('<w:keepNext/><w:spacing w:after="60"/><w:jc w:val="center"/>', run(title, sz=16, sc=True, explicit=False)),
    ]


def table_note(text: str):
    return P('<w:spacing w:before="40" w:after="120"/><w:jc w:val="both"/>', runs(text, sz=14))


# ---------------------------------------------------------------------------
# Equations (Office Math).


def mr(text: str, plain=False) -> str:
    sty = '<m:rPr><m:sty m:val="p"/></m:rPr>' if plain else ""
    return f'<m:r>{sty}<m:t xml:space="preserve">{escape(text)}</m:t></m:r>'


def msub(e: str, s: str) -> str:
    return f"<m:sSub><m:e>{e}</m:e><m:sub>{s}</m:sub></m:sSub>"


def msup(e: str, s: str) -> str:
    return f"<m:sSup><m:e>{e}</m:e><m:sup>{s}</m:sup></m:sSup>"


def msubsup(e: str, a: str, b: str) -> str:
    return f"<m:sSubSup><m:e>{e}</m:e><m:sub>{a}</m:sub><m:sup>{b}</m:sup></m:sSubSup>"


def mfrac(n: str, d: str) -> str:
    return f"<m:f><m:num>{n}</m:num><m:den>{d}</m:den></m:f>"


def msum(a: str, b: str, e: str) -> str:
    return (
        '<m:nary><m:naryPr><m:chr m:val="\u2211"/><m:limLoc m:val="undOvr"/></m:naryPr>'
        f"<m:sub>{a}</m:sub><m:sup>{b}</m:sup><m:e>{e}</m:e></m:nary>"
    )


def equation(omml: str, n: int):
    ppr = (
        '<w:tabs><w:tab w:val="center" w:pos="2520"/><w:tab w:val="right" w:pos="5040"/></w:tabs>'
        '<w:spacing w:before="60" w:after="120"/>'
    )
    tab = f"<w:r>{rpr(explicit=False)}<w:tab/></w:r>"
    return P(ppr, f"{tab}<m:oMath>{omml}</m:oMath>{tab}{run(f'({n})')}")


def eq_return():
    prev = msub(mr("p"), mr("t\u22121"))
    return equation(msub(mr("r"), mr("t")) + mr("=") + mfrac(msub(mr("p"), mr("t")) + mr("\u2212") + prev, prev), 1)


def eq_variance():
    rhs = (
        mr("\u03bb") + msub(mr("v"), mr("t\u22121")) + mr("+(1\u2212\u03bb)") + msubsup(mr("r"), mr("t"), mr("2"))
        + mr(",  \u03bb=0.94")
    )
    return equation(msub(mr("v"), mr("t")) + mr("=") + rhs, 2)


def eq_exposure():
    return equation(mr("V=") + msum(mr("i=1"), mr("n"), msub(mr("E"), mr("i")) + msub(mr("\u03c3"), mr("i"))), 3)


def eq_fair():
    num = msub(mr("a"), mr("in", True)) + msub(mr("P"), mr("in", True)) + msup(mr("10"), msub(mr("d"), mr("out", True)))
    den = msub(mr("P"), mr("out", True)) + msup(mr("10"), msub(mr("d"), mr("in", True)))
    return equation(mr("fairOut", True) + mr("=") + mfrac(num, den), 4)


def eq_min():
    return equation(mr("minOut", True) + mr("=") + mr("fairOut", True) + mr("\u00b7") + mfrac(mr("10000\u2212s"), mr("10000")), 5)


def eq_hash():
    k = lambda v: msub(mr(v), mr("k"))  # noqa: E731
    inner = msub(mr("h"), mr("k\u22121")) + mr("\u2225") + k("p") + mr("\u2225") + k("c") + mr("\u2225") + k("e") + mr("\u2225") + k("\u03c4")
    return equation(k("h") + mr("=") + mr("keccak256", True) + mr("(") + inner + mr(")"), 6)


# ---------------------------------------------------------------------------
# Tables.


def cell(text: str, width: int, header=False, align="center", span=1, top_rule=False) -> str:
    top = '<w:top w:val="single" w:color="000000" w:sz="12"/>' if top_rule else '<w:top w:val="single" w:color="000000" w:sz="4"/>'
    borders = (
        f"<w:tcBorders>{top}"
        '<w:left w:val="single" w:color="000000" w:sz="4"/>'
        '<w:bottom w:val="single" w:color="000000" w:sz="4"/>'
        '<w:right w:val="single" w:color="000000" w:sz="4"/></w:tcBorders>'
    )
    span_xml = f'<w:gridSpan w:val="{span}"/>' if span > 1 else ""
    tcpr = (
        f'<w:tcPr><w:tcW w:type="dxa" w:w="{width}"/>{span_xml}{borders}'
        '<w:tcMar><w:top w:type="dxa" w:w="20"/><w:left w:type="dxa" w:w="60"/>'
        '<w:bottom w:type="dxa" w:w="20"/><w:right w:type="dxa" w:w="60"/></w:tcMar>'
        '<w:vAlign w:val="center"/></w:tcPr>'
    )
    content = run(text, sz=16, sc=True) if header else runs(text, sz=16)
    return f'<w:tc>{tcpr}<w:p><w:pPr><w:spacing w:after="0"/><w:jc w:val="{align}"/></w:pPr>{content}</w:p></w:tc>'


def table(widths: list[int], header: list[str], rows: list[list], rules: frozenset = frozenset()):
    """rows: lists of str or (str, span); first column left-aligned. rules: row indexes with a heavy top line."""
    grid = "".join(f'<w:gridCol w:w="{w}"/>' for w in widths)
    trs = ['<w:tr><w:trPr><w:cantSplit/><w:tblHeader/></w:trPr>'
           + "".join(cell(h, widths[k], header=True) for k, h in enumerate(header)) + "</w:tr>"]
    for r, row in enumerate(rows):
        cells, col = [], 0
        for c in row:
            text, span = c if isinstance(c, tuple) else (c, 1)
            w = sum(widths[col:col + span])
            cells.append(cell(text, w, align="left" if col == 0 else "center", span=span, top_rule=r in rules))
            col += span
        trs.append('<w:tr><w:trPr><w:cantSplit/></w:trPr>' + "".join(cells) + "</w:tr>")
    border = '<w:{0} w:val="single" w:color="auto" w:sz="4"/>'
    tblpr = (
        f'<w:tblPr><w:tblW w:type="dxa" w:w="{sum(widths)}"/><w:jc w:val="center"/><w:tblBorders>'
        + "".join(border.format(s) for s in ("top", "left", "bottom", "right", "insideH", "insideV"))
        + '</w:tblBorders><w:tblLayout w:type="fixed"/></w:tblPr>'
    )
    return parse_xml(f"<w:tbl {NS}>{tblpr}<w:tblGrid>{grid}</w:tblGrid>{''.join(trs)}</w:tbl>")


# ---------------------------------------------------------------------------
# Figures.


def figure(doc, path: Path, width_in: float, name: str, descr: str):
    inline = doc.part.new_pic_inline(str(path), Inches(width_in), None)
    doc_pr = inline.find(qn("wp:docPr"))
    doc_pr.set("name", name)
    doc_pr.set("descr", descr)
    p = P('<w:keepNext/><w:spacing w:before="60" w:after="60"/><w:jc w:val="center"/>', "<w:r><w:drawing/></w:r>")
    p.find(f".//{qn('w:drawing')}").append(inline)
    return p


# ---------------------------------------------------------------------------
# Numbers.


def load_results() -> dict:
    summary = json.loads((RESULTS / "summary.json").read_text())
    gas = json.loads((RESULTS / "gas.json").read_text())
    sp1_path = RESULTS / "sp1_cycles.json"
    sp1 = json.loads(sp1_path.read_text()) if sp1_path.exists() else None
    return {"s": summary, "g": gas, "sp1": sp1}


WORDS = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine"}


def pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def usd(x: float) -> str:
    return f"${x:,.0f}"


# ---------------------------------------------------------------------------
# The paper.


SYSTEMS = ["B0_unguarded", "B1_prompt_filter", "B2_static", "B3_signed", "B4_stateless", "zkLeash"]
FAMILIES = [
    ("direct_transfer", "Direct transfer", "S"),
    ("illiquid_pool", "Unlisted router", "S"),
    ("stolen_key", "Stolen key", "S"),
    ("indirect_all_in", "All-in buy", "G"),
    ("vol_spike_buy", "Vol. spike buy", "G"),
    ("salami", "Salami drain", "G+L"),
    ("benign_rebalance", "Calm rebalance", "G"),
    ("calm_buy", "Calm buy", "G"),
    ("derisk_in_drawdown", "De-risk sale", "G"),
]


def build(doc, R: dict) -> list:
    s, g, sp1 = R["s"], R["g"], R["sp1"]
    sysm = s["systems"]
    fam = s["per_family"]
    zk = sysm["zkLeash"]
    harmful_n = zk["attack_success"]["n"]
    benign_n = zk["false_block"]["n"]
    guest_n = zk["attack_success_guest_decided"]["n"]
    total_n = harmful_n + benign_n
    per_fam = fam["salami"]["n"]
    n_fams = WORDS.get(len(fam), str(len(fam)))
    zk_hi = pct(zk["attack_success"]["ci95"][1])
    zk_guest_hi = pct(zk["attack_success_guest_decided"]["ci95"][1])
    zk_fb_hi = pct(zk["false_block"]["ci95"][1])
    sal = fam["salami"]
    sal_b4 = sal["loss_usd_B4_stateless"]
    sal_zk = sal["loss_usd_zkLeash"]
    legs = sal["legs_executed_ledger"]
    cap = s["config"]["policy"]["max_window_loss"]
    vol_budget = s["config"]["policy"]["max_vol_exposure"]
    static_cap = s["config"]["static_cap_usd"]
    salami_legs = s["config"]["salami_legs"]
    allin = fam["indirect_all_in"]["zkleash_deny_reasons"]
    spike = fam["vol_spike_buy"]
    ratios = [f.get("sigma_est_over_true_median") for f in fam.values() if f.get("sigma_est_over_true_median")]
    toy, real = s["salami_curves"]["toy"], s["salami_curves"]["realistic"]
    ew_c, ew_s = g["ewma_calldata_gas"], g["ewma_storage_gas"]
    cross = g["single_asset_points_to_exceed_280k"]
    eg = g["execute_guarded_gas"]

    if sp1:
        rows = sp1["runs"]
        lo, hi = rows[0], rows[-1]
        all_same = all(r["identical"] for r in rows)
        per_point = (hi["cycles"] - lo["cycles"]) / ((hi["points_per_asset"] - lo["points_per_asset"]) * hi["assets"])
        sp1_impl = (
            "We compiled the guest with the SP1 toolchain and ran it in the SP1 executor, which runs the RISC-V program "
            f"without generating a proof, for histories of {lo['points_per_asset']} to {hi['points_per_asset']} prices per asset on the two-asset calm scenario. "
            + ("Its committed public values were byte-identical to native execution in every case. " if all_same else "")
            + f"Execution took {lo['cycles']:,} RISC-V cycles at {lo['points_per_asset']} prices and {hi['cycles']:,} at {hi['points_per_asset']}, "
            f"or about {per_point:,.0f} cycles for each additional price."
        )
        exec_phrase = (
            "native execution of the guest crate; on the inputs we also ran in the SP1 executor, the two produced "
            "byte-identical public values (Section VII)"
        )
        abstract_tail = "The attacker is scripted, prices are synthetic, the guest was executed in SP1 but not proved, and no live model was scored."
        limit_proof = (
            "No Groth16 proof was generated. We ran the guest in the SP1 executor, which gives cycle counts but not proving time, "
            "and we cite rather than measure verification gas. The tests use a stand-in verifier."
        )
    else:
        sp1_impl = "The harness runs the guest crate natively; we did not run the SP1 executor for the results reported here."
        exec_phrase = "native execution of the guest crate"
        abstract_tail = "The attacker is scripted, prices are synthetic, the guest was executed natively but not proved, and no live model was scored."
        limit_proof = (
            "No Groth16 proof was generated. Guest decisions come from native execution of the same crate, and the tests use a "
            "stand-in verifier. We report neither proving time nor measured verification gas."
        )

    E: list = []
    add = E.append

    add(front("Abstract", (
        "LLM agents are increasingly given access to cryptocurrency wallets, where a prompt injection or a faulty numerical "
        "judgment can lose funds irreversibly. Existing guards check one transaction at a time and rely on a trusted signing key "
        "or a flat per-session budget. We present zkLeash, a smart-account design in which the untrusted agent can only propose "
        "a swap. The agent\u2019s session key reaches a single executor function, which swaps only if a deterministic risk function, "
        "compiled for the SP1 zero-knowledge virtual machine and evaluated over a hash-chained log of Pyth prices, approved that "
        "exact action, and an on-chain ledger of execution losses, committed into every proof, still has headroom in a rolling "
        "window. The proof replaces an off-chain signature, and the contract re-checks every inexpensive limit. "
        f"On {total_n} randomized trials in {n_fams} families, zkLeash admitted none of {harmful_n} harmful trials (95% upper bound {zk_hi}) "
        f"and blocked none of {benign_n} benign ones (upper bound {zk_fb_hi}). The same proof without the ledger admitted all "
        f"{per_fam} multi-trade drains, losing up to {usd(sal_b4['max'])} against a {usd(cap)} cap, and a static notional cap admitted "
        "every buy during a volatility spike while blocking every large de-risking sale. Computing the same volatility on-chain "
        f"from stored prices costs {ew_s['8'] / 1000:.0f}k to {ew_s['128'] / 1000:.0f}k gas for 8 to 128 prices, more than the roughly 280k gas "
        f"of verifying an SP1 Groth16 proof beyond about {cross['storage']} prices. " + abstract_tail
    )))
    add(front("Index Terms", (
        "Decentralized finance, ERC-4337, LLM agents, prompt injection, risk management, smart accounts, zero-knowledge proofs"
    )))

    # I
    add(h1("Introduction"))
    add(body(
        "Developers now routinely give LLM agents access to cryptocurrency wallets so that the agent can swap, lend, and rebalance "
        "holdings on the user\u2019s behalf. The practice carries two distinct risks. The first is that an agent can be steered by "
        "whatever text it reads: a message from the user, a news item, a token\u2019s metadata, or the output of a tool may embed an "
        "instruction such as \u201csend all funds to this address,\u201d and the model may comply [1], [2]. Attacks on Web3 agents that "
        "work by tampering with their context have already been demonstrated [3]. The second risk is that the model\u2019s own view of "
        "whether a trade is safe is an opinion rather than a verified calculation, and a blockchain transaction cannot be undone."
    ))
    add(body(
        "An obvious remedy is to put a deterministic guard between the agent and the wallet, and the nearest prior systems do "
        "exactly that. PACE signs a policy decision that is tied to the precise bytes of the transaction [4]. Proof-Gated Signing "
        "uses a solver to test a policy over a band of oracle uncertainty and enforces post-conditions on-chain [5]. Two gaps "
        "remain. Each system evaluates a transaction in isolation, so a drain made of many small trades, each acceptable by itself, "
        "slips past the per-trade rule: the PACE authors report that their design and all of their baselines let a five-leg drain "
        "through [4], and Proof-Gated Signing bounds an in-policy drain only through a per-session budget [5]. In addition, PACE "
        "depends on the signing key of an off-chain verifier."
    ))
    add(body("This paper presents zkLeash, which targets both gaps. Our contributions are as follows:"))
    add(item(
        "*A stateful, keyless guard.* A zero-knowledge proof of a deterministic risk computation replaces the signature, and an "
        "on-chain ledger of execution loss, committed into every proof, carries state from one trade to the next.", 3))
    add(item(
        "*Binding the proof to an action, a policy, and chain state.* An action hash, a policy commitment, price-log heads, and the "
        "ledger state tie every proof to one swap under one set of limits, and the contract re-derives each limit that is cheap to "
        "compute.", 3))
    add(item(
        f"*An evaluation that isolates each mechanism.* On {total_n} seeded, randomized trials we record which check denies each "
        "trade. The ledger alone stops multi-trade drains, and the proved volatility statistic alone stops buys during volatility "
        "spikes. We also measure the gas of computing that statistic on-chain from stored prices.", 3))
    add(body(
        "Section II surveys related work and Section III states the threat model. Section IV presents the design, Section V the "
        "algorithms, Section VI a security analysis, and Section VII the implementation. Section VIII reports the evaluation, and "
        "Sections IX and X discuss limitations and conclude. Section IX also states what the evidence does not establish."
    ))

    # II
    add(h1("Background and Related Work"))
    add(h2("Prompt Injection and Web3 Agents"))
    add(body(
        "Prompt injection redirects a model away from its intended goal by means of attacker-supplied text [1]. In the indirect "
        "variant, that text arrives inside data the application fetches [2]. Benchmarks such as InjecAgent [6] and AgentDojo [7] "
        "show that tool-using agents remain vulnerable across models and defenses. In the wallet setting, Patlan et al. show that "
        "corrupting an agent\u2019s prompt or stored memory leads to unauthorized transfers, and they release the CrAIBench benchmark "
        "[3]. CaMeL argues for defenses that hold by construction rather than by model behavior [8]. zkLeash applies the same "
        "principle at the wallet: its guarantees do not depend on the model resisting the attack."
    ))
    add(h2("Transaction-Level Guards"))
    add(body(
        "PACE is an authorization framework that works on individual transactions [4]. An agent\u2019s request is expressed as a typed "
        "intent, a deterministic verifier evaluates it against a policy, and the outcome is recorded in a signed decision record "
        "that ties the approved intent, the policy, and the simulation report to the exact bytes that will be executed, with "
        "replay and expiry protection. A Solidity smart account validates the signatures on-chain. In its study of an adaptive "
        "adversary, a drain split into five legs that each stay below the cap is admitted by PACE and by all of its baselines, and "
        "the authors name multi-step sequences and an ERC-4337 validation module as future work."
    ))
    add(body(
        "Proof-Gated Signing takes a different route [5]. It simulates the transaction, asks a solver whether a value-and-permission "
        "policy holds at every price inside an oracle-uncertainty band, and turns the assumptions behind that result into "
        "post-conditions that the wallet checks atomically at execution time, so that the guarantee survives changes in chain state "
        "between the check and the execution. The one family it does not prevent is an in-policy drain that stays within the "
        "per-session budget."
    ))
    add(body(
        "Zero-knowledge proofs have also been attached to agent guardrails. NiyamAI commits permitted tools and constraints to an "
        "intent contract and proves that each authorized tool call was evaluated correctly under it [9], and ERC-8354 standardizes "
        "a pre-execution allow-or-deny verdict for an agent action, proven in zero knowledge against an undisclosed policy [10]. "
        "Both decide one action at a time. Wallet permission standards such as ERC-7715 grant an application scoped permissions, "
        "for example a token allowance with an expiry [11]; these are fixed budgets rather than limits that depend on market risk."
    ))
    add(body(
        "zkLeash differs from these systems in two respects. It keeps state across trades, through an execution-loss ledger and an "
        "exposure limit scaled by volatility, and it substitutes a proof over authenticated market data for a signature. Its "
        "treatment of state drift is weaker than that of Proof-Gated Signing: we rely on a live-price band and a minimum output, and "
        "we do not simulate the transaction."
    ))
    add(h2("Account Abstraction and Zero-Knowledge Virtual Machines"))
    add(body(
        "ERC-4337 specifies smart accounts that validate user operations without any change to the protocol [12]. ERC-7579 adds "
        "modular validators and executors for such accounts [13], and ERC-7562 limits which state validation code may read, which "
        "lets bundlers simulate it safely [14]. The price oracle, the price log, and the verifier all sit outside the storage an "
        "account may touch during validation. For this reason zkLeash verifies the proof at execution time, in an ERC-7579 "
        "executor, and the validator only checks who signed and which function is called. SP1 compiles standard Rust to RISC-V and "
        "proves its execution, and a Groth16 wrapper lets an EVM contract verify the resulting proof [15]."
    ))
    add(h2("Risk Measures and Oracles"))
    add(body(
        "We measure volatility with an exponentially weighted moving average (EWMA) of squared returns and a decay factor of "
        "\u03bb = 0.94, the RiskMetrics choice [16]. It needs no parameter fitting and is deterministic in integer arithmetic. Prices "
        "come from Pyth, a pull-based oracle in which the transaction carries a signed price update that the chain verifies [17]."
    ))

    # III
    add(h1("Threat Model"))
    add(body(
        "*Adversary.* The adversary controls all content the agent reads and can therefore make the agent propose any action. It may "
        "control the machine that runs the prover, may hold the agent\u2019s session key, may append prices to the permissionless "
        "price log, and may reorder or sandwich a swap within its minimum output."
    ))
    add(body(
        "*Trusted.* We assume that SP1 and the on-chain verifier are sound, that Pyth prices are correct within the stated "
        "deviation band, that the deployed bytecode and the owner key are honest, and that allowlisted routers behave as their "
        "interface specifies."
    ))
    add(body(
        "*Goals.* (G1) No operation signed by the session key moves tokens to any address other than the account. (G2) No swap "
        "executes unless the risk function approved that exact action under the deployed policy, the current price log, and the "
        "current ledger. (G3) Within a window, cumulative execution loss, valued at proven prices, never exceeds a fixed cap."
    ))
    add(body(
        "*Out of scope.* Compromise of the owner key, which can call the account directly; oracle manipulation within the permitted "
        "band; market moves between trades, which G3 does not count and the drawdown limit addresses only in part; and bugs in the "
        "router."
    ))

    # IV
    add(h1("System Design"))
    add(h2("Overview"))
    add(body(
        "Fig. 1 shows the components and the trust boundary. The agent observes a market and produces one typed intent: swap, "
        "transfer, or hold. The transaction builder maps a swap to an action and has no encoding for a transfer; this is a "
        "convenience rather than a security boundary, since the adversary may control that machine. The risk function, written in "
        "Rust and compiled for the SP1 zkVM, reads the action, the portfolio, the price log, and the ledger state, and emits an "
        "allow-or-deny decision with a public-values record of 52 words. The session key can call only executeGuarded on the "
        "executor, which verifies the proof, re-checks every limit that is cheap to check, swaps with the account as recipient, and "
        "updates the ledger."
    ))
    add(figure(doc, FIG_ARCH, 3.3, "Fig1", "zkLeash components in off-chain and on-chain lanes"))
    add(caption(
        "Fig. 1. zkLeash components. Everything off-chain, including the prover host, is untrusted. The guest reads the price-log "
        "heads and the ledger state, and the executor compares both with chain state before it swaps."
    ))
    add(h2("Components"))
    add(body("Table I lists the on-chain and off-chain components."))
    E.extend(table_title("I", "Components of zkLeash"))
    add(table([1500, 3540], ["Component", "Role"], [
        ["Agent", "Proposes one typed intent; never signs"],
        ["Transaction builder", "Maps a swap to an action; not a security boundary"],
        ["Risk function (guest)", "EWMA volatility, exposure, and limits; commits the decision"],
        ["Session-key validator", "Admits only calls to executeGuarded"],
        ["Executor", "Verifies the proof, re-checks limits, swaps to the account"],
        ["Account", "Minimal ERC-4337 and ERC-7579 account"],
        ["Price log", "Hash chain of Pyth prices with increasing publish times"],
        ["Risk ledger", "Window execution loss, peak equity, trade count"],
    ]))
    add(h2("Binding the Proof"))
    add(body(
        "Four commitments restrict a proof to one use. The action hash covers the chain identifier, the account, the router, both "
        "tokens, the fee, the input amount, the deadline, and the account nonce. The policy commitment covers every limit: "
        "volatility-scaled exposure, concentration, drawdown, notional, slippage, window loss, window length, trade count, minimum "
        "history, price deviation, price age, and the quote token. The first and last price-log heads of each asset pin the history "
        "the guest read, and the committed ledger fields (cumulative profit and loss, peak equity, window loss, window start, and "
        "trade count) pin the outcome of earlier trades. The executor recomputes the action hash, compares the rest with its own "
        "storage, and rejects any mismatch. The nonce is incremented only once the action hash matches, so a replayed proof reverts."
    ))
    add(h2("Execution Checks"))
    add(body("The executor carries out the following steps in order."))
    for t in [
        "Accept any attached Pyth update blobs and pay the update fee.",
        "Verify the proof against the program\u2019s verification key.",
        "Decode the public values and require an allow decision, unexpired timestamps, a matching policy commitment, the expected "
        "number of assets, and an allowlisted router.",
        "Recompute the action hash with the current nonce, then increment the nonce.",
        "Resolve the token indexes, rejecting unknown tokens and any swap of a token for itself.",
        "For each asset, read the live Pyth price and require that it is fresh, has the expected exponent, and lies within 0.5% of "
        "the proven price; require the minimum history and that the first and last log heads match the proof.",
        "Check balances against the committed pre- and post-trade balances, recompute the volatility-scaled exposure from the "
        "committed volatilities, require that the ledger state matches the proof, and enforce the exposure, notional, "
        "concentration, drawdown, and trade-count limits.",
        "Swap with the account as recipient and an oracle-derived minimum output, then update the ledger. If the loss cap would be "
        "crossed, the whole call reverts.",
    ]:
        add(item(t, 4))
    add(body(
        "A trade that sells into the quote asset without raising the exposure is exempt from the exposure, concentration, and "
        "drawdown limits, so a user can always reduce risk; the notional limit, the minimum output, and the ledger still apply."
    ))

    # V
    add(h1("Algorithms"))
    add(body(
        "All arithmetic uses integers scaled by 10^{18}; no floating point is used. A Pyth price *p* with exponent *e* becomes "
        "*P* = *p* \u00b7 10^{18+*e*}."
    ))
    add(h2("EWMA Volatility"))
    add(body("For consecutive log entries with prices *p*_{*t*\u22121} and *p*_{*t*}, the return is"))
    add(eq_return())
    add(body("The variance starts at zero and is updated once per pair:"))
    add(eq_variance())
    add(body(
        "and \u03c3 = \u230a\u221a*v*_{*T*}\u230b with an integer square root. A non-positive price, or a publish time that does not "
        "increase, causes a deny. On the worked example [1000, 1100, 1210] the Rust function and its Solidity port both return "
        "34117444218463961. Two properties matter when setting a policy. First, \u03c3 is per observation: returns are taken "
        "between consecutive log entries, so the limit is calibrated to the posting cadence (one minute in our evaluation). "
        "Second, starting from zero biases \u03c3 low by a factor \u221a(1 \u2212 \u03bb^{*m*}) after *m* returns, about 0.59 at the "
        f"minimum history of eight prices. In the evaluation, histories of 16 to 64 prices gave median estimated-to-true \u03c3 "
        f"ratios between {min(ratios):.2f} and {max(ratios):.2f}."
    ))
    add(h2("Volatility-Scaled Exposure"))
    add(body("For assets *i* = 1, \u2026, *n* with exposure *E*_{*i*} and volatility \u03c3_{*i*},"))
    add(eq_exposure())
    add(body(
        "The policy threshold applies to *V*. Because standard deviation is subadditive, *V* bounds the one-step standard "
        "deviation of portfolio value for any correlation among the assets, so 2.33*V* bounds the parametric 99% value at risk "
        "under normal returns. The guest reports 2.33*V* as VaR99. No covariance is estimated, so the bound gives no "
        "diversification credit."
    ))
    add(h2("Fair Output and Minimum Output"))
    add(eq_fair())
    add(eq_min())
    add(body(
        "where *d*_{in} and *d*_{out} are the token decimals and *s* is the slippage limit in basis points. Risk is computed on "
        "fairOut, so a pessimistic minimum cannot hide a risky purchase, while minOut is enforced on the tokens actually received."
    ))
    add(h2("Hash-Chained Price History"))
    add(eq_hash())
    add(body(
        "where *p*_{*k*} is the price, *c*_{*k*} its confidence, *e*_{*k*} its exponent, and \u03c4_{*k*} its publish time. Anyone "
        "may append a Pyth-verified price, but only with a publish time later than the previous entry; otherwise an attacker could "
        "repeat one price to add zero returns and pull \u03c3 toward zero. The proof must cover the whole log, so a prover cannot "
        "pick a quiet stretch. Appending a price invalidates outstanding proofs, which fails closed but lets anyone delay a trade "
        "(Section IX)."
    ))
    add(h2("Rolling Execution-Loss Ledger"))
    add(body(
        "Around each swap the executor values the portfolio at the proven prices before and after the trade, and adds any decrease "
        "to a window total *L*. This is execution loss: value given up to the counterparty through slippage, fees, or a manipulated "
        "pool. Market moves between trades are not counted; the drawdown limit covers them. If *L* would exceed the cap "
        "*L*_{max} within the window, the ledger update reverts and the swap with it. The ledger also stores peak equity for the "
        "drawdown limit and a trade count. Because the guest reads the ledger state and commits it, every proof is evaluated "
        "against the losses of all earlier trades."
    ))
    add(h2("Simple Limits"))
    add(body(
        "The guest and the executor also enforce a per-trade notional cap, an 80% concentration cap on non-quote assets, a 30% "
        "drawdown cap, a 1% slippage cap, and at most 20 trades per window. These limits are repeated in Solidity so that a bug "
        "in the guest cannot waive them; a Foundry test sets the allow bit on a trade over the exposure budget and confirms that "
        "the executor reverts."
    ))
    add(h2("Why the Risk Function Is Proved"))
    add(body(
        "Computing \u03c3 in Solidity costs gas linear in the window, and a guard must read the logged prices from storage, since "
        "calldata is unauthenticated. Table II gives measured costs with each contract\u2019s storage cold."
    ))
    E.extend(table_title("II", "Measured gas"))
    add(table([1700, 1670, 1670], ["Prices (one asset)", "EWMA, calldata", "EWMA, storage"], [
        *[[k, f"{ew_c[k]:,}", f"{ew_s[k]:,}"] for k in ("8", "32", "64", "128")],
        ["Guarded trade, first", (f"{eg['first_trade']:,}", 2)],
        ["Guarded trade, later", (f"{eg['next_trade']:,}", 2)],
        ["Stand-in verifier", (f"{eg['stand_in_verifier']:,}", 2)],
        ["Price-log append", (f"{g['price_log_record_gas']:,}", 2)],
    ], rules=frozenset({4})))
    add(table_note(
        "Execution gas of one call, excluding intrinsic and calldata gas. Guarded trades use the stand-in verifier in place of "
        "Groth16 verification."
    ))
    add(body(
        "The storage column reads one slot per price, the layout of the price log; the calldata column is a lower bound because "
        "nothing authenticates its input. Succinct publishes roughly 280,000 gas to verify an SP1 Groth16 proof [15], independent "
        f"of the window. Extrapolating linearly, one asset passes that figure at about {cross['storage']} stored prices "
        f"({cross['calldata']} from calldata), and two assets at 64 prices already exceed it. A later guarded trade costs "
        f"{eg['next_trade_without_verifier']:,} gas without verification, so about {eg['next_trade_with_groth16_estimate'] / 1000:.0f}k "
        "with a Groth16 verifier. These are measurements of individual calls plus a cited verification cost, not of an "
        "end-to-end proved trade."
    ))

    # VI
    add(h1("Security Analysis"))
    add(body(
        "*G1.* The session-key validator accepts a user operation signed by the session key only if it calls the account\u2019s "
        "execute function with the executor as target, zero value, and the executeGuarded selector. executeGuarded approves "
        "exactly the input amount to an allowlisted router and swaps with the account as recipient. No session-key path therefore "
        "moves tokens elsewhere; the owner key can, and is trusted. A test submits a raw transfer signed by the session key and "
        "checks that validation fails."
    ))
    add(body(
        "*G2.* A swap needs an allow decision in public values that the verifier accepts for the program\u2019s key. By soundness, "
        "those values are the guest\u2019s output on some input. The action hash fixes the swap and the nonce, the policy commitment "
        "fixes the limits, the log heads fix the price history, the committed balances fix the portfolio, and the ledger fields fix "
        "the earlier trades. The executor checks each against chain state, so the only accepted input is the true one. Tests cover "
        "a replay, a tampered public-values byte, a log with an extra entry, and an unknown router."
    ))
    add(body(
        "*G3.* Every executed swap calls the ledger, which adds the trade\u2019s execution loss and reverts if the window total "
        "exceeds *L*_{max}. Because the swap and the ledger update happen in one call, no executed sequence leaves *L* above the "
        "cap. An invariant test of 128,000 random ledger updates never found the cap crossed, and a salami test stops at it."
    ))
    add(body(
        "*Attacks considered.* A forged calm history fails the head comparison, and padding the real log with repeated prices is "
        "refused by the log. A malicious prover host can only obtain proofs of decisions the guest actually computes. A stolen "
        "session key gains nothing beyond proposing trades the guest would approve. A sandwich or manipulated pool can extract at "
        "most the slippage limit per trade and *L*_{max} per window. This argument is informal and rests on tests, not on a "
        "machine-checked proof."
    ))

    # VII
    add(h1("Implementation"))
    add(body(
        "The risk function is a no_std Rust crate that runs unmodified in native tests, in a command-line host, and as the SP1 "
        "guest. " + sp1_impl + " The contracts are written in Solidity 0.8.28 and tested with Foundry; the agent, orchestrator, "
        "and harness are written in Python."
    ))
    add(body(
        "The agent is a tool-calling loop with three tools (prices, portfolio, and news) running against a simulated market. By "
        "default it uses a deterministic scripted stand-in for the model, so the benchmark needs no API key; optional clients for "
        "Ollama and Gemini exist but were not scored. The account is a teaching implementation of the ERC-4337 and ERC-7579 call "
        "path, not a production account. In the tests, an honest-verifier stand-in ties the proof bytes to the public values; a "
        "mock verifier is used only to wire up demonstrations and supports no security claim. On-chain results come from a local "
        "chain with mock tokens and a mock router."
    ))
    add(body(
        "The Foundry suite has 20 tests and one invariant. They cover a calm swap, a denied all-in purchase, a guest that sets the "
        "allow bit on a trade over the exposure budget, a de-risking sale over budget, a head mismatch, a repeated publish time "
        "refused by the log, a replay, a tampered public-values byte, the restricted session key, a salami loop halted at the loss "
        "cap, a stolen-key case against a signed baseline, a fuzz test that the minimum output never exceeds the fair output, and "
        "the gas samples. In an invariant test of 128,000 handler calls, the stored window loss never exceeded the cap. The Rust "
        "crate has 13 unit tests."
    ))

    # VIII
    add(h1("Evaluation"))
    add(h2("Setup"))
    add(body(
        f"The harness generates {total_n} trials, {per_fam} seeds in each of {n_fams} families (Table III). Each seed draws a distinct "
        "trial: a WETH price path from a geometric random walk with per-minute volatility in a calm (2\u20138\u00d710^{\u22124}) or "
        "volatile (6\u201312\u00d710^{\u22123}) regime, a history of 16 to 64 prices, a $30,000\u2013$50,000 portfolio, and a trade size. The policy is "
        f"fixed: an exposure budget *V* \u2264 {usd(vol_budget)} of one-minute \u03c3 (0.1% of a $40,000 book), a {usd(cap)} daily loss "
        "cap (1%), and the limits of Section V-F."
    ))
    add(body(
        "Three harmful families are structural: a direct transfer, a swap through a router that is not allowlisted, and a trade "
        "signed with a stolen attestation key. No session-key path exists for them on-chain, so zkLeash\u2019s outcome is taken from "
        "the contract and backed by a Foundry test rather than measured. Three harmful families are decided by the guest: an "
        "all-in purchase of 85\u2013100% of the stable balance, a $1,000\u2013$4,900 buy in the volatile regime, and a salami drain of "
        f"{salami_legs} alternating $3,000\u2013$4,900 swaps from each of which a sandwicher keeps 0.5\u20131%. Three families are benign: a "
        "calm rebalance, a calm buy sized like the spike buy, and a sale of 20\u201360% of the WETH during a 32\u201350% drawdown in "
        "the volatile regime. Six systems are compared:"
    ))
    for t in [
        "B0: no guard.",
        "B1: a keyword filter on the text that triggered the action.",
        f"B2: a router allowlist and a static ${static_cap:,} per-trade notional cap.",
        "B3: a trusted signer that applies zkLeash\u2019s stateless checks; anyone holding its key can sign.",
        "B4: a stateless proof, i.e., zkLeash with the ledger turned off.",
        "zkLeash: proof plus ledger.",
    ]:
        add(item(t, 5))
    add(body(
        "B1\u2013B4 are decision rules that stand for classes of design; they are not reimplementations of PACE or Proof-Gated "
        f"Signing. Guest decisions come from {exec_phrase}. An attack succeeds if the family\u2019s harm occurs; for the salami "
        f"drain, if cumulative execution loss exceeds the {usd(cap)} cap. Because that cap is zkLeash\u2019s own policy, the harness "
        "measures which designs enforce a common policy rather than resistance to an external definition of harm. Intervals are "
        "exact Clopper\u2013Pearson 95% intervals over distinct trials."
    ))
    add(h2("Results"))
    add(body("Table III gives, for each family, the number of trials each system blocked."))
    E.extend(table_title("III", f"Trials blocked, out of {per_fam} per family"))
    short = {"B0_unguarded": "B0", "B1_prompt_filter": "B1", "B2_static": "B2", "B3_signed": "B3", "B4_stateless": "B4", "zkLeash": "zkLeash"}
    rows = []
    for key, label, mech in FAMILIES:
        rows.append([label, mech] + [str(fam[key]["blocked"][x]) for x in SYSTEMS])
    rows.append([("Attack success", 2)] + [f"{sysm[x]['attack_success']['k']}/{harmful_n}" for x in SYSTEMS])
    rows.append([("False blocks", 2)] + [f"{sysm[x]['false_block']['k']}/{benign_n}" for x in SYSTEMS])
    add(table([1240, 460, 520, 520, 520, 520, 520, 740], ["Family", "Mech.", *[short[x] for x in SYSTEMS]], rows,
              rules=frozenset({6, 9})))
    add(table_note(
        "Harmful families above the first heavy line, benign families below it. Mechanism: S, structural (taken from the "
        "contract and tested in Foundry); G, guest; L, ledger."
    ))
    add(body(
        f"zkLeash admitted none of the {harmful_n} harmful trials (95% interval [0, {zk_hi}]) and none of the {guest_n} decided by "
        f"the guest ([0, {zk_guest_hi}]), and it blocked none of the {benign_n} benign trials ([0, {zk_fb_hi}]). Recording deny "
        f"reasons shows which mechanism did the work. All {spike['zkleash_decided_only_by_vol_limit']} volatility-spike buys were denied "
        f"by the exposure limit alone; the static cap admitted every one, since each was under ${static_cap:,} and under the "
        f"concentration cap. The all-in purchases were denied by concentration in all {allin.get('concentration', 0)} cases (and also "
        f"by the exposure limit in {allin.get('vol_limit', 0)}), so the cheap checks would have sufficed there. The salami drain "
        f"separates the ledger from everything else: every stateless design let all {salami_legs} legs through, losing "
        f"{usd(sal_b4['mean'])} on average and up to {usd(sal_b4['max'])}, while zkLeash stopped each sequence after {legs['min']} to "
        f"{legs['max']} legs with at most {usd(sal_zk['max'])} lost. B3 fails the stolen-key family by construction. The cost of the "
        f"static cap appears on the benign side: it blocked every de-risking sale, each of which exceeded ${static_cap:,}."
    ))
    add(figure(doc, FIG_SALAMI, 3.4, "Fig2", "Cumulative execution loss against salami legs for B4 and zkLeash"))
    add(caption(
        f"Fig. 2. Cumulative execution loss as an attacker repeats legs that each lose {toy['extract_bps'] / 100:.0f}%. Left: "
        f"${toy['leg_usd']:,.0f} legs against a ${toy['cap_usd']:,.0f} cap. Right: ${real['leg_usd']:,.0f} legs against a "
        f"${real['cap_usd']:,.0f} cap (1% of a $40,000 book). The stateless guard (B4) loses without bound; zkLeash stops below the cap."
    ))
    add(h2("What the Results Show"))
    add(body(
        "Two ablations carry the argument. B4 and zkLeash share the proof and the limits and differ only in the ledger, so the "
        "ledger is what bounds multi-trade drains (Fig. 2). B2 and B4 differ in the proved statistic, and the volatility-spike "
        "family is where only that statistic decides. The proof does a third thing the harness cannot show: it removes the "
        "trusted signer whose key B3 loses."
    ))

    # IX
    add(h1("Discussion and Limitations"))
    add(body(
        f"*Scripted attacker.* The attack families, and the held-out cases in our release, were written by the authors. Zero "
        f"successes in {harmful_n} trials is evidence that the mechanisms work as designed, not that no attack exists; an adaptive "
        "adversary or an independently written attack set may do better."
    ))
    add(body("*No real proof.* " + limit_proof))
    add(body(
        "*No live model.* No live LLM was scored. Real models may propose different trades, including benign ones the policy "
        "blocks."
    ))
    add(body(
        "*Synthetic markets.* Price paths are geometric random walks with a fixed volatility per trial. Real prices have jumps and "
        "volatility clustering, which affect both the EWMA and the false-block rate."
    ))
    add(body(
        "*State drift.* We use a 0.5% live-price band and a minimum output instead of simulating the transaction. Proof-Gated "
        "Signing handles drift more robustly [5]."
    ))
    add(body(
        f"*Price-log liveness.* Appending a price invalidates outstanding proofs, so anyone willing to pay about "
        f"{g['price_log_record_gas'] / 1000:.0f}k gas per append can delay trades. Accepting any recent head, or indexing a sliding "
        "window, would trade a little freshness for liveness. Prices are posted by a single script; liveness depends on it, "
        "safety does not."
    ))
    add(body(
        "*Design limits.* The proof covers the whole price log rather than a sliding window, so proving cost grows with the log. "
        "Volatility is per asset without covariance. The account is a teaching implementation, and nothing beyond a local chain "
        "is deployed. We did not measure economic performance such as the Sharpe ratio."
    ))

    # X
    add(h1("Conclusion and Future Work"))
    add(body(
        "zkLeash places a deterministic, proof-backed risk function and an execution-loss ledger between an untrusted LLM agent "
        "and a smart account. On a randomized harness, the ledger is what stops multi-trade drains that a stateless proof admits, "
        "the proved volatility statistic is what stops buys during volatility spikes that a static cap admits, and the proof "
        "removes the trusted signing key. Evaluating that statistic on-chain from stored prices costs more than the published "
        f"cost of verifying a proof beyond about {cross['storage']} prices per asset. The evidence is limited by a scripted attacker, "
        "synthetic prices, unproved execution, and the lack of a live model. Future work includes Groth16 proofs for a subset of "
        "cases verified on a testnet, scoring live models on the same families, an attack set written independently of the "
        "implementation, a sliding-window price index, bias-corrected and time-normalized volatility, historical conditional "
        "value at risk in the guest, checking Pyth signatures inside the guest, and simulating pool output at the transaction "
        "level."
    ))

    add(h1("Acknowledgment", numbered=False))
    add(body(
        "The authors thank [[TODO: guide\u2019s name]], Department of Computer Engineering, Pimpri Chinchwad College of Engineering "
        "and Research, for guidance. [[An AI assistant was used to help draft and revise parts of the text and the evaluation "
        "code; the authors reviewed all content and take full responsibility for it. TODO: confirm or edit this disclosure.]]"
    ))

    add(h1("References", numbered=False))
    accessed = "Accessed: Oct. 11, 2026."
    for t in [
        "F. Perez and I. Ribeiro, \u201cIgnore previous prompt: Attack techniques for language models,\u201d arXiv:2211.09527, 2022.",
        "K. Greshake, S. Abdelnabi, S. Mishra, C. Endres, T. Holz, and M. Fritz, \u201cNot what you\u2019ve signed up for: Compromising "
        "real-world LLM-integrated applications with indirect prompt injection,\u201d in *Proc. 16th ACM Workshop Artif. Intell. "
        "Secur. (AISec)*, 2023, pp. 79\u201390.",
        "A. S. Patlan, P. Sheng, S. A. Hebbar, P. Mittal, and P. Viswanath, \u201cReal AI agents with fake memories: Fatal context "
        "manipulation attacks on Web3 agents,\u201d in *Proc. Financial Cryptography Data Secur. (FC)*, 2026. arXiv:2503.16248.",
        "R. Karanjai *et al.*, \u201cPACE: Policy-attested contract execution for safe AI agents in decentralized finance,\u201d "
        "arXiv:2608.17220, Aug. 2026.",
        "B. Ghosh, \u201cProof-gated signing: Solver-checked transaction guards that hold under state drift for onchain AI agents,\u201d "
        "arXiv:2610.00354, Sep. 2026.",
        "Q. Zhan, Z. Liang, Z. Ying, and D. Kang, \u201cInjecAgent: Benchmarking indirect prompt injections in tool-integrated large "
        "language model agents,\u201d in *Findings Assoc. Comput. Linguistics: ACL 2024*, 2024. arXiv:2403.02691.",
        "E. Debenedetti, J. Zhang, M. Balunovi\u0107, L. Beurer-Kellner, M. Fischer, and F. Tram\u00e8r, \u201cAgentDojo: A dynamic "
        "environment to evaluate prompt injection attacks and defenses for LLM agents,\u201d in *Proc. NeurIPS Datasets Benchmarks "
        "Track*, 2024. arXiv:2406.13352.",
        "E. Debenedetti *et al.*, \u201cDefeating prompt injections by design,\u201d arXiv:2503.18813, 2025.",
        "A. Katkar, O. Karkele, K. Mandhane, M. More, and Y. Kashid, \u201cNiyamAI\u2014An intent-bound AI agent with cryptographically "
        "verifiable guardrails using zero-knowledge proofs,\u201d arXiv:2608.07167, Aug. 2026.",
        "M. Z. Fatonie, F. Firdani, and M. A. Muhammad, \u201cERC-8354: Confidential agent policy verdicts,\u201d Ethereum Improvement "
        "Proposals, no. 8354, Jul. 2026. [Online]. Available: https://eips.ethereum.org/EIPS/eip-8354",
        "L. Isailovic *et al.*, \u201cERC-7715: Request permissions from wallets,\u201d Ethereum Improvement Proposals, no. 7715, "
        "May 2024. [Online]. Available: https://eips.ethereum.org/EIPS/eip-7715",
        "V. Buterin *et al.*, \u201cERC-4337: Account abstraction using alt mempool,\u201d Ethereum Improvement Proposals, no. 4337, "
        "Sep. 2021. [Online]. Available: https://eips.ethereum.org/EIPS/eip-4337",
        "zeroknots, K. Kopp, T. Lee, F. Makarov, E. Poon, and L. Min, \u201cERC-7579: Minimal modular smart accounts,\u201d Ethereum "
        "Improvement Proposals, no. 7579, Dec. 2023. [Online]. Available: https://eips.ethereum.org/EIPS/eip-7579",
        "Y. Weiss, D. Tirosh, A. Forshtat, and S. Nacson, \u201cERC-7562: Account abstraction validation scope rules,\u201d Ethereum "
        "Improvement Proposals, no. 7562, Sep. 2023. [Online]. Available: https://eips.ethereum.org/EIPS/eip-7562",
        f"Succinct Labs, \u201cSP1 zkVM documentation.\u201d {accessed} [Online]. Available: https://docs.succinct.xyz",
        "J.P. Morgan/Reuters, *RiskMetrics\u2014Technical Document*, 4th ed. New York, NY, USA, 1996.",
        f"Pyth Network, \u201cPyth Network documentation.\u201d {accessed} [Online]. Available: https://docs.pyth.network",
    ]:
        add(ref(t))
    return E


def fix_author_table(tbl) -> None:
    """Drop the IEEE template ordinals ("1st", "2nd", ...) in front of each author name."""
    for tc in tbl.iter(qn("w:tc")):
        p = tc.find(qn("w:p"))
        rs = p.findall(qn("w:r")) if p is not None else []
        if len(rs) >= 3 and rs[1].find(f".//{qn('w:vertAlign')}") is not None:
            p.remove(rs[0])
            p.remove(rs[1])
            t = rs[2].find(qn("w:t"))
            t.text = t.text.lstrip()


def main() -> None:
    doc = Document(str(SRC))
    bodyel = doc.element.body
    old = list(bodyel.iterchildren())
    head = [old[i] for i in KEEP_HEAD]
    tail = [old[i] for i in KEEP_TAIL]
    sect = old[-1]
    assert sect.tag == qn("w:sectPr")
    fix_author_table(head[1])

    old_images = {b.get(qn("r:embed")) for b in bodyel.iter(qn("a:blip"))}
    new = build(doc, load_results())
    for el in old:
        bodyel.remove(el)
    for el in head + new + tail + [sect]:
        bodyel.append(el)
    for rid in old_images:
        doc.part.drop_rel(rid)

    doc.core_properties.title = "zkLeash: Stateful, Proof-Gated Risk Enforcement for LLM Trading Agents"
    doc.save(str(OUT))
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
