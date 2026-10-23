---
name: sauce
description: Pulls visual references from Pinterest, Dribbble, Cosmos and (via the browser) Behance or Mobbin, and turns them into a usable reference brief for any creative or product task - UI and landing page design, branding, illustration style, photography, interiors, architecture, fashion, packaging, game art, or image generation prompts. Downloads the references, builds a numbered contact sheet, helps pick the strongest ones and writes a brief (palette, composition, typography, texture, mood). Use when the user asks for references, inspiration, a moodboard, "sauce", "look on Pinterest/Dribbble/Behance", "what does X usually look like", or wants a design or generated image that feels less generic.
---

# Sauce: visual references for any project

Flow: search -> look -> pick -> write a reference brief -> hand it to the next step
(a design implementation, a prompt for an image model, a client proposal, a style guide).
You orchestrate; the script searches and downloads.

Script: `scripts/sauce.py` next to this file (Python 3.8+, standard library only; Pillow is
optional and only needed for the contact sheet). Call it as
`python3 <skill-dir>/scripts/sauce.py` (`python` on Windows).

## Sources

| source | best for | how |
|---|---|---|
| `pinterest` (default) | anything visual: illustration, photo, interiors, fashion, posters, mood | script |
| `dribbble` | UI, app screens, icons, branding, motion stills | script |
| `cosmos` | curated, high-taste collections: art direction, editorial, photography, type | script |
| Behance | full case studies: branding, identity, packaging, editorial, 3D | browser only (`scripts/browser_extract.js`) |
| Mobbin | real app screenshots and flows | browser only, needs the user's own Mobbin login |

Pick sources by use: UI or product work -> `dribbble,cosmos` plus Mobbin/Behance in the
browser when available; brand or print -> `pinterest,cosmos` plus Behance; illustration,
photo, spaces, prompts for image models -> `pinterest,cosmos`. `--source all` runs the
three script sources at once and interleaves them.

## Steps

1. **Understand what the references are for.** A UI moodboard, a brand direction, an
   illustration style, a photo shoot, a room, a poster, a prompt? That decides which sources
   to use, what to look for in the images and what the brief must contain. Ask only if the
   use is really unclear.
2. **Write 1 to 3 searches in English** (every source returns far more for English queries).
   Combine subject + style + medium, and vary the angle between searches instead of repeating
   synonyms. Examples: `fintech dashboard dark ui`, `editorial typography grid layout`,
   `brutalist poster red black`, `japandi living room oak`, `isometric game tileset pixel art`.
   Avoid vague words like "beautiful", "modern", "cool".
3. **Run the script**, once per search. Default folder is `./references`; use the one the user
   names if any.

   ```bash
   python3 <skill-dir>/scripts/sauce.py "<query>" --source pinterest,dribbble,cosmos --limit 12 --download 12 --sheet
   ```

   Output: a numbered list (index, source, size, dominant color, title, image URL), the saved
   files, a `<slug>-sheet.jpg` contact sheet and a `<slug>-refs.md` table with page links and
   authors where the source provides them.
   Useful flags: `--pick 2,5,11` downloads only those indexes; `--size orig` fetches full
   resolution (large; only when the image itself will be used); `--out <dir>`; `--json`.
   A source that fails is skipped with a message; the others still run. Pinterest's
   logged-out search returns nothing for some exact phrasings, so the script retries with
   natural variants and says which one it used.
4. **Browser sources (Behance, Mobbin), when a browser tool is available and the use calls
   for them.** Open the site's search page, wait for results, run `scripts/browser_extract.js`
   in the page and keep the returned list (title, author, page, image). Download the chosen
   image URLs with `curl -L -o <file> <url>` into the same references folder, numbered after
   the script's files, and add them to the refs table by hand. Mobbin only shows screens to
   logged-in users: never log in for the user; use it only if their browser session already is.
5. **Look.** Read the contact sheet (one read shows all references, numbered). Without Pillow,
   read 4 to 6 individual files instead. Say what you see, not what you expected.
6. **Pick 3 to 5 references.** Criteria: they fit the stated use, they are not generic, they
   show different solutions to the same problem, and the execution is strong. Skip items that
   are mostly a logo, a licensed character, a watermark, or a recognisable person. If the
   batch is weak, refine the search or switch source and run again (at most 2 extra rounds
   without asking).
7. **Write the reference brief** in `references/<slug>-brief.md` (or in the chat if the user
   just wants a quick answer). Keep it concrete, 10 to 20 lines:
   - Chosen references: index, source, page link or image URL, author when known, and one
     line on why each one earns its place.
   - Palette: 3 to 6 hex values, starting from the dominant colors and corrected by eye.
   - Composition and layout: grid, density, hierarchy, whitespace, framing, aspect ratio.
   - Typography (if present): classification, weight contrast, case, letterspacing.
   - Surface: texture, material, lighting, rendering technique or medium.
   - Mood in 3 to 5 words, plus what the references have in common and what makes the
     best one stand out.
   - Anti-references: 1 or 2 things seen in the batch to avoid.
8. **Hand off according to the use.**
   - Design or code: turn the palette into tokens, name the type pairing, describe the
     layout rules; then implement or pass it to the design step.
   - Image generation (any model or tool the user has): prompt = the user's original request
     + the brief, written as concrete visual instructions. The request sets the subject; the
     brief refines style only. If the tool accepts an input image, pass one reference with
     "use the attached image only as a style reference (palette, composition, lighting);
     create an original image of: <request>". Never ask a model to reproduce a reference.
   - Research or proposal: list the references with links and the brief as the rationale.
9. **Deliver**: the brief, the contact sheet path, and the list of chosen references with
   links. Leave the files in the references folder for the user.

## Rules

- References are for direction, not copying. Do not reproduce a specific work, a brand mark
  or a product design. Credit authors in the brief when the source gives them.
- More than ~5 references in one brief averages out into something bland; pick fewer.
- Pinterest items carry only image, size and dominant color (no title, author or link);
  Dribbble and Cosmos carry title, page link and often the author. Describe what you see
  yourself and cite the link or image URL.
- Read only. The skill never saves, likes, follows or posts anything on any site, and never
  logs in on the user's behalf.
- Sites that explicitly refuse automated access (for example Are.na) are not used, even
  through the browser.

## If a script source fails

Each source uses the public endpoint its own logged-out website calls, which can change
without notice. On HTTP 403, zero results or a "failed" line:

1. Open the site's search page in a browser tool (Pinterest, Dribbble and Cosmos all show
   results without login; ignore login modals, the items load behind them).
2. Run `scripts/browser_extract.js` in the page and use the returned image URLs.
3. Download the chosen URLs with `curl -L -o <file> <url>` and continue from step 5.

Pinterest has announced an official MCP server with pin search behind OAuth
(developers.pinterest.com/about-pinterest-mcp). Once it is public, it can replace that source.
