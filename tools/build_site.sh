#!/usr/bin/env bash
# Assembles the published site: only the files the pages use, with the deploy
# version in every module, stylesheet, icon and data URL. GitHub Pages lets
# browsers cache files for 10 minutes; versioned URLs keep all files of a page
# from one deploy. tools/build_pages.py pre-renders the chapter pages, the
# index and the sitemap for search engines. Used by .github/workflows/pages.yml.
# Usage: tools/build_site.sh <output dir> <version> [<base url>]
set -euo pipefail
out=$1
version=$2
base=${3:-https://pavelsupenko.github.io/worm-uk}

rm -rf "$out"
mkdir -p "$out"
cp -R index.html chapter_template.html glossary.html styles.css manifest.webmanifest sw.js js assets texts "$out"/
python3 tools/build_pages.py "$out" "$base"

perl -pi -e "s#(from '\./[\w-]+\.js)'#\1?v=$version'#g" "$out"/js/*.js
perl -pi -e "s#((?:src|href)=\"(?:js/[\w-]+\.js|styles\.css|assets/[\w-]+\.svg))#\1?v=$version#g" "$out"/*.html
perl -pi -e "s#export const VERSION = 'dev'#export const VERSION = '$version'#" "$out"/js/version.js
grep -q "VERSION = '$version'" "$out"/js/version.js

# The service worker changes with every deploy, so browsers install the new one
# and cache this deploy's files for offline reading
perl -pi -e "s#const VERSION = 'dev'#const VERSION = '$version'#" "$out"/sw.js
grep -q "VERSION = '$version'" "$out"/sw.js
