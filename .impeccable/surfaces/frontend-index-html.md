---
version: 1
slug: "frontend-index-html"
primary_target: "frontend/index.html"
related_targets: []
---

# Surface brief — app shell + menu (frontend/index.html)

Scope: the whole app shell (top bar, tabs, tables, cards, buttons, forms) and the main menu (`#inicio`). Mode: Operate. Build path: code-led.
Audience/job: the player (desktop and phone equally) picks or resumes a club and runs matchdays; dense numbers when deciding, spectacle at moments.
Constraints: plain HTML/CSS/JS on Pico.css 2; Google Fonts allowed; club crests/shirts are SVG from data; pt-BR.
Unresolved: emoji still used as icons inside screens beyond the menu/shell (replace in the polish step).

## Direction contract

THESIS: The game as a night-match TV broadcast. Refuses the grey admin dashboard with one accent; every screen header is a broadcast graphic.

OWN-WORLD: Near-black navy night ground with a cold floodlight glow at the top; broadcast slabs in pitch green with white condensed caps; gold reserved for "you" and highlights; red only for LIVE and defeats. Barlow Condensed for graphics, scores and labels; Barlow for body; tabular numerals everywhere.

STORY: The player opens the broadcast, sees their club's next fixture as the lead graphic, presses Continue or picks a club from the kit wall, and every screen after reads like the match-day coverage of their club.

FIRST VIEWPORT: Top bar = channel bug (TALDO MANAGER) left, Menu right. Lead graphic = score-bug slab with the club crest, name, season/round and a big Continue button. Below, broadcast tabs Novo jogo / Carregar; kit cards (shirt, crest, name, stars, goal) in a fluid grid, 2 per row on phones.

FORM: Transmissão de TV noturna, user-chosen (not the rolled #5, vestiário); seed key e09f673c. Signature move: the broadcast score-bug strip (crest · SIGLA · status chip) heading the round, match and menu screens.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
