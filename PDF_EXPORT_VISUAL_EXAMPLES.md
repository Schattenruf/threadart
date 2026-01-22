"""
Visual Example of PDF Export Output Structure

This file shows what the generated PDF will look like.
"""

# ============================================================================
# EXAMPLE 1: Small Project (100 lines, 2 colors)
# ============================================================================

"""
PDF: my_art_instructions_01.pdf

Page 1 (54 cells, 3x18 layout):

┌─────────────────────────────────────────────────────────────────────┐
│ ==================================================                 │
│ Progress: 0/100                                                     │
│ ==================================================                 │
│ Black (1/2)                                                         │
│ ==================================================                 │
│ From: Hanger   0 L                                                  │
│ To:   Hanger  50 R                                                  │
│ From: Hanger  50 R                                                  │
│ To:   Hanger 100 L                                                  │
│ From: Hanger 100 L                                                  │
│ To:   Hanger 150 R                                                  │
│ ... (15 more instructions)                                          │
│ ==================================================                 │
│ Completed: Black group 1/2                                          │
│                                                                      │
│ ==================================================                 │
│ Progress: 45/100                                                    │
│ ==================================================                 │
│ Red (1/1)                                                           │
│ ==================================================                 │
│ From: Hanger 160 L                                                  │
│ To:   Hanger 190 R                                                  │
│ ... (10 more instructions)                                          │
└─────────────────────────────────────────────────────────────────────┘

STATISTICS:
============================================================
THREAD ART STATISTICS
============================================================
Total lines: 100

Lines per color:
    Black               :    50 lines ( 50.0%)
    Red                 :    50 lines ( 50.0%)

Total hangers needed: 95
Average lines per hanger: 1.1
Most used hanger: Hanger 42 (12 connections)
Least used hanger: Hanger 5 (1 connections)
"""


# ============================================================================
# EXAMPLE 2: Large Project (10000 lines, 5 colors)
# ============================================================================

"""
PDF: stag_instructions_01.pdf (10 pages)

PAGES GENERATED:
- Pages 1-8: Black (4 groups, 2680 lines total)
- Pages 8-9: Brown (2 groups, 1890 lines)
- Pages 9-10: Red (1 group, 1200 lines)
- etc.

SINGLE PAGE SAMPLE:
┌─────────────────────────────────────────────────────────────────────┐
│ Column 1           │ Column 2           │ Column 3             │
├─────────────────────┼─────────────────────┼──────────────────────┤
│ ===========         │ ===========         │ ============         │
│ Progress: 5340/10k  │ From: Hng  22 L     │ From: Hng 140 R      │
│ ===========         │ To:   Hng  73 R     │ To:   Hng 175 L      │
│ Black (3/4)         │ From: Hng  73 R     │ From: Hng 175 L      │
│ ===========         │ To:   Hng 120 L     │ To:   Hng 200 R      │
│ From: Hng   0 L     │ From: Hng 120 L     │ From: Hng 200 R      │
│ To:   Hng  51 R     │ To:   Hng 142 R     │ To:   Hng 245 L      │
│ From: Hng  51 R     │ From: Hng 142 R     │ From: Hng 245 L      │
│ To:   Hng  82 L     │ To:   Hng 178 L     │ To:   Hng 280 R      │
│ From: Hng  82 L     │ From: Hng 178 L     │ From: Hng 280 R      │
│ To:   Hng 104 R     │ To:   Hng 200 R     │ To:   Hng 299 L      │
│ From: Hng 104 R     │ From: Hng 200 R     │ From: Hng 299 L      │
│ To:   Hng 156 L     │ To:   Hng 250 L     │ To:   Hng 310 R      │
│ From: Hng 156 L     │ From: Hng 250 L     │ From: Hng 310 R      │
│ To:   Hng 189 R     │ To:   Hng 280 R     │ To:   Hng 320 L      │
│ From: Hng 189 R     │ From: Hng 280 R     │ From: Hng 320 L      │
│ To:   Hng 220 L     │ To:   Hng 300 L     │ To:   Hng 285 R      │
│ From: Hng 220 L     │                      │ From: Hng 285 R      │
│ To:   Hng 245 R     │ ===========         │ To:   Hng 240 L      │
│ From: Hng 245 R     │ Completed           │ ===========          │
│ To:   Hng 270 L     │ Black group 3/4     │ Completed            │
│ ===========         │                      │ Black group 3/4      │
│ Completed           │                      │                      │
│ Black group 3/4     │                      │                      │
└─────────────────────┴─────────────────────┴──────────────────────┘

FINAL STATISTICS:
============================================================
THREAD ART STATISTICS
============================================================
Total lines: 10000

Lines per color:
    Black               :  6800 lines ( 68.0%)
    Brown               :  1890 lines ( 18.9%)
    Red                 :   900 lines (  9.0%)
    Gold                :   300 lines (  3.0%)
    White               :   110 lines (  1.1%)

Total hangers needed: 160
Average lines per hanger: 8.4
Most used hanger: Hanger 87 (45 connections)
Least used hanger: Hanger 12 (1 connection)
"""


# ============================================================================
# EXAMPLE 3: Node Formatting
# ============================================================================

"""
How nodes are formatted for display:

Input: node indices from drawing algorithm
  from_pin = 42, to_pin = 87

Conversion (PictureHangerFormatter):
  42 = Hanger 21 Left (42 // 2 = 21, 42 % 2 = 0 → L)
  87 = Hanger 43 Right (87 // 2 = 43, 87 % 2 = 1 → R)

Display in PDF:
  From: Hanger  21 L
  To:   Hanger  43 R

Example mappings:
  0  → Hanger   0 L (left position of hanger 0)
  1  → Hanger   0 R (right position of hanger 0)
  2  → Hanger   1 L (left position of hanger 1)
  3  → Hanger   1 R (right position of hanger 1)
  ...
  318 → Hanger 159 L
  319 → Hanger 159 R
"""


# ============================================================================
# EXAMPLE 4: Color Grouping Strategy
# ============================================================================

"""
If user selected subset of colors:
  - User selected: Red-1, Red-2, Red-3 (from 5 reds detected)
  - Algorithm merges unselected reds to nearest selected red

Example:
  Detected: Red-1 (5%), Red-2 (8%), Red-3 (4%), Red-4 (3%), Red-5 (2%)
  Selected: Red-2, Red-3
  
  Merge strategy:
    Red-1 (5%) → Nearest: Red-2 (distance=3%) → Red-2 becomes 5+8=13%
    Red-4 (3%) → Nearest: Red-3 (distance=1%) → Red-3 becomes 4+3=7%
    Red-5 (2%) → Nearest: Red-3 (distance=2%) → Red-3 becomes 7+2=9%
    
  Final: Red-2 (13%), Red-3 (9%)

This is reflected in the PDF:
  Group Order: "...22333222333..."
  Lines distributed accordingly in the instruction sequence
"""


# ============================================================================
# EXAMPLE 5: Streamlit UI Flow
# ============================================================================

"""
User Experience in Streamlit:

1. UPLOAD IMAGE
   ┌─────────────────────────────┐
   │ Choose Image/Demo           │
   │ [Upload / Select Demo]      │
   └─────────────────────────────┘

2. CONFIGURE PARAMETERS
   ┌─────────────────────────────┐
   │ Width: 500                  │
   │ Nodes: 320                  │
   │ Shape: Rectangle            │
   │ Group Orders: "4"           │
   └─────────────────────────────┘

3. SELECT COLORS
   ┌─────────────────────────────┐
   │ Found Colors:               │
   │ [✓] Black (67%)             │
   │ [✓] Red (20%)               │
   │ [✓] Brown (13%)             │
   └─────────────────────────────┘

4. GENERATE
   ┌─────────────────────────────┐
   │ [Generate Thread Art]       │
   │ (Generating lines... 5/10k) │
   └─────────────────────────────┘

5. DOWNLOAD OPTIONS
   ┌─────────────────────────────────────────┐
   │ Download Options                        │
   │ [📊 CSV] [📄 JSON] [🖨️ PDF]            │
   │                                          │
   │ When PDF button clicked:                 │
   │ (Generating PDF... 15 seconds)          │
   │ ✅ PDF generated: art_instructions_01   │
   │                                          │
   │ [💾 Download PDF]                       │
   └─────────────────────────────────────────┘

6. DOWNLOAD & PRINT
   Output: art_instructions_01.pdf (10 pages, 2.5 MB)
   - 54 instructions per page
   - 540 total instructions
   - Ready to print
"""


# ============================================================================
# EXAMPLE 6: File Organization
# ============================================================================

"""
Generated files in outputs_drawing/:

my_stag_01.html                          (preview, interactive)
my_stag_01_sequence.csv                  (raw data)
my_stag_01_sequence.json                 (raw data)
my_stag_instructions_01.pdf              (10 pages, printable)
my_stag_instructions_02.pdf              (different settings)
my_stag_instructions_03.pdf              (etc.)

Auto-incrementing for multiple runs with same name.
"""


# ============================================================================
# EXAMPLE 7: Terminal Output
# ============================================================================

"""
Console output when generating PDF:

$ streamlit run streamlit_app.py

[User clicks "Generate PDF Instructions"]

Generating PDF...
Generated PDF: my_art_instructions_01.pdf

============================================================
THREAD ART STATISTICS
============================================================
Total lines: 10000

Lines per color:
    Black               :  6800 lines ( 68.0%)
    Brown               :  1890 lines ( 18.9%)
    Red                 :   900 lines (  9.0%)
    Gold                :   300 lines (  3.0%)
    White               :   110 lines (  1.1%)

Total hangers needed: 160
Average lines per hanger: 8.4
Most used hanger: Hanger 87 (45 connections)
Least used hanger: Hanger 12 (1 connection)

[PDF download button appears in UI]
"""

if __name__ == "__main__":
    print("This file shows examples of PDF output structure.")
    print("See PDF_EXPORT_QUICKSTART.md for usage instructions.")
