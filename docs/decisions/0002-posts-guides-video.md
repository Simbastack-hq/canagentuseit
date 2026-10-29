# 0002: Verdict posts, how-to guides, video from runs (2026-10-30)

**Decided:** verdict posts are scoped to the task, not the tool, and show outcome, recovery, outside help and attempts as separate facts. How-to guides are a separate, validated product: one per tool and task, updated in place, and drafted only after their own steps pass the hidden check on a clean machine. Video is a clean, labelled reconstruction of the run for NJ to edit, not a finished cut.

Inputs: NJ's capture spec and guide request (via the parent session), the proposal (`0002-proposal-posts-guides-video.md`), GPT Astra's review (`0002-astra-review.md`).

| Astra said | Decision | How |
|---|---|---|
| "Can an agent use Tool?" promises more than one quickstart attempt shows | **Adopted** | Titles name the task: "Can an agent <task> with <Tool> <ver>?" The badge stays as shorthand. |
| `partly` folds two findings together; recovery is hidden | **Adopted** | Posts list outcome, recovery (errors hit and fixed), outside help (left the docs / never opened them), attempts, then the badge. The enum is unchanged so results stay comparable. |
| The "full transcript" is clipped | **Adopted** | Called "Transcript" with a note that long outputs are clipped; complete redacted logs are linked from `results/<run>/` (added on publish). Final files are unpacked unclipped into `work-files/` for the writer. |
| "Checked by a human" becomes false under auto-publish | **Adopted** | The writer never claims review; `post_draft.py --publish` (NJ's step) appends "Reviewed by a human on <date>". |
| "Every command ran" ≠ "these instructions work"; omitted exploratory installs break the guide on a clean machine | **Adopted** | `tools/guide_check.py`: runs the guide's Steps top to bottom in a fresh container, then the run's hidden check. `post_draft.py` withholds the guide unless that passes for the current guide text. |
| Agent slips get mislabelled as workarounds, inventing doc defects | **Adopted** | Step tags: documented · workaround (needed on a clean machine, docs silent) · setup (our box). An agent's own slip and fix is never a step and never an "error you might hit". |
| One guide per tool × task, maintained in place; version slugs collide | **Adopted** | Guide slugs have no version. If the guide is already live, the new version is drafted as `<slug>-next-<date>` and swapped into the live slug on publish. "Tested on" only moves when the guide itself re-validates. |
| HowTo rich results were retired by Google; don't justify schema work with them | **Adopted** | No SlopIt PR for HowTo JSON-LD. `tested_on` / `tested_version` stay in front matter and the body. A SlopIt "tested on" field is a possible later PR if guides get traffic. |
| Will guides rank? Unknown; narrow task/error queries beat generic pages | **Adopted** | Titles and SEO descriptions lead with the task; "Errors you might hit" quotes exact error strings (the long-tail queries). |
| Animated output is reconstruction; label it | **Adopted** | The footer says "replay"; the renderer docs call it a reconstructed replay. Output appears as a block (we don't have per-line timestamps), commands type in. |
| Squeezing every gap erases reading time; captions/markers drift without a time map | **Adopted** | Output holds 0.7 s + 0.12 s per line (max 4 s). Waits over 5 s play as 1 s with a "⏩ N s skipped" badge in the footer. `timemap.csv` maps video seconds to wall clock; markers carry both. |
| Burned-in narration locks the edit; deliver clean assets | **Adopted** | Terminal clips have no captions and no full-screen cards; cards are separate PNGs (title, each attempt, verdict) per orientation; the agent's words are `captions.srt` as source text. |
| Docs re-rendered later may differ from what was tested | **Adopted (partly)** | The B-roll is captured right after the run and its on-screen label carries the capture date. The fetched page text is kept in the sandbox call log. |
| Start with H.264, test in Resolve before ProRes | **Adopted** | H.264 High 4:2:0 CRF 16 at 3840×2160 and 2160×3840. NJ's first Resolve import + phone playback is the pilot. |

## Not built yet
- Live Playwright recording inside the container for quickstarts that need a real web UI step.
- A per-tool registry page type in SlopIt (caniuse-style table across versions). Worth a SlopIt PR once ~10 results exist.
