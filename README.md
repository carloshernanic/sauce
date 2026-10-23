# sauce

A [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skill that pulls visual
references from fifteen design, art and photography sites and turns them into a reference
brief you can act on: palette, composition, typography, texture, mood, plus the images
themselves with links back to their pages and authors.

Works for any project that needs visual direction: UI and landing pages, branding,
typography, packaging, illustration, photography, interiors, architecture, fashion, game
art, or prompts for image models. No logins. API keys only for the two optional photo
sources.

## Sources

| source | best for | access |
|---|---|---|
| Pinterest | anything visual: illustration, photo, interiors, fashion, posters | script, no login |
| Dribbble | UI, app screens, icons, branding | script, no login |
| Cosmos | curated collections: art direction, editorial, photography, type | script, no login |
| Designspiration | graphic design, identity, print, type; 5-color palette per item | script, no login |
| Fonts In Use | typography in real use, with the typefaces named | script, no login |
| Awwwards | award-level websites and landing pages | script, no login |
| Land-book | curated landing pages and marketing sites | script, no login |
| The Dieline | packaging design and branding | script, no login |
| ArchDaily | architecture and interiors, professional photography | script, no login |
| The Met | open-access collection, public domain | script, no login |
| Unsplash, Pexels | free-license photography, usable as assets | script, needs a free API key |
| Behance | full case studies: branding, identity, packaging, editorial, 3D | browser extractor (site blocks scripts) |
| ArtStation | concept art, game art, 3D, illustration | browser extractor |
| Art Institute of Chicago | open-access paintings and prints, very high resolution | browser extractor |
| Mobbin | real app screenshots and flows | browser extractor, needs your own Mobbin login |

Not included: sites that explicitly refuse automated access (for example Are.na), and sites
that are paywalled for everyone (Refero, Savee search).

## How it works

1. You ask for references ("references for a dark fintech dashboard", "/sauce brutalist
   jazz poster", "make this less generic").
2. Claude picks sources for the job, writes 1 to 3 English searches and runs `scripts/sauce.py`.
3. The script lists results from each source, downloads the top ones into `./references`,
   builds a numbered contact sheet and a markdown table with page links and authors.
4. For Behance, ArtStation, the Art Institute or Mobbin, Claude opens the search page in a
   browser tool and runs `scripts/browser_extract.js` to collect the items shown there.
5. Claude reads the sheet, picks 3 to 5 references, and writes a brief
   (`references/<slug>-brief.md`) with hex palette, layout notes, type, surface and mood.
6. The brief feeds the next step: design tokens, a client proposal, or a prompt for whatever
   image model you use.

## Install

```bash
git clone https://github.com/carloshernanic/sauce ~/.claude/skills/sauce
```

Project-local install: clone into `.claude/skills/sauce` inside the project instead.

Requirements: Python 3.8+. Optional: `pip install pillow` for the contact sheet;
`UNSPLASH_ACCESS_KEY` and `PEXELS_API_KEY` in the environment for the photo sources.

## Use the script on its own

```bash
python3 scripts/sauce.py --sources                                              # list sources
python3 scripts/sauce.py "japandi living room oak"                              # Pinterest
python3 scripts/sauce.py "fintech" --source awwwards,landbook,dribbble --limit 8
python3 scripts/sauce.py "coffee packaging" --source dieline,designspiration --download 12 --sheet
python3 scripts/sauce.py "brutalist poster" --source all --limit 4 --download 16 --sheet
python3 scripts/sauce.py "editorial layout" --pick 2,5,11 --size orig --out ./refs
python3 scripts/sauce.py "editorial layout" --json
```

Each run prints index, source, size, dominant color, title and image URL per item. With
several sources the lists are interleaved, so `--download 12` mixes them. Downloads are
saved as `<slug>-NN.<ext>`, with `<slug>-sheet.jpg` (contact sheet) and `<slug>-refs.md`
(table with source, title, author, page link and image URL).

## Notes and limits

- Every keyless source uses the public endpoint the site's own logged-out page calls
  (Pinterest `BaseSearchResource`, Dribbble's search fragment, Cosmos's GraphQL API,
  Designspiration's embedded JSON, ArchDaily's search API, The Met's open API, plain HTML
  for the gallery sites). They can change without notice; `scripts/browser_extract.js` is
  the fallback.
- Gallery sites match words literally: short plain queries work best there.
- Some DNS filters (OpenDNS/Cisco Umbrella, for example) block Designspiration's image CDN
  (`dspncdn.com`); the search then works but the downloads fail with an SSL handshake error.
- Pinterest items carry image, size and dominant color only. The other sources carry title,
  page link and usually the author.
- References are for direction, not copying. Only The Met, the Art Institute (public domain),
  Unsplash and Pexels (free licenses) may be used as actual assets. Respect the rights of the
  original authors and each site's terms; keep usage light.
- Pinterest has announced an official MCP server with pin search behind OAuth. When it is
  public, it is the better long-term source for that site.

## License

MIT
