# Extended profile panoramas

Created 23 new, individually referenced scene extensions using the built-in imagegen tool and the imagegen skill. The existing approved Pacto de Sangre panorama remains in use. Final assets: `apps/web/public/images/profile-panoramas-v4/{theme-id}.webp`.

All sources and the exact prompt for every image are in [generation-manifest.json](generation-manifest.json). Output dimensions and sizes are in [assets.json](assets.json). [contact-sheet.jpg](contact-sheet.jpg) shows the 23 illustrations together. PNG generation originals remain at their default Codex paths; project assets are encoded as WebP without cropping, scaling, stretching or creative postprocessing.

Shared prompt intent: extend each reference scene toward the right, preserve its subjects, palette, lighting and perspective, add coherent scenery, avoid enlarging or duplicating the main subject, and leave framing room for a shallow profile header. A 5:1 canvas was requested; the generated outputs retain a 3:1 format, so desktop rendering fits the illustration to the header height and fades its left edge into the theme background. This preserves the entire vertical composition instead of enlarging it to fill the width.

Profile-only mapping: `apps/web/src/theme/profilePanoramaAssets.json`. Original mural and public-profile banner mappings remain available. The existing side fades follow the counters and message shortcut; the image center has no global brightness or blur filter. Desktop placement uses the expanded right-hand scenery. Narrow screens use a dedicated focal position. Missing panorama assets fall back to the original banner of the same theme.

Validation: decoded assets and header layout in 24 desktop themes and four representative mobile themes; desktop image proportions and height; no horizontal overflow; profile card alignment; production build. Per-theme rendered screenshots are in `artifacts/profile-panorama/`.
