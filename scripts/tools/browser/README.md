# Browser Tools

Minimal CDP tools for collaborative site exploration. All scripts are globally available.

## Start Chrome

```bash
./start.js              # Fresh profile
./start.js --profile    # Copy your profile (cookies, logins)
```

Start Chrome on `:9222` with remote debugging.

## Navigate

```bash
./nav.js https://example.com
./nav.js https://example.com --new
```

Navigate current tab or open new tab.

## Evaluate JavaScript

```bash
./eval.js 'document.title'
./eval.js 'document.querySelectorAll("a").length'
```

Execute JavaScript in active tab (async context).

## Screenshot

```bash
./screenshot.js
```

Screenshot current viewport, returns temp file path.

## Pick Elements

```bash
./pick.js "Click the submit button"
```

Interactive element picker. Click to select, Cmd/Ctrl+Click for multi-select, Enter to finish.

## Cookies

```bash
./cookies.js                    # Get all cookies for current page
./cookies.js example.com        # Get cookies for specific domain
```

Extract HTTP-only cookies via CDP.

## Setup

Requires `puppeteer-core`:

```bash
cd ~/.factory/skills/browser && npm install puppeteer-core
```

## Workflow

1. Start Chrome with `./start.js --profile` to mirror your authenticated state.
2. Navigate via `./nav.js https://target.app` or open secondary tabs with `--new`.
3. Inspect the DOM using `./eval.js` for quick counts, attribute checks, or extracting JSON.
4. Capture artifacts with `./screenshot.js` for visual proof or `./pick.js` for precise selectors.
5. Extract cookies with `./cookies.js` if needed for deterministic scrapers.

## Verification

- `./start.js --profile` should print `✓ Chrome started on :9222 with your profile`.
- `./nav.js https://example.com` should confirm navigation.
- `./eval.js 'document.title'` should echo the current page title.
- `./screenshot.js` should output a valid PNG path under your system temp directory.

If any step fails, rerun `start.js`, confirm Chrome is listening on `localhost:9222/json/version`, and ensure `puppeteer-core` is installed.
