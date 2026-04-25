# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-04-25

First stable release.

A Calibre plugin that sends books from your library to your reMarkable
tablet via the desktop app, converts EPUBs to reMarkable-tuned PDFs,
and syncs reading positions back to Calibre.

### Added

- **Send to reMarkable** — selected books land in the desktop app's
  local store and sync to your tablet on next app launch.
- **Export as PDF…** — save the same reMarkable-tuned PDF anywhere on
  disk, no device required (useful for previewing or as a fallback
  upload path).
- **EPUB → PDF conversion** tuned per device (reMarkable 2, Paper Pro,
  Paper Pro Move): configurable font family, size, line height, and
  per-edge margins, plus a configurable page footer.
- **Full-bleed cover** inserted as the first page (top-aligned, padded
  with the cover's dominant edge color).
- **Reading position sync** — pull progress, current page, and
  last-read timestamp back into Calibre custom columns.
- **Smart document naming**: `Series-Number Title - Author`.

### Requirements

- Calibre 5.0+ (tested on Calibre 9.7).
- The [reMarkable desktop app](https://remarkable.com/desktop)
  installed and signed in. **A free reMarkable Connect account is
  enough — no paid subscription required.**
- After sending books, **quit and restart the desktop app** so it picks
  up the new documents and uploads them to your tablet.

### Notes

- Developed and tested on **macOS**. Windows and Linux code paths exist
  but are currently untested — feedback welcome.
- See the [README](README.md) for the full feature list, settings
  reference, and reading-position sync setup.

Inspired by the [Remarcal](https://remarcal.net/) team's work.

[1.0.0]: https://github.com/mremond/calibre-remarkable/releases/tag/v1.0.0
