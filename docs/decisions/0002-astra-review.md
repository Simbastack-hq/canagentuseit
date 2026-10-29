**1. Verdict posts: keep the structure; narrow the claim.**

**Sound:** Answer first, exact task, pinned environment, errors attributed to the right party, and a falsifiable check. [SPEC.md](../../SPEC.md) establishes a credible experiment.

**Wrong:** “Can an agent use Tool?” promises more than one quickstart attempt establishes. A first-pass success can hide extensive recovery; `partly` combines two different findings: another agent succeeded, or outside documentation was necessary. Readers could interpret these as comparable measures of tool quality.

The “full transcript” is also abridged: [transcript.py](../../tools/transcript.py) clips commands/files at 2,500 characters and outputs at 1,500. A decisive error can disappear. The mandatory “checked by a human” footer becomes false under planned auto-publication.

**Change:** Title around the actual task: “Can Claude build Tool’s first server?” Show task outcome, recovery required, outside-help usage, and attempt count separately. Keep the verdict badge as shorthand. Put selected evidence in the article and link complete, redacted logs separately. Generate review attribution from actual approval records.

**2. Guides: useful potential, but the current publication rule manufactures confidence.**

**Sound:** Tested versions, executable examples, exact errors, and provenance can offer something better than rewritten documentation.

**Wrong:** “Every command ran” does not mean “these instructions work.” An agent installs a dependency during exploration, later succeeds, and the writer omits that exploratory step. The guide now fails on a clean machine. Conversely, an agent mistypes an import and repairs it; calling that repair a `workaround` invents a documentation defect.

Showing final file contents alongside historical commands can produce a sequence that never actually occurred. “Leave unclear steps out” makes this worse. The clipped transcript cannot reliably supply complete files. A fresh shell in the already-modified sandbox, as specified for `run.sh`, proves neither clean installation nor guide reproducibility.

**Change:** Treat guide production as a separate editorial and execution stage. Extract the shortest supported recipe, obtain complete final artifacts, then execute the **published instructions** in a fresh container with only stated prerequisites. Allow newly validated commands; preserve their separate provenance without changing the original verdict. Classify deviations as documented setup, necessary workaround, agent-error recovery, or harness requirement. Only verified, relevant troubleshooting belongs in the guide.

Will it rank? Unknown without query and competition evidence. My assessment: narrow task/error queries offer a stronger opportunity than generic “get Tool working” pages. Google emphasizes original value and satisfying the reader’s task; transcript-derived duplication alone is weak differentiation. [Google guidance](https://developers.google.com/search/docs/fundamentals/creating-helpful-content). Don’t justify the schema work through HowTo rich results: Google retired them. [Google announcement](https://developers.google.com/search/blog/2023/08/howto-faq-changes).

Use **one maintained guide per tool × task**, updated in place, with dated validation history and linked historical verdict posts. Split versions only when instructions materially diverge. The existing version-only slug already collides across reruns. Publish posts independently; guides require their own validation gate. Display tested compatibility prominently, flag newer versions as unverified, and advance “tested on” only after validating the guide itself.

**3. Video: approve the renderer concept, revise the editing deliverable.**

**Sound:** HTML gives controllable typography and separate landscape/portrait compositions. Sparse screenshots plus explicit durations suit mostly static terminal material; concat supports duration directives. [FFmpeg documentation](https://ffmpeg.org/ffmpeg-formats.html#concat-1). Labelled docs B-roll is honest.

**Wrong:** [The proposal](../../docs/decisions/0002-proposal-posts-guides-video.md) overstates temporal fidelity. Normalized results contain whole output blobs, not timestamps per line. Animated output would be reconstruction. Typing, blinking cursors and elapsed counters also change frames between events.

Compressing every long gap to one second can erase reading time. Without a source-to-render time map, markers and captions drift. Burned-in agent narration locks NJ into wording and pacing before the edit. Rendering today’s docs can illustrate instructions different from those tested.

**Change:** Label the terminal as a reconstructed replay; distinguish measured timing from presentation timing. Preserve reading holds and export both original and compressed timestamps. Render separate portrait layouts with large text and overlay-safe margins; 4K alone does not create legibility.

Deliver clean terminal clips with handles, optional overlays, separate text cues, cards and B-roll. Agent text is editorial source material, not subtitles for NJ’s eventual voiceover. Retain captured docs evidence and label later captures. Start with H.264, then test a representative Resolve edit before adding ProRes intermediates.

**Must-fix, in order:**

1. Validate guides independently from clean environments.
2. Preserve complete redacted evidence and artifacts.
3. Separate agent mistakes from genuine workarounds.
4. Decouple guide publication and version maintenance.
5. Correct verdict scope and review attribution.
6. Establish video timing maps and editable assets.
7. Pilot both orientations through Resolve and phone playback.
