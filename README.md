# sauce

A [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skill that pulls visual
references from Pinterest, Dribbble, Cosmos, Behance and Mobbin, and turns them into a
reference brief you can act on: palette, composition, typography, texture, mood, plus the
images themselves with links back to their pages and authors.

Works for any project that needs visual direction: UI and landing pages, branding,
illustration, photography, interiors, architecture, fashion, packaging, game art, or
prompts for image models. No logins, no API keys.

## Sources

| source | best for | access |
|---|---|---|
| Pinterest | anything visual: illustration, photo, interiors, fashion, posters | script, no login |
| Dribbble | UI, app screens, icons, branding | script, no login |
| Cosmos | curated collections: art direction, editorial, photography, type | script, no login |
| Behance | full case studies: branding, identity, packaging, editorial, 3D | browser extractor (site blocks scripts) |
| Mobbin | real app screenshots and flows | browser extractor, needs your own Mobbin login |

Not included: sites that explicitly refuse automated access (for example Are.na).

## How it works

1. You ask for references ("references for a dark fintech dashboard", "/sauce brutalist
   jazz poster", "make this less generic").
2. Claude picks sources for the job, writes 1 to 3 English searches and runs `scripts/sauce.py`.
3. The script lists results from each source, downloads the top ones into `./references`,
   builds a numbered contact sheet and a markdown table with page links and authors.
4. For Behance or Mobbin, Claude opens the search page in a browser tool and runs
   `scripts/browser_extract.js` to collect the items shown there.
5. Claude reads the sheet, picks 3 to 5 references, and writes a brief
   (`references/<slug>-brief.md`) with hex palette, layout notes, type, surface and mood.
6. The brief feeds the next step: design tokens, a client proposal, or a prompt for whatever
   image model you use.

## Install

```bash
git clone https://github.com/carloshernanic/sauce ~/.claude/skills/sauce
```

Project-local install: clone into `.claude/skills/sauce` inside the project instead.

Requirements: Python 3.8+. Optional: `pip install pillow` for the contact sheet.

## Use the script on its own

```bash
python3 scripts/sauce.py "japandi living room oak"                              # Pinterest
python3 scripts/sauce.py "fintech dashboard dark" --source dribbble,cosmos --limit 12
python3 scripts/sauce.py "brutalist poster" --source all --download 12 --sheet
python3 scripts/sauce.py "editorial layout" --pick 2,5,11 --size orig --out ./refs
python3 scripts/sauce.py "editorial layout" --json
```

Each run prints index, source, size, dominant color, title and image URL per item. With
several sources the lists are interleaved, so `--download 12` mixes them. Downloads are
saved as `<slug>-NN.<ext>`, with `<slug>-sheet.jpg` (contact sheet) and `<slug>-refs.md`
(table with source, title, author, page link and image URL).

## Notes and limits

- Every script source uses the public endpoint the site's own logged-out page calls
  (Pinterest `BaseSearchResource`, Dribbble's search fragment, Cosmos's GraphQL API).
  They can change without notice; `scripts/browser_extract.js` is the fallback.
- Pinterest items carry image, size and dominant color only. Dribbble and Cosmos carry
  title, page link and usually the author.
- Pinterest's logged-out search returns nothing for some exact phrasings; the script retries
  with natural variants and says which one it used.
- References are for direction, not copying. Respect the rights of the original authors and
  each site's terms; keep usage light.
- Pinterest has announced an official MCP server with pin search behind OAuth. When it is
  public, it is the better long-term source for that site.

## License

MIT
