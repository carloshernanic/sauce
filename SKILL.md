---
name: sauce
description: Pulls visual references from Pinterest (no login, no API key) and turns them into a usable reference brief for any creative or product task - UI and landing page design, branding, illustration style, photography, interiors, architecture, fashion, packaging, game art, or image generation prompts. Downloads pins, builds a numbered contact sheet, helps pick the strongest references and writes a brief (palette, composition, typography, texture, mood). Use when the user asks for references, inspiration, a moodboard, "sauce", "look on Pinterest", "what does X usually look like", or wants a design or generated image that feels less generic.
---

# Sauce: Pinterest references for any project

Flow: search -> look -> pick -> write a reference brief -> hand it to the next step
(a design implementation, a prompt for an image model, a client proposal, a style guide).
You orchestrate; the script searches and downloads.

Script: `scripts/pinterest_search.py` next to this file (Python 3.8+, standard library only;
Pillow is optional and only needed for the contact sheet). Call it as
`python3 <skill-dir>/scripts/pinterest_search.py` (`python` on Windows).

## Steps

1. **Understand what the references are for.** A UI moodboard, a brand direction, an
   illustration style, a photo shoot, a room, a poster, a prompt? That decides what you look
   for in the images and what the brief must contain. Ask only if the use is really unclear.
2. **Write 1 to 3 searches in English** (Pinterest returns much more for English queries).
   Combine subject + style + medium, and vary the angle between searches instead of repeating
   synonyms. Examples: `fintech dashboard dark ui`, `editorial typography grid layout`,
   `brutalist poster red black`, `japandi living room oak`, `isometric game tileset pixel art`.
   Avoid vague words like "beautiful", "modern", "cool".
3. **Run the script**, once per search. Default folder is `./references`; use the one the user
   names if any.

   ```bash
   python3 <skill-dir>/scripts/pinterest_search.py "<query>" --limit 30 --download 12 --sheet
   ```

   Output: a numbered list (index, size, dominant color, image URL), the saved files, a
   `<slug>-sheet.jpg` contact sheet and a `<slug>-refs.md` with the table of downloaded pins.
   Useful flags: `--pick 2,5,11` downloads only those indexes; `--size orig` fetches full
   resolution (large; only when the image itself will be used); `--out <dir>`; `--json`.
   Logged-out search returns nothing for some exact phrasings; the script then retries with
   natural variants ("... design inspiration", "... ideas", fewer words) and says which one it
   used. If it still finds nothing, reword the query the way a person would type it.
4. **Look.** Read the contact sheet (one read shows all pins, numbered). Without Pillow, read
   4 to 6 individual files instead. Say what you see, not what you expected.
5. **Pick 3 to 5 references.** Criteria: they fit the stated use, they are not generic, they
   show different solutions to the same problem, and the execution is strong. Skip pins that
   are mostly a logo, a licensed character, a watermark, or a recognisable person. If the
   batch is weak, refine the search and run again (at most 2 extra rounds without asking).
6. **Write the reference brief** in `references/<slug>-brief.md` (or in the chat if the user
   just wants a quick answer). Keep it concrete, 10 to 20 lines:
   - Chosen references: index, URL, and one line on why each one earns its place.
   - Palette: 3 to 6 hex values, starting from the dominant colors and corrected by eye.
   - Composition and layout: grid, density, hierarchy, whitespace, framing, aspect ratio.
   - Typography (if present): classification, weight contrast, case, letterspacing.
   - Surface: texture, material, lighting, rendering technique or medium.
   - Mood in 3 to 5 words, plus what the references have in common and what makes the
     best one stand out.
   - Anti-references: 1 or 2 things seen in the batch to avoid.
7. **Hand off according to the use.**
   - Design or code: turn the palette into tokens, name the type pairing, describe the
     layout rules; then implement or pass it to the design step.
   - Image generation (any model or tool the user has): prompt = the user's original request
     + the brief, written as concrete visual instructions. The request sets the subject; the
     brief refines style only. If the tool accepts an input image, pass one reference with
     "use the attached image only as a style reference (palette, composition, lighting);
     create an original image of: <request>". Never ask a model to reproduce a reference.
   - Research or proposal: list the references with URLs and the brief as the rationale.
8. **Deliver**: the brief, the contact sheet path, and the list of chosen references.
   Leave the files in the references folder for the user.

## Rules

- References are for direction, not copying. Do not reproduce a specific work, a brand mark
  or a product design.
- More than ~5 references in one brief averages out into something bland; pick fewer.
- Logged-out pins carry only image, size and dominant color (no title, author or link), so
  describe what you see yourself and cite the image URL.
- Read only. The skill never saves, likes or posts anything on Pinterest.

## If the search fails

The script uses Pinterest's internal web endpoint (`BaseSearchResource`), which can change
without notice. On HTTP 403 or zero results:

1. Open `https://www.pinterest.com/search/pins/?q=<query>` in a browser tool. Ignore the login
   modal; the pins are loaded behind it.
2. Run `scripts/browser_fallback.js` in the page (it returns the original image URLs of the
   visible pins). Scroll to load more.
3. Download the chosen URLs with `curl -L -o <file> <url>` and continue from step 4.

Pinterest has announced an official MCP server with pin search behind OAuth
(developers.pinterest.com/about-pinterest-mcp). Once it is public, it can replace the script.
