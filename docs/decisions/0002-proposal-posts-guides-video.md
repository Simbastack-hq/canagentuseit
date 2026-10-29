# Proposal: post format, how-to guides, and video from runs (2026-10-30)

## Posts and guides
- Verdict post and guide formats: `prompts/writer.md`. The guide only contains commands that ran in
  the transcript on the way to the passing check, each tagged documented/workaround, plus an
  "Errors you might hit" section with exact error strings and the fix that worked. Re-run on a new
  version: the guide's tested date updates, or it gets flagged stale. Both go to the draft queue
  together; publishing the post publishes its guide.
- Posts carry `tested_on` and `tested_version` front matter. SlopIt has no field for them yet, so
  they show in the body; a SlopIt core PR can add them as post fields + TechArticle/HowTo JSON-LD.

## Video: render, don't screen-record
- Masters (kept forever, tiny): raw agent stream (Claude stream-json / Codex JSON) with a wall-clock
  `_t` on every line, normalized events, the sandbox call log (start/end per command), the
  docs-walk B-roll .webm. No live screen capture of the agent: it has no screen; we replay.
- `tools/render/`: an HTML page (terminal pane, the agent's text as captions, step / elapsed / tool
  calls counter, verdict card at the end) driven by a timeline built from the events. Playwright
  (headless Chromium) screenshots the page only when the frame changes; ffmpeg's concat demuxer
  holds each frame for its duration and encodes H.264 High 4:2:0, CRF 16, 30 fps, at 3840×2160
  (16:9) and 2160×3840 (9:16). Idle gaps > 5 s are squeezed to 1 s with an on-screen "⏩ 42 s"
  marker. Command output appears line-block by line-block (no fake typing of output); commands
  "type" in over ~0.6 s.
- The docs-walk is a replay of the pages the agent read, labelled on screen as B-roll, never
  presented as the agent's own browsing. If a quickstart's step needs a real web UI, that session
  gets recorded live inside the container (not built yet).
- Per approved run, `media/`: terminal-16x9.mp4, terminal-9x16.mp4, docs-broll.mp4, verdict-card
  PNGs (16:9 + 9:16), markers.csv (t, event: first command, first error, fix, success),
  captions.srt (the agent's narration). Pulled to the Mac (DaVinci Resolve) by an rsync script.
