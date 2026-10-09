#!/usr/bin/env bash
# Assembles the published site: only the files the pages use, with the deploy
# version in every module, stylesheet, icon and data URL. GitHub Pages lets
# browsers cache files for 10 minutes; versioned URLs keep all files of a page
# from one deploy. Used by .github/workflows/pages.yml.
# Usage: tools/build_site.sh <output dir> <version>
set -euo pipefail
out=$1
version=$2

rm -rf "$out"
mkdir -p "$out"
cp -R index.html chapter_template.html styles.css js assets texts audio "$out"/

perl -pi -e "s#(from '\./[\w-]+\.js)'#\1?v=$version'#g" "$out"/js/*.js
perl -pi -e "s#((?:src|href)=\"(?:js/[\w-]+\.js|styles\.css|assets/[\w-]+\.svg))#\1?v=$version#g" "$out"/*.html
perl -pi -e "s#export const VERSION = 'dev'#export const VERSION = '$version'#" "$out"/js/version.js
grep -q "VERSION = '$version'" "$out"/js/version.js
