// Browser extractor for sites that block scripts or need a login.
// Run it in a browser tab (e.g. a browser tool's "execute JavaScript" action) that is open
// on a search/results page of one of these sites:
//   Behance    https://www.behance.net/search/projects?search=<query>
//   Mobbin     https://mobbin.com/search/... (needs your own logged-in session)
//   ArtStation https://www.artstation.com/search?query=<query>
//   Art Institute of Chicago  https://www.artic.edu/collection?q=<query>
//   Pinterest  https://www.pinterest.com/search/pins/?q=<query>   (fallback for sauce.py)
//   Dribbble   https://dribbble.com/search/<query>                 (fallback for sauce.py)
//   Cosmos     https://www.cosmos.so/explore?q=<query>             (fallback for sauce.py)
//   Any other gallery: falls back to every image wider than 300px with its link.
// It scrolls a few screens to trigger lazy loading, then returns an array of
// {source, title, author, page, image} for the visible items, de-duplicated by image.
// Nothing is saved, liked or posted; it only reads what the page already shows you.
(async () => {
  const host = location.hostname.replace(/^www\./, '');
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  for (let i = 0; i < 4; i++) { window.scrollBy(0, window.innerHeight * 2); await sleep(900); }
  window.scrollTo(0, 0); await sleep(600);

  const best = (img) => {
    const set = (img.srcset || img.dataset.srcset || '').split(',').map((s) => s.trim().split(' ')[0]).filter(Boolean);
    return set.pop() || img.dataset.src || img.src;
  };
  const clean = (s) => (s || '').replace(/\s+/g, ' ').trim().slice(0, 120);
  const out = [];

  if (host.endsWith('behance.net')) {
    for (const a of document.querySelectorAll('a[href*="/gallery/"]')) {
      let root = a, img = null;
      for (let d = 0; d < 6 && root; d++) {
        img = root.querySelector('img[src*="behance.net/projects"], img[srcset*="behance.net/projects"]');
        if (img) break;
        root = root.parentElement;
      }
      if (!img) continue;
      const owner = root.querySelector('a[href*="behance.net/"]:not([href*="/gallery/"]), [class*="Owner"] a');
      out.push({ source: 'behance', title: clean(a.textContent || img.alt), author: clean(owner && owner.textContent),
                 page: a.href.split('?')[0], image: best(img) });
    }
  } else if (host.endsWith('mobbin.com')) {
    for (const img of document.querySelectorAll('img[src*="supabase.co/storage"], img[srcset*="supabase.co/storage"]')) {
      const url = best(img);
      if (/app_logos|avatars/.test(url) || img.width < 80) continue;
      const a = img.closest('a');
      out.push({ source: 'mobbin', title: clean(img.alt), author: '', page: a ? a.href : location.href, image: url });
    }
  } else if (host.endsWith('pinterest.com')) {
    for (const img of document.querySelectorAll('img[src*="pinimg.com"]')) {
      if (img.width < 50) continue;
      const a = img.closest('a[href*="/pin/"]');
      out.push({ source: 'pinterest', title: clean(img.alt === 'Salvar Pins' || img.alt === 'Save' ? '' : img.alt), author: '',
                 page: a ? a.href : '', image: best(img).replace(/\/\d+x\//, '/originals/') });
    }
  } else if (host.endsWith('dribbble.com')) {
    for (const li of document.querySelectorAll('li[id^="screenshot-"]')) {
      const img = li.querySelector('img[data-srcset], img[srcset], img[src*="cdn.dribbble.com"]');
      if (!img) continue;
      const a = li.querySelector('a[href*="/shots/"]');
      const t = li.querySelector('.shot-title');
      const u = li.querySelector('.display-name');
      out.push({ source: 'dribbble', title: clean(t ? t.textContent : img.alt), author: clean(u && u.textContent),
                 page: a ? a.href : '', image: best(img).split('?')[0] });
    }
  } else if (host.endsWith('artstation.com')) {
    for (const a of document.querySelectorAll('a[href*="/artwork/"]')) {
      const img = a.querySelector('img') || a.parentElement.querySelector('img');
      if (!img || img.width < 80) continue;
      const card = a.closest('[class*="project"], [class*="gallery"], li, article') || a.parentElement;
      const user = card && card.querySelector('a[href*="artstation.com/"]:not([href*="/artwork/"])');
      out.push({ source: 'artstation', title: clean(img.alt || a.getAttribute('title')), author: clean(user && user.textContent),
                 page: a.href.split('?')[0], image: best(img).replace(/\/(smaller_square|small_square|small|medium|large)\//, '/large/') });
    }
  } else if (host.endsWith('artic.edu')) {
    for (const a of document.querySelectorAll('a[href*="/artworks/"]')) {
      const img = a.querySelector('img');
      if (!img || img.width < 80) continue;
      const m = best(img).match(/\/iiif\/2\/([^/]+)\//);
      out.push({ source: 'artic', title: clean(img.alt || a.textContent), author: '', page: a.href.split('?')[0],
                 image: m ? `https://www.artic.edu/iiif/2/${m[1]}/full/1686,/0/default.jpg` : best(img) });
    }
  } else if (host.endsWith('cosmos.so')) {
    for (const img of document.querySelectorAll('img[src*="cdn.cosmos.so"], img[srcset*="cdn.cosmos.so"]')) {
      if (img.width < 80) continue;
      const a = img.closest('a');
      out.push({ source: 'cosmos', title: clean(img.alt), author: '', page: a ? a.href : '', image: best(img).split('?')[0] });
    }
  } else {
    for (const img of document.images) {
      if (img.naturalWidth < 300) continue;
      const a = img.closest('a');
      out.push({ source: host, title: clean(img.alt), author: '', page: a ? a.href : '', image: best(img) });
    }
  }

  const seen = new Set();
  return out.filter((p) => p.image && !seen.has(p.image) && seen.add(p.image));
})();
