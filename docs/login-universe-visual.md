# Login universe illustration

Generated using the built-in imagegen tool, editing the user-provided visual reference to remove its embedded UI. No backend, authentication, database, or navigation changes.

Assets:
- `apps/web/public/images/login-universe/fantasy-sky-v1.webp` — 1812 × 868, 174604 bytes.
- `apps/web/public/images/login-universe/fantasy-sky-small-v1.webp` — 1024 × 491, 45772 bytes.

The illustration supplies textured nebulae, the cat, castle, arched bridge, organic hills, foliage, fireflies, and book constellation. Independent CSS/WAAPI layers supply twinkling stars, 14 desktop luceros, soft atmospheric light, and a single shooting star every 12–25 seconds. All moving layers respect reduced-motion and remain behind the form. The illustration itself does not move.

Generation prompt:

> Use case: precise-object-edit. Edit the attached LibrIAverse fantasy login reference into a production website BACKGROUND ONLY illustration. Preserve its very wide panoramic approximately 2.08:1 composition, detailed painterly violet fantasy atmosphere, rich textured purple and magenta nebula sky occupying upper 75%, luminous pink lavender horizon, layered organic misty hills, rim-lit sitting cat on left hill at 14% width 65% height, gothic fantasy castle with warm lit windows and arched bridge on right hill at 90% width, foreground dark leafy vegetation framing bottom corners and upper left, tiny warm fireflies, delicate glowing OPEN BOOK CONSTELLATION at upper right. REMOVE the entire central login card, ALL text, ALL buttons, ALL inputs and the little logo above the card. Seamlessly fill their former central area with matching violet starry sky and distant mist landscape; center must stay unobstructed for a real HTML form. Remove the two large shooting stars so the website will animate them separately. Keep numerous fine static stars and subtle 4-point glints, but no aggressive bloom. No UI, no lettering, no watermark, no logos. Faithfully preserve the lush illustrated reference instead of simplifying to geometric mountains or flat gradients. High resolution landscape asset, wide 2.08:1 framing.

Screenshots: `artifacts/login-universe/chrome-1792.png` (1792 × 859) and `chrome-390.png` (390 × 844). Edge equivalents use the `edge-` prefix.

Remaining differences: illustration is an edited derivative rather than a pixel-identical reproduction; the header book mark is a live Lucide book/sparkle symbol and the Google link includes a multicolor vector icon. On phones, the lateral cat/castle are intentionally cropped. No features depend on them. Tests mock invalid credentials to verify the login payload and error state; they do not perform a live Google OAuth sign-in. Safari and Firefox were unavailable.

Animation follow-up: tested actual opacity changes in stars and luceros, behind-card shooting-star layering, and explicit activation/pause with system reduced motion enabled. The first shooting star appears after 1.5 seconds; subsequent appearances remain 12?25 seconds apart. Reduced motion is respected by default and can be overridden explicitly using the visible animation control.
