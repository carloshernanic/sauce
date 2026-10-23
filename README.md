# sauce

A [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skill that pulls visual
references from Pinterest and turns them into a reference brief you can act on: palette,
composition, typography, texture, mood, plus the pins themselves.

Works for any project that needs visual direction: UI and landing pages, branding,
illustration, photography, interiors, architecture, fashion, packaging, game art, or
prompts for image models. No Pinterest login, no API key, no browser automation.

## How it works

1. You ask for references ("give me references for a dark fintech dashboard", "/sauce
   brutalist jazz poster", "make this less generic").
2. Claude writes 1 to 3 English searches and runs `scripts/pinterest_search.py`.
3. The script lists public pins, downloads the top ones into `./references`, builds a
   numbered contact sheet and a markdown table of the pins.
4. Claude reads the sheet, picks 3 to 5 references, and writes a brief
   (`references/<slug>-brief.md`) with hex palette, layout notes, type, surface and mood.
5. The brief feeds the next step: design tokens, a client proposal, or a prompt for whatever
   image model you use.

## Install

```bash
git clone https://github.com/carloshernanic/sauce ~/.claude/skills/sauce
```

Project-local install: clone into `.claude/skills/sauce` inside the project instead.

Requirements: Python 3.8+. Optional: `pip install pillow` for the contact sheet.

## Use the script on its own

```bash
python3 scripts/pinterest_search.py "japandi living room oak" --limit 30
python3 scripts/pinterest_search.py "japandi living room oak" --download 12 --sheet
python3 scripts/pinterest_search.py "japandi living room oak" --pick 2,5,11 --size orig --out ./refs
python3 scripts/pinterest_search.py "japandi living room oak" --json
```

Each run prints index, size, dominant color and original image URL per pin. Downloads are
saved as `<slug>-NN.<ext>`, with `<slug>-sheet.jpg` (contact sheet) and `<slug>-refs.md`
(table of the downloaded pins).

## Notes and limits

- Uses Pinterest's internal web search endpoint, the same one the logged-out website calls.
  It can change without notice; `scripts/browser_fallback.js` extracts image URLs from the
  search page in a browser if that happens.
- Logged-out results carry image, size and dominant color only (no title, author or link).
- References are for direction, not copying. Respect the rights of the original authors.
- Pinterest has announced an official MCP server with pin search behind OAuth. When it is
  public, it is the better long-term source for this skill.

## License

MIT
