# ROADMAP

## Completed

- [x] Check if the file has been already generated in the target dir and prompt to ask if we want to override it
- [x] Add ability to define conversion parameters that work generally well for the RMPP
- [x] Ability to choose remarkable device type (automatic resolution parameters)
- [x] Font selector to choose among installed fonts
- [x] Detect and warn if the reMarkable app is not installed
- [x] Default action for the button: Send to reMarkable
- [x] Force stop / start the reMarkable app if it was already running
- [x] Reading position sync from reMarkable to Calibre custom columns
- [x] UUID-based sync matching (only syncs books sent from Calibre)
- [x] Reading Goal plugin compatibility (0-100 scale for progress, shareable columns)
- [x] Document naming convention: "Series-Number Title - Author"
- [x] Full-bleed cover pages for EPUB conversion (top-aligned, dominant color padding)

## TODO
- [ ] Make the UUID column optional but recommended. If it does not exist, it will fallback to sync based on file name but will be less accurate.
- [ ] Make the position sync with Calibre bidirectional so that I can update the position on a book I have read on KOreader in between reMarkable read session. Note: KOreader sync on a scale of 0-1 the percentage read.
- [ ] Investigate running conversion as background task (ThreadedJob) without Qt crash
- [ ] I18N
- [ ] Make the reMarkable directory be seen like a device that can be mounted if present ? It would allow us to see which books have been uploaded already.