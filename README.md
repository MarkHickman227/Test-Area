# Lume Arno

An original multi-page tourism guide for Florence, Italy. Fresh brand, copy, and design — not affiliated with any official tourism board.

## Pages

- `index.html` — Home (destination hero + ways into the city)
- `explore.html` — Things to do (art, streets, views)
- `plan.html` — Plan your visit (season, tickets, getting around)

## Run locally

Any static file server works. From the repo root:

```bash
# Python
python3 -m http.server 8000

# or Node
npx --yes serve -l 8000
```

Open [http://localhost:8000](http://localhost:8000).

## Stack

Static HTML, CSS, and a small `js/main.js` for navigation and scroll reveals. Fonts load from Google Fonts (Fraunces + Sora). Imagery is freely licensed Florence photography (Unsplash, Pexels, Wikimedia Commons) stored under `images/` — see `images/ATTRIBUTION.md`.
