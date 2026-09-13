# Tempered demo video (Remotion script)

This is the shot-for-shot script for the demo video. It runs exactly 2:00 and is
built to be rendered in Remotion. Every scene lists what is on screen, the
voiceover, the on-screen text, and the motion. Colours, fonts, and the blue swoosh
come straight from the website so the video and the product look like one thing.

## The brief we are answering

> "Build one useful, multi-step AI agent. Connect it to at least three external
> apps. Show how you know it works."

The video hits each part on purpose:

- Multi-step agent: scene 5 shows the agent load tools, choose one, call the API,
  and answer, with every step visible.
- At least three external apps: scene 6 shows the eight presets we ship, plus the
  fact that any OpenAPI spec (or a plain sentence) connects a new one.
- Show how you know it works: scene 7 is the whole point of Tempered. It attacks
  each tool, catches the ones that accept bad input, grades them, and repairs them.

## Look and feel

Pull these values straight from the site so the video matches it exactly.

Colours:

- Background near-black: `#0b0b0d`
- Surface / cards: `#161618`, raised: `#242526`
- Brand blue: `#0b84f3` (light `#2290f5`, dark `#0a77db`)
- Text: `#ffffff`, softer body text `#e3e3e3`, muted `#9a9aa2`
- Pass green `#4dbf4d`, fail red `#fa5c60`, amber `#ffba00`
- Command chip background `#333`

Type:

- Display and headings: Clash Display (Fontshare), bold. This is the big voice.
- Body and captions: system-ui.
- Code, tool calls, timecodes: a monospace stack (SF Mono, Menlo, Consolas).

Signature elements to reuse as motion assets:

- The blue swoosh: one thick blue line that arcs across the full width and drifts
  slowly. Use it as the transition wipe between scenes.
- Neo-brutalist buttons: a 1.5px blue outline with a 3px hard offset shadow that
  presses in on click. Match the real buttons when you animate cursor clicks.
- Radius 8px on buttons, 16px on cards. Ease everything out, fast then settling.

## Music

The video should never sit silent. Use one clean, upbeat electronic bed, around
112 to 120 BPM, nothing vocal. Keep it low under the voiceover and let it breathe
in the gaps.

- 0:00 a low pulse under the hook.
- 0:22 the beat opens up as the demo starts.
- 1:22 a build through the scan, then a hit on the F to A flip at about 1:40.
- 1:48 resolve into the closing line.

Duck the music by roughly 6 dB whenever the voiceover is talking. Use a
royalty-free track so the submission is clean to share.

## Shot list (2:00 total)

### 1. Hook (0:00-0:10, 10s)

- On screen: black, then the blue swoosh sweeps across and the headline snaps in,
  "Build any AI tool from a sentence." Cut to a tiny chat bubble that reads
  "Posted to Slack, done" with a green tick, then a red flag drops on it: "nothing
  was sent."
- Voice: "Build any AI tool from a sentence. Then make sure it is not lying to you."
- On-screen text: "Build any AI tool from a sentence."
- Motion: swoosh wipe in, headline scales up and settles, the red flag lands hard.

### 2. The brief (0:10-0:22, 12s)

- On screen: the brief in mono type on the dark background, one line at a time.
- Voice: "Here is the brief. One multi-step agent. Three external apps, at least.
  And proof it actually works."
- On-screen text: the three requirements, each ticking green as it is named.
- Motion: lines type in; ticks pop as the voice hits each part.

### 3. The site, one click in (0:22-0:34, 12s)

- On screen: screen recording of the real landing page, swoosh drifting behind the
  headline. The cursor moves to the primary button and clicks it. The page crosses
  into the live demo.
- Voice: "This is Tempered. One click into the live demo."
- Motion: real cursor move, the button presses in on click, a swoosh wipe carries
  you to the demo page.

### 4. Pick a connector, ask in English (0:34-0:50, 16s)

- On screen: the demo page. Cursor scrolls to "Try a preset, no setup" and clicks
  the Pollinations image connector. The tools-loaded line appears. The cursor
  clicks the chat box and types "generate an image of a fox in a spacesuit," then
  clicks Send.
- Voice: "Pick a ready-made connector. No keys, no setup. Then ask for something
  in plain English."
- On-screen text: a small callout, "8 presets, or describe any API."
- Motion: cursor-driven, real typing cadence, the Send button presses in.

### 5. The agent works, the result lands (0:50-1:10, 20s)

- On screen: the chat streams the agent's steps. A call bubble shows the tool name
  and input, a result bubble follows, then the assistant replies and the generated
  image reveals large and clean.
- Voice: "The agent loads the tools, picks the right one, and calls the API. It is
  multi-step, and you can watch every call it makes."
- Motion: tool bubbles slide in one after another, the image reveals with a soft
  blur-to-sharp and a gentle scale.

### 6. Three apps? Eight, plus anything (1:10-1:22, 12s)

- On screen: a quick grid of the eight presets with tiny result thumbnails, weather,
  crypto prices, a NASA photo, the AI image, GitHub, Unsplash, Discord, and the
  Petstore demo.
- Voice: "The brief asked for three apps. Tempered ships eight, and it connects to
  anything with an API spec, or just a sentence."
- On-screen text: "8 ready. Limitless from a spec."
- Motion: the eight tiles land on the beat, then the line settles under them.

### 7. Show how you know it works (1:22-1:48, 26s)

- On screen: switch to Verify. The cursor clicks Scan on a freshly generated
  connector (Petstore). Red findings stream in, each showing the bad payload sent
  and the success it got back. The grade lands on a big red F. Then the cursor
  clicks Repair, a diff streams, the scan runs again, and the grade flips to a
  green A.
- Voice: "Here is the part most demos skip. A tool can take bad input and still
  report success. Your agent would believe it. So Tempered attacks every tool on
  purpose and grades what it catches. Then one click rewrites the tool to enforce
  its own rules and checks again. F to A."
- On-screen text: "silent success caught" over the findings, then "F to A" on the
  flip.
- Motion: findings stream fast, the F pulses red, the F to A flip pops with the
  music hit and a green sweep.

### 8. Close (1:48-2:00, 12s)

- On screen: back to the dark hero with the swoosh. The command chip shows
  `python -m tempered.cli serve` and the local URL. Wordmark and a small team
  credit.
- Voice: "Describe it. Chat with it. Prove it works. That is Tempered."
- On-screen text: "Tempered. Build any AI tool from a sentence." plus the repo link.
- Motion: swoosh settles, the closing line holds, music resolves.

## Assets to capture

Record all of these in the site's dark theme at 1920x1080 or larger.

- Landing hero with the swoosh drifting (scene 1 and 3).
- Cursor moving to the primary button and clicking through to the demo (scene 3).
- Preset pick, chat typing, and Send on the Pollinations connector (scene 4).
- The chat tool-call bubbles and the image reveal (scene 5).
- The eight preset buttons, and one small result per preset for the grid (scene 6).
- A Scan that lands on F and a Repair that flips it to A (scene 7).
- The command chip and wordmark for the close (scene 8).

Keep real cursor movement where you can. It reads as a genuine product, not a
mockup. If a live run is slow, record it, then speed the dead time in Remotion so
the timings above still hold.
