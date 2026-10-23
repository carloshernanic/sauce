// Fallback: run this in a browser tab open at https://www.pinterest.com/search/pins/?q=...
// (for example with a browser tool's "execute JavaScript" action). Ignore the login modal.
// Returns the visible pins' original image URL, thumbnail and alt text, de-duplicated.
[...document.querySelectorAll('img')]
  .filter(i => i.src.includes('pinimg.com') && i.width > 50)
  .map(i => ({
    orig: (i.srcset || '').split(',').pop().trim().split(' ')[0] || i.src.replace(/\/\d+x\//, '/originals/'),
    thumb: i.src,
    alt: (i.alt || '').slice(0, 100),
  }))
  .filter((p, idx, arr) => arr.findIndex(q => q.orig === p.orig) === idx)
