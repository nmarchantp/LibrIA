# Auth narrative transitions

The shared `AuthJourneyProvider` wraps routes and survives navigation. `SessionGate` holds the guest form while a successful login's visual journey completes. API calls, token handling, password validation, endpoints, and destination filtering remain unchanged.

- Login: existing castle scene, 900 ms zoom toward 94%/65%, after successful authentication only. Failed requests never start the animation.
- Login → registration: 900 ms zoom toward the existing sky book at 86%/17%, warm portal light, crossfade to the library.
- Registration → login: reverse library fade, preserving the validated `next` destination.
- Reduced motion: 180 ms opacity-only scene change. Registration maintains name, email, password, confirmation, strength, and validation messages.
- Timers are cleaned up, duplicate transitions are locked, and interaction is inert only during the short scene playback.

New assets, built-in imagegen (no API key or external dependencies):
- `apps/web/public/images/login-universe/magic-library-v1.webp`
- `apps/web/public/images/login-universe/magic-library-small-v1.webp`

Generation prompt:

> Use case: illustration-story. Production website background ONLY, wide panoramic 2.08:1 high-resolution painterly fantasy illustration for LibrIAverse registration page. Interior of an enchanting magical library, deep indigo and violet architecture, lavender wooden bookshelves full of antique books on both lateral sides, rolled parchment scrolls, subtle glowing dust motes, warm pink gold lamps and magical booklight, welcoming quiet atmosphere. One open luminous book on a small reading desk toward lower left, soft purple luminous arched doorway and tall window to the right. Center vertical 30% of image must be calm low-detail darker violet atmospheric space unobstructed for a real HTML registration card. Depth via shelves receding into dim warm lavender haze. Refined whimsical painted fantasy concept art matching a violet night castle landscape, organic detail rather than flat geometry. Rich but not cluttered, coherent purple/lavender/indigo palette with subtle golden warm illumination. No people, no letters, no text, no logos, no form, no cards, no buttons, no watermarks.

Validation:
- `npm run test:auth-journey` in Chrome and Edge, with mocked auth responses: failed and successful login, guard continuity during animation, forward/reverse transitions, preserved destination, mismatch rejection, registration error, reduced motion, seven desktop/tablet/phone dimensions including landscape and a shortened keyboard-sized viewport.
- `tests/login-universe.mjs`: existing login behavior and ten responsive sizes.
- ESLint on changed components/tests and Vite production build passed.
- Screenshots: `artifacts/auth-journey/chrome-register-1792.png` and `chrome-register-390.png` (Edge equivalents also available).
- Safari and Firefox were not available; no live credentials or Google OAuth were exercised.
