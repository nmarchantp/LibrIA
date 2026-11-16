# Literary character portraits

Original illustrated interpretations for the curated LibrIA character selector:

- Once Upon a Broken Heart / Érase una vez un corazón roto: Jacks, Evangeline Fox, Apollo.
- A Court of Thorns and Roses / Una corte de rosas y espinas: Rhysand, Feyre Archeron, Tamlin.

This is an initial selection, not an exhaustive cast. Characters are explicitly associated with existing local works in migration `0097_literary_characters`. No characters from unrelated works appear as fallbacks. New works require their own catalog entries. Administrators can add a named character and upload its portrait through `POST /api/admin/catalog/works/{work_id}/characters`, multipart fields `name` and `portrait`. Readers only select catalog characters.

Images were generated with the imagegen skill and encoded as WebP, preserving composition and dimensions. PNG originals remain in the Codex generated-images directory. Shared prompt: Original illustrated literary character portrait interpretation. Vertical head and shoulders, 3:4 ratio, elegant realistic painterly fantasy book illustration, richly detailed hair and fabrics, softly lit face, restrained warm rim lighting. Moody dark plum neutral blurred background, no landscape, text, watermark or border. Face fills frame for a small character gallery. Fictional character, not a real actor. Cohesive premium fantasy artwork.

Character prompt details: Jacks has tousled blond hair, pale blue eyes, dark tailored coat and a red apple; Evangeline has rose-gold hair and a cream/blush gown; Apollo has curly dark hair and an ivory/gold royal coat; Rhysand has black hair, violet eyes, pointed ears and a black jacket; Feyre has golden-brown hair, blue-grey eyes and a midnight-blue dress; Tamlin has long blond hair, green eyes, pointed ears and an emerald tunic. These portraits are artistic interpretations, not official artwork.

Book and character context: [Hachette](https://adaptive.hachettelearning.com/titles/stephanie-garber-2/once-upon-a-broken-heart/9781399643887/), [Bloomsbury](https://www.bloomsbury.com/in/discover/sarah-j-maas/a-court-of-thorns-and-roses/).
