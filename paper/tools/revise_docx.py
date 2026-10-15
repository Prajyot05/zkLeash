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
import zipfile
from copy import deepcopy
from pathlib import Path
from xml.sax.saxutils import escape

from docx import Document
from docx.oxml import parse_xml
from docx.oxml.ns import qn
from docx.shared import Inches

ROOT = Path(__file__).resolve().parents[2]
_revised = ROOT / "zkLeash_IEEE_paper_revised.docx"
SRC = _revised if _revised.exists() else ROOT / "zkLeash_IEEE_paper_v3.docx"
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


BODY_PPR = '<w:spacing w:before="0" w:after="0"/><w:ind w:firstLine="288"/><w:jc w:val="both"/>'


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
    return item(text, 6, sz=16, after=20)


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


def cell(text: str, width: int, header=False, align="center", span=1, top_rule=False, sz=16, pad=60) -> str:
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
        f'<w:tcMar><w:top w:type="dxa" w:w="20"/><w:left w:type="dxa" w:w="{pad}"/>'
        f'<w:bottom w:type="dxa" w:w="20"/><w:right w:type="dxa" w:w="{pad}"/></w:tcMar>'
        '<w:vAlign w:val="center"/></w:tcPr>'
    )
    content = run(text, sz=sz, sc=True) if header else runs(text, sz=sz)
    return f'<w:tc>{tcpr}<w:p><w:pPr><w:spacing w:after="0"/><w:jc w:val="{align}"/></w:pPr>{content}</w:p></w:tc>'


def table(widths: list[int], header: list[str], rows: list[list], rules: frozenset = frozenset(), sz=16, pad=60):
    """rows: lists of str or (str, span); first column left-aligned. rules: row indexes with a heavy top line."""
    grid = "".join(f'<w:gridCol w:w="{w}"/>' for w in widths)
    trs = ['<w:tr><w:trPr><w:cantSplit/><w:tblHeader/></w:trPr>'
           + "".join(cell(h, widths[k], header=True, sz=sz, pad=pad) for k, h in enumerate(header)) + "</w:tr>"]
    for r, row in enumerate(rows):
        cells, col = [], 0
        for c in row:
            text, span = c if isinstance(c, tuple) else (c, 1)
            w = sum(widths[col:col + span])
            cells.append(cell(text, w, align="left" if col == 0 else "center", span=span, top_rule=r in rules, sz=sz, pad=pad))
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
    crash_path = RESULTS / "crash_replay.json"
    crash = json.loads(crash_path.read_text()) if crash_path.exists() else None
    trade_cap = None
    salami_extra = None
    trials_path = RESULTS / "trials.jsonl"
    if trials_path.exists():
        stopped = []
        salami_losses = []
        trade_cap_stops = 0
        trades_cap = int(summary["config"]["policy"]["max_trades_per_window"])
        loss_cap = float(summary["config"]["policy"]["max_window_loss"])
        for line in trials_path.read_text().splitlines():
            row = json.loads(line)
            if row["family"] == "fair_turnover" and row["systems"]["zkLeash"]:
                stopped.append(row["loss_usd"]["zkLeash"])
            if row["family"] == "salami":
                loss = float(row["loss_usd"]["zkLeash"])
                salami_losses.append(loss)
                if int(row["legs_executed"]["zkLeash"]) == trades_cap and loss < loss_cap:
                    trade_cap_stops += 1
        if stopped:
            trade_cap = {"n": len(stopped), "max_loss": max(stopped)}
        if salami_losses:
            salami_extra = {"loss_min": min(salami_losses), "n": len(salami_losses), "trade_cap_stops": trade_cap_stops}
    return {
        "s": summary, "g": gas, "sp1": sp1, "crash": crash,
        "trade_cap": trade_cap, "salami_extra": salami_extra,
    }


WORDS = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten"}


def pct(x: float) -> str:
    return "0" if x == 0 else f"{100 * x:.1f}%"


def ci_text(bounds) -> str:
    lo, hi = bounds
    return f"[{pct(lo)}, {pct(hi)}]"


def word_count(text: str) -> int:
    return len(text.split())


def usd(x: float) -> str:
    return f"${x:,.0f}"


# ---------------------------------------------------------------------------
# The paper.


SYSTEMS = [
    "B0_unguarded", "B1_prompt_filter", "B2_static", "B3_signed", "B4_stateless", "B5_daily_notional", "zkLeash",
]
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
    ("fair_turnover", "Fair turnover", "G+L"),
]


def _end(curve: list) -> float:
    return curve[-1] if curve else 0.0


def build(doc, R: dict) -> list:
    s, g, sp1 = R["s"], R["g"], R["sp1"]
    crash, trade_cap, salami_extra = R["crash"], R["trade_cap"], R["salami_extra"]
    sysm = s["systems"]
    fam = s["per_family"]
    zk = sysm["zkLeash"]
    b5 = sysm["B5_daily_notional"]
    measured_n = zk["attack_success"]["n"]
    structural_n = zk["structural_blocked"]["n"]
    benign_n = zk["false_block"]["n"]
    total_n = measured_n + structural_n + benign_n
    per_fam = fam["salami"]["n"]
    n_fams = WORDS.get(len(fam), str(len(fam)))
    zk_hi = pct(zk["attack_success"]["ci95"][1])
    zk_fb = zk["false_block"]["k"]
    zk_fb_hi = pct(zk["false_block"]["ci95"][1])
    b5_fb = b5["false_block"]["k"]
    sal = fam["salami"]
    sal_b4 = sal["loss_usd_B4_stateless"]
    sal_b5 = sal["loss_usd_B5_daily_notional"]
    sal_zk = sal["loss_usd_zkLeash"]
    legs = sal["legs_executed_ledger"]
    daily_legs = sal["legs_executed_daily"]
    cap = s["config"]["policy"]["max_window_loss"]
    notional_cap = s["config"]["policy"]["max_notional"]
    vol_budget = s["config"]["policy"]["max_vol_exposure"]
    static_cap = s["config"]["static_cap_usd"]
    daily_cap = s["config"]["daily_notional_usd"]
    salami_legs = s["config"]["salami_legs"]
    allin = fam["indirect_all_in"]["zkleash_deny_reasons"]
    spike = fam["vol_spike_buy"]
    ratios = [f.get("sigma_est_over_true_median") for f in fam.values() if f.get("sigma_est_over_true_median")]
    small, real = s["salami_curves"]["small_leg"], s["salami_curves"]["realistic"]
    fair = fam["fair_turnover"]
    derisk = fam["derisk_in_drawdown"]
    trades_cap = s["config"]["policy"]["max_trades_per_window"]
    ew_c, ew_s = g["ewma_calldata_gas"], g["ewma_storage_gas"]
    cross = g["single_asset_points_to_exceed_280k"]
    eg = g["execute_guarded_gas"]

    if sp1:
        rows = sp1["runs"]
        lo, hi = rows[0], rows[-1]
        all_same = all(r["identical"] for r in rows)
        per_price = (hi["cycles"] - lo["cycles"]) / (hi["points_per_asset"] - lo["points_per_asset"])
        sp1_impl = (
            "We compiled the guest with the SP1 toolchain and ran it in the SP1 executor, which runs the RISC-V program "
            f"without generating a proof, for histories of {lo['points_per_asset']} to {hi['points_per_asset']} prices per asset on the two-asset calm scenario. "
            "That sweep is not the benchmark in Section VIII. "
            + ("Its committed public values were byte-identical to native execution in every case. " if all_same else "")
            + f"Execution took {lo['cycles']:,} RISC-V cycles at {lo['points_per_asset']} prices per asset and {hi['cycles']:,} at {hi['points_per_asset']}. "
            f"Dividing that difference by the {hi['points_per_asset'] - lo['points_per_asset']} extra prices gives {per_price:,.0f} cycles "
            "for each additional price on each of two assets."
        )
        exec_phrase = (
            "native execution of the guest crate. The SP1 executor runs reported in Section VII use the calm scenario, not these "
            f"{total_n} trials"
        )
        abstract_tail = (
            f"The {total_n} decisions are native guest runs. A separate calm scenario was executed in SP1 and not proved. "
            "The attacker is scripted, the only real path is one August 2024 ETH-USDT window, and no live model was scored."
        )
        limit_proof = (
            "No Groth16 proof was generated. The harness decisions are native runs of the guest crate. We also ran that crate in the "
            "SP1 executor on the calm scenario above, which gives cycle counts but not proving time, and we cite rather than measure "
            "verification gas. The tests use a stand-in verifier."
        )
    else:
        sp1_impl = "The harness runs the guest crate natively; we did not run the SP1 executor for the results reported here."
        exec_phrase = "native execution of the guest crate. Those runs are not SP1 executor runs"
        abstract_tail = (
            "The trial decisions are native guest runs, and the guest was not proved. "
            "The attacker is scripted, the only real path is one August 2024 ETH-USDT window, and no live model was scored."
        )
        limit_proof = (
            "No Groth16 proof was generated. Guest decisions come from native execution of the same crate, and the tests use a "
            "stand-in verifier. We report neither proving time nor measured verification gas."
        )

    E: list = []
    add = E.append

    abstract = (
        "LLM agents that can move cryptocurrency can lose funds irreversibly to a prompt injection or a bad numerical judgment. "
        "Guards that check one transaction and trust a signing key or a flat budget miss a drain of many allowed trades. zkLeash "
        "lets the agent\u2019s session key call one executor function, which swaps only if an SP1 guest, run on a hash-chained Pyth "
        "price log, approved the action and an on-chain execution-loss ledger still has room. The contract re-checks the inexpensive "
        f"limits, including a {usd(notional_cap)} per-trade notional cap. Of {total_n} trials, {structural_n} harmful cases are "
        "structural and stay out of the measured rate: a raw transfer has no session-key path, an unlisted router fails the allowlist, "
        f"and zkLeash has no attestation key to steal. On the other {measured_n}, zkLeash and a stateless proof plus an {usd(daily_cap)} "
        f"daily notional cap each admitted none (95% Clopper\u2013Pearson upper bound {zk_hi}). The cap false-blocked {b5_fb} of {benign_n} "
        f"benign trials. zkLeash false-blocked {zk_fb} of {benign_n} (95% interval {ci_text(zk['false_block']['ci95'])}), each stopped "
        f"by a {trades_cap}-trade cap. Without a cumulative limit the same proof lost up to {usd(sal_b4['max'])}, against a {usd(cap)} cap. "
        f"Stored-price EWMA costs {ew_s['8'] / 1000:.0f}k to {ew_s['128'] / 1000:.0f}k gas for 8 to 128 prices and exceeds a cited 280k "
        f"Groth16 verification near {cross['storage']} prices. " + abstract_tail
    )
    abstract_words = word_count(abstract)
    print(f"abstract words: {abstract_words}")
    if not 150 <= abstract_words <= 250:
        raise SystemExit(f"abstract is {abstract_words} words; keep an IEEE conference abstract between 150 and 250")
    add(front("Abstract", abstract))
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
        "slips past the per-trade rule. In PACE\u2019s adaptive study, a five-leg drain whose legs each stay under the cap is one of eight "
        "policy-valid cases that PACE and every baseline admit [4], and Proof-Gated Signing bounds an in-policy drain only through a "
        "per-session budget [5]. In addition, PACE "
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
        f"*An evaluation that isolates each mechanism.* On {total_n} seeded trials we separate structural cases, each backed by a "
        "Foundry test, from attacks the guest decides. A stateless proof admits multi-trade drains that the ledger bounds. A daily notional cap "
        "bounds them too, and we measure the benign turnover it refuses. The proved volatility statistic is what stops buys "
        "during volatility spikes, including one replayed from the August 2024 ETH unwind.", 3))
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
        "replay and expiry protection. A Solidity smart account validates the signatures on-chain. In the adaptive study, "
        "PACE and every baseline admit all 8 of 8 policy-valid but harmful cases (Table 4, seed 0). Those cases include a swap at the "
        "slippage bound, a transfer at the value cap, an approval to an allowlisted spender, and a five-leg drain whose legs each stay "
        "under the cap. The authors leave multi-step loops that compose policy-valid legs, and integration with ERC-4337 "
        "validateUserOp, as future work."
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
        f"minimum history of eight prices. On the guest families that record it, the per-family median ratio of estimated \u03c3 to the "
        f"random-walk \u03c3 runs from {min(ratios):.3f} to {max(ratios):.3f}. Those medians are not one shared history length."
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
        f"The guest and the executor also enforce a per-trade notional cap of {usd(notional_cap)}, an 80% concentration cap on non-quote "
        f"assets, a 30% drawdown cap, a 1% slippage cap, and at most {trades_cap} trades per window. These limits are repeated in Solidity so that a bug "
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
        "default it uses a deterministic scripted stand-in for the model, so the benchmark needs no API key. A proposal panel for "
        "one local Ollama model is included; no model server was available while preparing this draft, so no live model was scored. "
        "The account is a teaching implementation of the ERC-4337 and ERC-7579 call "
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
        f"The harness generates {total_n} trials, {per_fam} seeds in each of {n_fams} families (Table III). Each guest-decided seed draws "
        "a distinct WETH path from a geometric random walk, with per-minute volatility in a calm (2\u20138\u00d710^{\u22124}) or volatile "
        "(6\u201312\u00d710^{\u22123}) regime, a $30,000\u2013$50,000 portfolio, and a trade size. Histories are 32 to 64 prices, except the calm "
        "rebalance, which draws 16 to 64. The three structural families do not draw a price path. The policy is fixed: an exposure "
        f"budget *V* \u2264 {usd(vol_budget)} of one-minute \u03c3 (0.1% of a $40,000 book), a {usd(cap)} window-loss cap (1%), a "
        f"{usd(notional_cap)} per-trade notional cap, at most {trades_cap} trades in the window, and the other limits of Section V-F."
    ))
    add(body(
        f"Three harmful families are structural. The harness does not call the contract, each row is the fixed outcome of the named "
        "Foundry test, and only B1\u2019s keyword check varies with the seed. A direct transfer has no session-key path: the session key "
        "can call only executeGuarded, and that call swaps back to the account. An unlisted router fails the executor allowlist after "
        "verification. zkLeash has no attestation key, so the stolen-key row is blocked for zkLeash, B4, and B5 by construction; B3 is "
        "not blocked, matching the Foundry test in which that key signs any action. B2 is marked blocked on every structural row, "
        f"including stolen key, because the harness sets the router unlisted. That is not {per_fam} stolen-key executions. These "
        f"{structural_n} trials are outside the measured attack-success rate. The guest or the ledger decides the other harmful "
        f"families: an all-in purchase of 85\u2013100% of the stable balance, a $1,000\u2013$4,900 volatile buy, and a salami drain of "
        f"{salami_legs} alternating $3,000\u2013$4,900 swaps that give up 0.5\u20131%. Four families are benign: a calm rebalance, a calm buy "
        "sized like the spike buy, a sale of 20\u201360% of the WETH with the ledger peak set so that current equity is 32\u201350% below it "
        "(the price path is not that drawdown), and a day of $400\u2013$1,200 clips, at most 10 basis points of loss, with intended "
        "notional $3,000\u2013$20,000. Seven systems are compared:"
    ))
    for t in [
        "B0: no guard.",
        "B1: a keyword filter on the text that triggered the action.",
        f"B2: a router allowlist and a static ${static_cap:,} per-trade notional cap.",
        "B3: SignedAttestationGuard, a signature over the call. In the harness it signs the stateless guest decision; the stolen-key row is the Foundry test in which that key signs anything.",
        "B4: a stateless proof, zkLeash with the ledger turned off.",
        f"B5: B4 plus a rolling daily notional cap of ${daily_cap:,}. With the 1% slippage limit this implies an execution-loss bound of ${daily_cap * 0.01:,.0f}.",
        "zkLeash: proof plus the execution-loss ledger.",
    ]:
        add(item(t, 5))
    add(body(
        "B1\u2013B5 are decision rules that stand for classes of design. B3 is the signed-attestation contract in this repository, "
        "not a reimplementation of PACE, and B5 is not a reimplementation of Proof-Gated Signing\u2019s session budget. "
        f"Guest decisions come from {exec_phrase}. An attack succeeds when the family\u2019s harm occurs. For the salami drain, harm "
        f"is cumulative execution loss above the {usd(cap)} cap, which is zkLeash\u2019s own policy, so the comparison is about which "
        "designs enforce that policy. A benign trial is a false block when the system refuses the intended trade. Intervals are "
        "exact Clopper\u2013Pearson 95% intervals over distinct trials."
    ))
    add(h2("Results"))
    add(body(
        "Table III gives, for each family, how many of the 25 trials each system blocked. The measured attack-success row uses "
        f"only the {measured_n} harmful trials the guest or the ledger decided. The {structural_n} structural trials sit above "
        "that comparison."
    ))
    E.extend(table_title("III", f"Trials blocked, out of {per_fam}. Measured attack success excludes structural rows"))
    short = {
        "B0_unguarded": "B0", "B1_prompt_filter": "B1", "B2_static": "B2", "B3_signed": "B3",
        "B4_stateless": "B4", "B5_daily_notional": "B5", "zkLeash": "zk",
    }
    rows = []
    for key, label, mech in FAMILIES:
        rows.append([label, mech] + [str(fam[key]["blocked"][x]) for x in SYSTEMS])
    rows.append([("ASR, of " + str(measured_n), 2)] + [str(sysm[x]["attack_success"]["k"]) for x in SYSTEMS])
    rows.append([("False, of " + str(benign_n), 2)] + [str(sysm[x]["false_block"]["k"]) for x in SYSTEMS])
    # One column is 3.5 in. Counts, not fractions, so a cell never wraps "75/75" into a second line.
    add(table(
        [1360, 500, 454, 454, 454, 454, 454, 454, 456],
        ["Family", "M.", *[short[x] for x in SYSTEMS]],
        rows,
        rules=frozenset({3, 6, 10}),
        sz=14,
        pad=28,
    ))
    add(table_note(
        "Heavy lines separate structural harmful families, measured harmful families, and benign families. "
        "M. is the mechanism: S, a fixed harness outcome backed by a Foundry test (only B1 varies with the seed); G, guest; L, ledger or, for B5, "
        "the daily notional cap. On every S row, B2 is marked blocked by the unlisted-router flag, including stolen key. "
        "Family rows count blocked trials out of 25. The last two rows are numerators; the label gives the denominator. "
        "A harmful trial counts in ASR only when the system let the harm through. zk is zkLeash."
    ))
    trade_sentence = ""
    if trade_cap is not None:
        trade_sentence = (
            f" The {fair['blocked']['zkLeash']} fair days zkLeash refused each stopped at {trades_cap} legs, with at most "
            f"{usd(trade_cap['max_loss'])} of loss, so the trade-count cap fired and the loss cap did not."
        )
    if salami_extra is None:
        salami_stop = (
            f"zkLeash stopped after {legs['min']} to {legs['max']} legs and lost at most {usd(sal_zk['max'])}."
        )
    else:
        earlier = salami_extra["n"] - salami_extra["trade_cap_stops"]
        salami_stop = (
            f"zkLeash lost from {usd(salami_extra['loss_min'])} to {usd(sal_zk['max'])} (mean {usd(sal_zk['mean'])}) and stopped "
            f"after {legs['min']} to {legs['max']} legs. The {usd(cap)} loss cap is the bound. In {salami_extra['trade_cap_stops']} of "
            f"the {salami_extra['n']} trials the guest stopped at {trades_cap} legs with the loss still under that cap, because the "
            f"window already held {trades_cap} trades, so the trade-count cap stopped those {salami_extra['trade_cap_stops']}. The other "
            f"{earlier} stopped with fewer than {trades_cap} trades, before that check could fire."
        )
    add(body(
        f"zkLeash admitted none of the {measured_n} measured harmful trials (95% interval {ci_text(zk['attack_success']['ci95'])}) "
        f"and false-blocked {zk_fb} of {benign_n} benign trials (95% interval {ci_text(zk['false_block']['ci95'])}). B5 also admitted "
        f"none of the {measured_n}, and false-blocked {b5_fb} of {benign_n} (95% interval {ci_text(b5['false_block']['ci95'])}). "
        f"Recording deny reasons shows which check did the work. All {spike['zkleash_decided_only_by_vol_limit']} "
        f"volatility-spike buys were denied by the exposure limit alone; B2 admitted every one, since each was under ${static_cap:,} "
        f"and under the concentration cap. The all-in purchases were denied for concentration in all {allin.get('concentration', 0)} "
        f"cases, for the exposure limit in {allin.get('vol_limit', 0)}, and for the {usd(notional_cap)} notional cap in "
        f"{allin.get('notional', 0)}. On the salami drain, B4 lost {usd(sal_b4['mean'])} on average and up to {usd(sal_b4['max'])}. "
        f"{salami_stop} B5 stopped after {daily_legs['min']} to {daily_legs['max']} legs and lost {usd(sal_b5['mean'])} on average, "
        f"at most {usd(sal_b5['max'])}: an {usd(daily_cap)} notional cap and a 1% slippage limit imply an {usd(daily_cap * 0.01)} loss "
        f"bound, which is tighter than {usd(cap)}."
    ))
    add(body(
        f"That tighter bound is paid for on benign days. B5 blocked {derisk['blocked']['B5_daily_notional']} of {derisk['n']} "
        f"de-risking sales, single trades above {usd(daily_cap)} that the risk-reducing exemption allowed through zkLeash, and "
        f"{fair['blocked']['B5_daily_notional']} of {fair['n']} fair-turnover days whose clips were each under the ${static_cap:,} "
        f"per-trade cap. B2 blocked all {derisk['blocked']['B2_static']} de-risking sales and none of the fair days."
        + trade_sentence
    ))
    add(figure(doc, FIG_SALAMI, 3.4, "Fig2", "Cumulative execution loss for B4, B5, and zkLeash"))
    add(caption(
        f"Fig. 2. Cumulative execution loss when each leg gives up {small['extract_bps'] / 100:.0f}%. "
        f"Left: ${small['leg_usd']:,.0f} legs. B5 stops at the ${daily_cap:,.0f} notional cap "
        f"(loss ${ _end(small['B5_daily_notional']):,.0f}). zkLeash stops at {len(small['zkLeash'])} legs because of the "
        f"{trades_cap}-trade cap (loss ${_end(small['zkLeash']):,.0f}), before the ${cap:,.0f} loss cap. B4 runs all "
        f"{len(small['B4_stateless'])} legs. Right: ${real['leg_usd']:,.0f} legs, so the loss cap binds first. "
        f"zkLeash stops at ${_end(real['zkLeash']):,.0f}; B5 stops after {len(real['B5_daily_notional'])} leg; "
        f"B4 reaches ${_end(real['B4_stateless']):,.0f}."
    ))
    if crash is not None:
        by_name = {case["name"]: case for case in crash["cases"]}
        calm_c, buy_c, sell_c = by_name["calm_buy"], by_name["crash_buy"], by_name["crash_sell"]
        add(h2("A Crash Day"))
        drawdown_pct = crash["drawdown_cap_bps"] / 100
        harness_dd = crash["harness_drawdown_cap_bps"] / 100
        age_h = crash["max_price_age_seconds"] // 3600
        add(body(
            f"The randomized paths have no jumps, so we replayed one real window through the guest. The series is Binance "
            f"ETH-USDT hourly closes, {crash['window_hours']} bars, from the public kline API. Sigma is per hour, not per minute. "
            f"The exposure budget is {usd(crash['max_vol_exposure_usd'])}, set to 1.5 times this calm window\u2019s own post-trade "
            f"exposure, so the calm allow is that calibration and the calm buy cannot fail the exposure limit. The replay also "
            f"relaxes three harness limits: the drawdown cap is {drawdown_pct:.0f}% rather than {harness_dd:.0f}%, the maximum price "
            f"age is {age_h} hours rather than one hour, and USDC is {crash['usdc']}. Those three settings are not what "
            f"denied the crash buy. The book is {crash['book']}. A $2,000 ETH buy on the calm window ending "
            f"{calm_c['end']} (ETH {usd(calm_c['eth_end'])}, hourly \u03c3 = {calm_c['sigma']:.4f}, "
            f"V = {usd(calm_c['vol_exposure_usd'])}) was allowed. The same buy on the window ending {buy_c['end']}, the low of the "
            f"August 5, 2024 unwind (ETH from {usd(buy_c['eth_start'])} to {usd(buy_c['eth_end'])}, {buy_c['return'] * 100:.1f}%, "
            f"\u03c3 = {buy_c['sigma']:.4f}, V = {usd(buy_c['vol_exposure_usd'])}), was denied by the volatility limit and by nothing "
            f"else. Selling 1 ETH into USDC on that same crash window left V = {usd(sell_c['vol_exposure_usd'])}, still above the "
            "budget, and was allowed because it reduced exposure. This is one path, not a sample of crash days."
        ))
    add(h2("What the Results Show"))
    add(body(
        "B4 and zkLeash share the proof and the per-trade limits and differ by the ledger, and the ledger is what puts a hard "
        "stop on the large-leg drain in Fig. 2. B5 shows the stop is not unique to a loss ledger: a daily notional cap enforces "
        "a stricter loss bound and refuses benign turnover the ledger accepts, including de-risking sales. The two are substitutes "
        "with a measured cost, not a dominance result. The volatility-spike family, and the August 2024 replay, are where the "
        "proved statistic decides and the static cap does not. The proof does one further thing the harness cannot show as a rate: "
        "it removes the attestation key that B3 loses in the Foundry stolen-key test."
    ))

    # IX
    add(h1("Discussion and Limitations"))
    add(body(
        f"*Scripted attacker.* The attack families, and the held-out cases in our release, were written by the authors. Zero "
        f"measured successes in {measured_n} trials is evidence that the mechanisms work as designed, not that no attack exists. "
        "An adaptive adversary, or an attack set written by someone who has not read the executor, may do better. "
        f"The {structural_n} structural rows are fixed harness outcomes, and B2\u2019s blocks on those rows are the unlisted-router flag."
    ))
    add(body("*No real proof.* " + limit_proof))
    add(body(
        "*No live model.* bench/model_panel.py records the tool a local Ollama model proposes on five fixed prompts. No model "
        "server was running for this draft, so we do not report a proposal panel. A live model can propose trades the policy "
        "then blocks; that panel would not replace Table III."
    ))
    add(body(
        "*Synthetic markets.* The harness paths are geometric random walks with one volatility per trial. The August 2024 replay "
        "is a single hourly window with a budget set from its own calm counterpart. It shows the exposure limit can fire on a "
        "real jump. It does not estimate a false-block rate on historical data."
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
        "and a smart account. On the measured trials, the ledger bounds multi-trade drains that a stateless proof admits, and a "
        f"daily notional cap bounds them at a lower loss while refusing benign turnover the ledger accepts. The proved volatility "
        "statistic stops buys during volatility spikes that a static cap admits, including a buy on the August 5, 2024 ETH unwind, "
        "and the proof removes the trusted signing key. Evaluating that statistic on-chain from stored prices costs more than the "
        f"published cost of verifying a proof beyond about {cross['storage']} prices per asset. The evidence is limited by a scripted "
        f"attacker, mostly synthetic prices, a {trades_cap}-trade cap that itself false-blocks busy benign days, unproved execution, "
        "and the lack of a live model. Future work includes one Groth16 confirmation on a testnet, the local-model proposal panel, "
        "an attack set written without reading the executor, a sliding-window price index, and replacing the trade-count cap with "
        "the loss bound alone where the two disagree."
    ))

    add(h1("Acknowledgment", numbered=False))
    add(body(
        "The authors thank [[TODO: guide\u2019s name]], Department of Computer Engineering, Pimpri Chinchwad College of Engineering "
        "and Research, for guidance. [[An AI assistant was used to help draft and revise parts of the text and the evaluation "
        "code; the authors reviewed all content and take full responsibility for it. TODO: confirm or edit this disclosure.]]"
    ))

    add(h1("References", numbered=False))
    accessed = "Accessed: Oct. 15, 2026."
    for t in [
        "F. Perez and I. Ribeiro, \u201cIgnore previous prompt: Attack techniques for language models,\u201d arXiv:2211.09527, 2022.",
        "K. Greshake, S. Abdelnabi, S. Mishra, C. Endres, T. Holz, and M. Fritz, \u201cNot what you\u2019ve signed up for: Compromising "
        "real-world LLM-integrated applications with indirect prompt injection,\u201d in *Proc. 16th ACM Workshop Artif. Intell. "
        "Secur. (AISec)*, 2023, pp. 79\u201390.",
        "A. S. Patlan, P. Sheng, S. A. Hebbar, P. Mittal, and P. Viswanath, \u201cReal AI agents with fake memories: Fatal context "
        "manipulation attacks on Web3 agents,\u201d arXiv:2503.16248, 2025.",
        "R. Karanjai *et al.*, \u201cPACE: Policy-attested contract execution for safe AI agents in decentralized finance,\u201d "
        "arXiv:2608.17220, Aug. 2026.",
        "B. Ghosh, \u201cProof-gated signing: Solver-checked transaction guards that hold under state drift for onchain AI agents,\u201d "
        "arXiv:2610.00354, Sep. 30, 2026.",
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


def two_column_sect(old: list):
    """Section properties that set the body to two columns.

    Older drafts store those properties on a paragraph. After this script runs, they
    are the final body sectPr, because an extra break after the references was a blank section.
    """
    for el in old[:-1]:
        cols = el.find(f".//{qn('w:cols')}")
        if cols is not None and cols.get(qn("w:num")) == "2":
            sect = el.find(f".//{qn('w:sectPr')}")
            if sect is not None:
                return sect
    last = old[-1]
    cols = last.find(f".//{qn('w:cols')}")
    if last.tag == qn("w:sectPr") and cols is not None and cols.get(qn("w:num")) == "2":
        return last
    raise SystemExit(f"{SRC.name} has no two-column section")


def embedded_ids(elements) -> set[str]:
    found = set()
    for el in elements:
        for blip in el.iter(qn("a:blip")):
            rid = blip.get(qn("r:embed"))
            if rid:
                found.add(rid)
    return found


def main() -> None:
    for path in (FIG_ARCH, FIG_SALAMI):
        if not path.is_file():
            raise SystemExit(f"missing figure {path}")
    doc = Document(str(SRC))
    bodyel = doc.element.body
    old = list(bodyel.iterchildren())
    head = [old[i] for i in KEEP_HEAD]
    # The two-column sectPr closes the body. Using it as the final section property
    # avoids an empty single-column section after the references.
    final_sect = deepcopy(two_column_sect(old))
    fix_author_table(head[1])

    old_images = embedded_ids(old)
    new = build(doc, load_results())
    used = embedded_ids(new)
    for el in old:
        bodyel.remove(el)
    for el in head + new + [final_sect]:
        bodyel.append(el)
    # new_pic_inline reuses a relationship id when the image is already in the package.
    # Dropping every old id would delete the relationships the new drawings still point at.
    for rid in old_images - used:
        if rid in doc.part.rels:
            doc.part.drop_rel(rid)

    doc.core_properties.title = "zkLeash: Stateful, Proof-Gated Risk Enforcement for LLM Trading Agents"
    doc.save(str(OUT))
    check_package(OUT)
    print(f"wrote {OUT.relative_to(ROOT)}")


def check_package(path: Path) -> None:
    with zipfile.ZipFile(path) as z:
        rels = z.read("word/_rels/document.xml.rels").decode()
        xml = z.read("word/document.xml").decode()
        media = [name for name in z.namelist() if name.startswith("word/media/")]
    embeds = set(re.findall(r'r:embed="([^"]+)"', xml))
    ids = set(re.findall(r'\bId="([^"]+)"', rels))
    missing = embeds - ids
    if missing:
        raise SystemExit(f"drawings point at missing relationships: {sorted(missing)}")
    if len(media) < len(embeds):
        raise SystemExit(f"expected image parts for {sorted(embeds)}, found {media}")
    sects = re.findall(r"<w:sectPr[\s\S]*?</w:sectPr>", xml)
    if 'w:num="2"' not in sects[-1]:
        raise SystemExit("the final section is not two-column")
    # Title is one column, and Table III is a one-column span. Nothing after the references is.
    if len(sects) != 2:
        raise SystemExit(f"expected a title section and a two-column body, found {len(sects)}")
    print(f"package ok: images {sorted(embeds)}, media {len(media)}, sections {len(sects)}")


if __name__ == "__main__":
    main()
