# English Voice Sample Hunting Guide

Check `output/noncompanion/{PCK}/{bank}/wav/` for candidate WAVs.

Legend:
- **wem={ID}** = WEM ID (filename without .wav)
- **~{N}s** = estimated duration
- Top candidates = longest files = best voice samples

---

## Kunrad Voigtvir (66 events, all PRL_)

**PCK:** `WH40KRT_NARR_PRL/bank_002058/wav/`

Top 15 candidates (longest):

| # | WEM ID | Size | ~Duration |
|---|--------|------|-----------|
| 1 | wem=756400996 | 866.5KB | ~9.2s |
| 2 | wem=39044881 | 866.3KB | ~9.2s |
| 3 | wem=941973350 | 851.5KB | ~9.1s |
| 4 | wem=981840537 | 827.3KB | ~8.8s |
| 5 | wem=399249533 | 825.8KB | ~8.8s |
| 6 | wem=145536766 | 825.6KB | ~8.8s |
| 7 | wem=875577511 | 718.3KB | ~7.7s |
| 8 | wem=310313030 | 718.3KB | ~7.7s |
| 9 | wem=515770269 | 698.9KB | ~7.5s |
| 10 | wem=307882689 | 698.9KB | ~7.5s |
| 11 | wem=718364273 | 693.2KB | ~7.4s |
| 12 | wem=634209436 | 693.2KB | ~7.4s |
| 13 | wem=333283497 | 638.8KB | ~6.8s |
| 14 | wem=550115296 | 621.5KB | ~6.6s |
| 15 | wem=70190655 | 568.8KB | ~6.1s |

Sample events: PRL_KunradIntroduction_01, PRL_KunradIntroduction_02, PRL_KunradIntroduction_03

Listen for: young male, theatrical, sly/manipulative tone

---

## Theodora von Valancius (99 events, all PRL_)

**PCK:** `WH40KRT_NARR_PRL/bank_002058/wav/` (same bank as Kunrad)

Top 15 candidates (same pool — Kunrad + Theodora mixed):

| # | WEM ID | Size | ~Duration |
|---|--------|------|-----------|
| 1 | wem=756400996 | 866.5KB | ~9.2s |
| 2 | wem=39044881 | 866.3KB | ~9.2s |
| 3 | wem=941973350 | 851.5KB | ~9.1s |
| 4 | wem=981840537 | 827.3KB | ~8.8s |
| 5 | wem=399249533 | 825.8KB | ~8.8s |
| 6 | wem=145536766 | 825.6KB | ~8.8s |
| ... | ... | ... | ... |

Sample events: PRL_TheodoraChoice_01, PRL_TheodoraChoice_02, PRL_Theodora_Combat_01

Listen for: mature female, authoritative, aristocratic

---

## Generic Male NPC (227 events: 98 PRL + 123 CH2 + misc)

**PCK:** `WH40KRT_NARR_PRL/bank_002058/wav/` (PRL events)
**PCK:** `WH40KRT_NARR_CH02/bank_a234d9/wav/` (81 WAVs, CH2 events)

NARR_CH02 top candidates:

| # | WEM ID | Size | ~Duration |
|---|--------|------|-----------|
| 1 | wem=xxx | xxxKB | ~xx.xs |
| 2 | wem=xxx | xxxKB | ~xx.xs |
| ... | ... | ... | ... |

Check the largest files in NARR_CH02 banks for generic male NPC voices.

---

## Narrator (16 events, NARR_ prefix)

Scattered across ALL NARR banks. Check the wav files that contain narration-style audio.

---

## Trazyn (63 events)

Events: TrazynOffer_*, TrazynFirstMeet_*, TrazynShowdown_*

**Bank TBD** — not yet identified. Try:
- `WH40KRT_NARR_CH02/` or CH03/ (mid-game appearance)
- `WH40KRT_NARR_DLC1/` (might be in DLC)
- Listen for: ancient, theatrical, smug, deep voice

---

## Edelthrad (0 events mapped)

No Sound.json events. May use Generic Male NPC voice.
Check the same banks as Generic Male NPC.

---

## Eogann (104 events, BNTRS_)

**NOT in NARR banks** — BNTRS = banter = companion system.
Try: `WH40KRT_Main_RaceAsks.pck` (not extracted yet).

---

## Smuggler / Psyker (NPC) / Seneschal (NPC) (Companions_ prefix)

**NOT in NARR banks** — "Companions_" prefix.
Try: `WH40KRT_Main_RaceAsks.pck` (not extracted yet).

---

## Generic Female NPC / Interrogator (NPC)

No events mapped. May share Generic Male NPC voice or use default_female.
No NARR extraction target.

---

## HOW TO USE

1. Pick a character above
2. Open the corresponding `output/noncompanion/{PCK}/{bank}/wav/` folder
3. Play the top 5-10 longest WAVs
4. When you recognize a character's voice, note the WEM ID
5. Tell me: "wem=756400996 is Kunrad" etc.
6. I'll create a reference sample and add to `refs/samples_en/`
