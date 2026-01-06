# Strip vs Print Contract

## Purpose

Photobooth produces **two related but distinct image artifacts** during session finalization:

1. **Strip (display strip)**  
   A framed, standalone digital photostrip intended for:
    - UI display
    - Guest download
    - Archival storage
    - Future digital reuse

2. **Print (physical print sheet)**  
   A printer-optimized composite containing:
    - Two unframed strips
    - A center cut gutter
    - Print-only QR and retrieval text

**Key principle:**  
Digital presentation and physical printing have **different constraints** and therefore **different artifacts**.

---

## Terminology

- **Photo**: One captured camera image (horizontal, original camera aspect ratio).
- **Logo tile**: The final tile in the strip, treated identically to a photo tile.
- **Tile**: One content slot in a strip (photo or logo).
- **Strip-to-print**: An unframed strip used only for physical print composition.
- **Strip (display strip)**: A framed wrapper around the strip-to-print artifact.
- **Cut gutter**: Intentional white space between printed strips to allow safe cutting.
- **Printer margin**: White border imposed by the Canon SELPHY hardware.

---

## Strip Artifacts

### 1. Strip-to-Print (Internal Artifact)

This artifact exists **only** to support print composition.

#### Characteristics

- **No outer borders**
- **No top or bottom padding**
- Contains only:
    - 3 photo tiles
    - 1 logo tile
    - Internal separators between tiles

#### Dimensions

- **Width:** `558 px`
- **Height:** `1536 px`

Derived from:

- Tile size: `558 × 372` (3:2 aspect ratio)
- Tiles: `372 × 4 = 1488`
- Separators: `16 × 3 = 48`
- Total height: `1488 + 48 = 1536`

This artifact is **never printed directly**.

---

### 2. Strip (Display / Download Artifact)

This is the canonical session strip stored as `strip.jpg`.

#### Characteristics

- Wraps the strip-to-print artifact
- Adds a consistent outer frame for digital presentation
- Visually balanced when viewed standalone

#### Dimensions

- **Width:** `590 px`
- **Height:** `1568 px`

Derived from:

- Strip-to-print size: `558 × 1536`
- Outer padding: `16 px` on all sides

This strip is used for:

- UI preview
- Download
- Archival storage

---

## Print Artifact

### Purpose

The print artifact is optimized specifically for the **Canon SELPHY CP1500**, accounting for:

- Forced printer margins
- Physical cutting tolerance
- Borderless driver behavior
- Visual symmetry after cutting

---

### Print Canvas

- **Final image size:** `1181 × 1748 px`
- **DPI metadata:** `300 DPI`
- **Orientation:** Portrait
- **Background:** White

This size was empirically validated as the most stable output size for the SELPHY.

---

### Horizontal Layout

- Two strip-to-print artifacts placed side-by-side
- **Center cut gutter:** `65 px` (white)
- No outer framing — printer margins provide edge padding

```bash
558 px strip | 65 px gutter | 558 px strip = 1181 px
```

The center gutter:

- Absorbs cutting inaccuracies
- Prevents visible seams
- Ensures symmetry post-cut

---

### Vertical Layout

From top to bottom:

1. **Strip-to-print content**  
   Height: `1536 px`

2. **Separator space**  
   Height: `16 px`  
   (acts as visual separation from QR content)

3. **QR / retrieval area**  
   Height: `196 px`

Total:

```bash
1536 + 16 + 196 = 1748 px
```

No additional top or bottom padding is added — printer margins are relied upon intentionally.

---

## QR / Retrieval Area

Each printed strip includes a retrieval area directly beneath it.

### Alignment

- Left edge aligns with strip content (not printer edge)
- No outer framing
- Fully contained within printable area

### Contents

- **QR code**
    - Square
    - Left-aligned
    - Sized to retrieval area height
- **Text**
    - “Find your photos online”
    - “saperstonestudios.com”

The QR code and text are **print-only** and never appear on the digital strip.

---

## Printer Margin Strategy (Intentional)

The Canon SELPHY CP1500 imposes unavoidable margins (~32 px per side).

Instead of fighting this behavior:

- No artificial outer borders are added
- Printer margins are treated as part of the visual frame
- Center gutter and internal spacing are designed to match this margin visually

This produces:

- Symmetric strips after cutting
- No over-bleed
- Professional, predictable results

---

## Invariants

- Camera photos are **never cropped or distorted**
- Strip-to-print artifact has **no outer padding**
- Display strip always wraps strip-to-print with `16 px` framing
- Print artifact is generated at exact pixel size and DPI
- Print layout is deterministic and printer-validated

---

## Configuration Notes

All dimensions are defined in layout configuration code.

If printer behavior changes in the future:

- Only layout constants should change
- Strip vs print responsibilities must remain separated

This contract is the authoritative reference for:

- Imaging code
- Unit tests
- Print validation
