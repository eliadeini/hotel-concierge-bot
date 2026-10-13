# `app/ui/hotel_assets/` — private per-hotel branding images

## Convention
One subfolder per `hotel_id`, e.g.:

```
app/ui/hotel_assets/
  <hotel_id>/
    logo.png
    background.jpg
```

Place a hotel's logo/background image files directly inside its subfolder,
using whatever file names you like. Point `HotelWebPage.logo_file` /
`background_file` (set via `PUT /admin/hotels/{hotel_id}/web-page`, see
`app/ui/README.md`) at the exact file name — the page then resolves it to
`/hotel-assets/<hotel_id>/<file>` at render time (served by the static
mount in `app/main.py`). No name/path other than the plain file name is
ever stored in the database or in code.

## Private by default — nothing in here is committed
Every file inside a hotel's subfolder is gitignored (see `.gitignore`'s
`app/ui/hotel_assets/*/*` rule) — this file is the only tracked thing in
this directory, same convention as `app/knowledge/hotel_skills/` and
`app/knowledge/files/<region>/`. A new hotel's images need no `.gitignore`
edit to stay private.

## Getting images onto the server
Local files here aren't automatically live anywhere — run
`deploy/sync-private-data.sh` to push them (along with the other private
knowledge/skill content) to the server over SSH, bypassing GitHub
entirely. That script copies image files byte-for-byte (no text-mode line
ending fix, which is only applied to `.md`/`.txt`/`.yaml`/`.yml` files —
applying it to a PNG/JPG would corrupt it).
