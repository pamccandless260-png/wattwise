# Wattwise

Auto-refreshing portable power station comparison site. Static HTML, standard-library Python, no dependencies.

- `fetch.py` pulls product feeds listed in `sources.json` into `data/products.json`
- `build.py` generates `dist/` (home, shortlists from `config.json`, product pages, disclosure, sitemap)
- `.github/workflows/refresh.yml` runs fetch + build daily and commits changed data
- Netlify rebuilds on every commit (`netlify.toml`)

## Run locally
    python3 build.py && python3 -m http.server -d dist

## Go live
1. Rename the site in `config.json` and set `base_url`.
2. Replace the sample products: enable a source in `sources.json` (set its feed URL as a repo secret and add it to the workflow `env`), or edit `data/products.json` by hand.
3. Push to GitHub, connect the repo to Netlify, submit `/sitemap.xml` to Google Search Console.
