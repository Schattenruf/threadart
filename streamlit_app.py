import base64
import gc
import io
import os
import sys

#print("Working directory:", os.getcwd())
#print("Directory contents:", os.listdir())
import tempfile
import traceback
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

import streamlit as st

# https://info.snowflake.com/streamlit-resource-increase-request.html?ref=blog.streamlit.io


# Set page configuration
st.set_page_config(page_title="Thread Art Generator", page_icon="🧵", layout="wide", initial_sidebar_state="expanded")

# Add parent directory to path so we can import the required modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
sys.path.insert(0, parent_dir)

# for path in Path(parent_dir).iterdir():
#     st.write(path)
#     if not path.is_file():
#         for subpath in path.iterdir():
#             st.write("sub: ", subpath)

#os.chdir(parent_dir)

gc.collect()

from image_color import Img, ThreadArtColorParams
from streamlit.components.v1 import html as st_html
# --- Neue Hilfsfunktion: decompose_image (angepasst für Streamlit) ---
def decompose_image(img_obj, n_lines_total=10000):
"""
   Prints / displays a suggested number of lines per color based on the color histogram.
   Adapted from a Jupyter-style snippet to Streamlit.

   Args:
       img_obj: object that should provide .palette and .color_histogram
                - palette can be a dict: {name: (r,g,b), ...} or a list of (r,g,b)
                - color_histogram can be a dict mapping color-name -> frequency (0..1),
                  or a list of frequencies matching a palette list
       n_lines_total: total number of lines to distribute
   """
pal = getattr(img_obj, "palette", None)
hist = getattr(img_obj, "color_histogram", None)

if pal is None or hist is None:
st.warning("Cannot compute suggestions: object lacks 'palette' or 'color_histogram' attributes.")
return

def render_color_line(color_tuple, name_str, n_lines):
r, g, b = tuple(int(c) for c in color_tuple)
color_string = str((r, g, b))
# Build an HTML line with a color swatch
swatch = f"<span style='display:inline-block;width:64px;height:16px;background:rgb{(r,g,b)};border:1px solid #333;margin:0 8px;vertical-align:middle'></span>"
text = f"<code>{color_string.ljust(18)}</code>{swatch}<code>{name_str}</code> = {n_lines}"
st.markdown(text, unsafe_allow_html=True)

# Case A: palette is a dict (name -> (r,g,b))
if isinstance(pal, dict):
# Compute n_lines per palette key order
keys = list(pal.keys())
# histogram expected to map same keys to frequencies (0..1)
try:
n_lines_per_color = [int(hist.get(k, 0) * n_lines_total) for k in keys]
except Exception:
st.warning("Unexpected format for color_histogram; expected dict mapping color-name -> frequency.")
return

# Identify index to absorb rounding remainder.
try:
sums = [sum(tuple(pal[k])) for k in keys]
darkest_idx = sums.index(max(sums))
except Exception:
darkest_idx = 0

n_lines_per_color[darkest_idx] += (n_lines_total - sum(n_lines_per_color))

# Display per-color suggestion
max_len_color_name = max(len(k) for k in keys) if keys else 0
for idx, k in enumerate(keys):
render_color_line(pal[k], k.ljust(max_len_color_name), n_lines_per_color[idx])

st.code(f"`n_lines_per_color` for you to copy: {n_lines_per_color}")

# Case B: palette is a list of tuples
elif isinstance(pal, (list, tuple)):
# histogram might be a list/tuple of frequencies with same length
if not isinstance(hist, (list, tuple)):
st.warning("Palette is a list but color_histogram is not a list/tuple; cannot reliably map.")
return

if len(hist) != len(pal):
st.warning("Length mismatch between palette and histogram; cannot reliably compute distribution.")
return

n_lines_per_color = [int(h * n_lines_total) for h in hist]

try:
sums = [sum(tuple(c)) for c in pal]
darkest_idx = sums.index(max(sums))
except Exception:
darkest_idx = 0

n_lines_per_color[darkest_idx] += (n_lines_total - sum(n_lines_per_color))

for idx, c in enumerate(pal):
render_color_line(c, f"Color {idx+1}", n_lines_per_color[idx])

st.code(f"`n_lines_per_color` for you to copy: {n_lines_per_color}")

else:
st.warning("Unrecognized palette format. Expected dict or list of RGB tuples.")
return
# ------------------------------------------------------------------

# Apply custom CSS for a clean, minimalist look
st.markdown(
"""
<style>
   .main .block-container {
       max-width: 1200px;
       padding-top: 2rem;
       padding-bottom: 2rem;
   }
   h1, h2, h3 {
       font-weight: 400;
   }
   .stButton button {
       width: 100%;
   }
   .stSelectbox, .stNumberInput {
       margin-bottom: 0.5rem;
   }
   .color-box {
       display: inline-block;
       width: 20px;
       height: 20px;
       margin-right: 10px;
       border: 1px solid #ccc;
   }
</style>
""",
unsafe_allow_html=True,
)

# Header
st.title("Thread Art Generator")
st.markdown(
"""
_Create beautiful thread art from images with customizable parameters!_

You can create art in 2 ways:

- Upload your own custom image and select parameters using the menu on the left
- Choose a demo image from the dropdown at the top, which also pre-fills all the parameters for you

Once you've chosen one of these options, you can hit the "Generate Thread Art" button at the bottom of the left hand menu, to create your thread art!

Note that the quality of output varies a lot based on small parameter changes, so we encourage you to start by looking at some of the demos and see what works well for them, and then try and upload your own image. We've also included some helpful tips next to each input field to help you understand what they do.
"""
)
# with st.expander("Some tips for creating good thread art"):
#     st.markdown(
# """
# -
# """)

# Initialize session state
if "generated_html" not in st.session_state:
st.session_state.generated_html = None
if "output_name" not in st.session_state:
st.session_state.output_name = None
if "temp_dir" not in st.session_state:
st.session_state.temp_dir = tempfile.TemporaryDirectory()

name = None

# parameters
demo_presets = {
"Custom": {},
"Tiger Demo (fast)": {
"filename": "tiger.jpg",
"name": "tiger_small_01",
"x": 600,
"nodes": 320,
"shape": "Rectangle",
"random_lines": 140,
"darkness": [0.16, 0.16, 0.16, 0.16],
"blur": 4,
"group_orders": "5",
"palette": [
(255, 255, 255),  # white
(255, 130, 0),  # orange
(255, 0, 0),  # red
(0, 0, 0),  # black
],
"lines": [2700, 2000, 650, 5200],
"html_x": 700,
},
"Tiger Demo (slow)": {
"filename": "tiger.jpg",
"name": "tiger_big_01",
"x": 700,
"nodes": 400,
"shape": "Rectangle",
"random_lines": 200,
"darkness": [0.12, 0.12, 0.12, 0.12],
"blur": 4,
"group_orders": "8",
"palette": [
(255, 255, 255),  # white
(255, 130, 0),  # orange
(255, 0, 0),  # red
(0, 0, 0),  # black
],
"lines": [5400, 4000, 2000, 9500],
"html_x": 800,
"html_line_width": 0.11,
},
"Stag Demo (fast)": {
"filename": "stag-large.jpg",
"name": "stag_small_01",
"x": 1200,
"nodes": 360,
"shape": "Rectangle",
"random_lines": 180,
"darkness": [0.14, 0.14, 0.10, 0.11, 0.10],
"blur": 4,
"group_orders": "1,4,2,5,1,4,3,2,5,1,4,3,2,5,3,5",
"palette": [
(255, 255, 255),  # white
(0, 215, 225),  # light_blue
(0, 120, 240),  # mid_blue
(0, 0, 120),  # dark_blue
(0, 0, 0),  # black
],
"lines": [1400, 750, 750, 3000, 6500],
"html_x": 1100,
},
"Stag Demo (slow)": {
"filename": "stag.jpg",
"name": "stag_large_01",
"x": 1400,
"nodes": 400,
"shape": "Rectangle",
"random_lines": 240,
"darkness": [0.14, 0.13, 0.10, 0.10, 0.10],
"blur": 4,
"group_orders": "1,4,2,5,1,4,3,2,5,1,4,3,2,5,3,5",
"palette": [
(255, 255, 255),  # white
(0, 215, 225),  # light_blue
(0, 120, 240),  # mid_blue
(0, 0, 120),  # dark_blue
(0, 0, 0),  # black
],
"lines": [1600, 900, 850, 3300, 8000],
"html_x": 1200,
"html_line_width": 0.11,
},
"Duck Demo": {
"filename": "duck.jpg",
"name": "duck_01",
"x": 660,
"nodes": 360,
"shape": "Rectangle",
"random_lines": 150,
"darkness": [0.12, 0.12, 0.12, 0.12],
"blur": 4,
"group_orders": "1,2,3,1,2,3,4,1,2,3,4,2,3,4,2,4,4",
"palette": [
(255, 255, 255),  # white
(255, 0, 0),  # red
(255, 255, 0),  # yellow
(0, 0, 0),  # black
],
"lines": [1800, 800, 1800, 8000],
"html_x": 1000,
},
"Fish Demo": {
"filename": "fish_sq_2.jpg",
"name": "fish_01",
"x": 1100,
"nodes": 360,
"shape": "Ellipse",
"random_lines": 200,
"darkness": [0.28, 0.25, 0.28, 0.25],
"blur": 4,
"group_orders": "1,1,2,2,3,4,1,2,3,4,4",
"palette": [
(255, 255, 255),  # white
(255, 100, 0),  # orange
(50, 150, 220),  # mid_blue
(0, 0, 0),  # black
],
"lines": [500, 1900, 2100, 3300],
"html_x": 850,
},
"Snake Demo": {
"filename": "snake.png",
"name": "snake_01",
"x": 1200,
"nodes": 360,
"shape": "Rectangle",
"random_lines": 160,
"darkness": [0.12, 0.12, 0.12, 0.14],
"blur": 2,
"group_orders": "1,1,2,2,3,3,4,1,2,3,4,1,2,3,4,1,2,3,4,4,4",
"palette": [
(255, 255, 255),  # white
(255, 255, 0),  # yellow
(255, 0, 0),  # red
(0, 0, 0),  # black
],
"lines": [1300, 1500, 1200, 11500],
"html_x": 1000,
},
"Planets Demo": {
"filename": "planets-1-Ga.png",
"w_filename": "planets-1-GwA.png",
"name": "planets_01",
"x": 1200,
"nodes": 360,
"shape": "Rectangle",
"random_lines": 180,
"darkness": [0.21, 0.21, 0.21, 0.21, 0.21, 0.14],
"blur": 2,
"group_orders": "1,1,1,2,2,2,4,4,3,3,1,2,4,4,3,5,6,2,3,4,5,5,6,6,6",
"palette": [
(255, 255, 255),  # white
(230, 200, 80),  # yellow
(0, 50, 200),  # mid_blue
(255, 0, 0),  # red
(140, 60, 0),  # dark_brown
(0, 0, 0),  # black
],
"lines": [750, 900, 500, 450, 1200, 9200],
"html_x": 1200,
},
}

# Sidebar for parameters
with st.sidebar:
st.header("Parameters")

images = {
"uploaded": None,
"demo": None,
}

# We need to reset stored HTML when this changes
def reset():
st.session_state.generated_html = None
st.session_state.output_name = None
st.session_state.sf = None

# Demo selector
demo_option = st.selectbox(
"Choose a demo or create your own",
demo_presets.keys(),
help="Select a demo to try out the thread art generator with preset parameters. Some of the demos are labelled with (fast) or (long) to indicate how long they will take to generate - the (long) images are larger and more detailed.",
on_change=reset,
)

preset_filename = demo_presets[demo_option].get("filename", None)
preset_w_filename = demo_presets[demo_option].get("w_filename", None)
preset_name = demo_presets[demo_option].get("name", None)
preset_x = demo_presets[demo_option].get("x", None)
preset_html_x = demo_presets[demo_option].get("html_x", None)
preset_html_line_width = demo_presets[demo_option].get("html_line_width", None)
preset_nodes = demo_presets[demo_option].get("nodes", None)
preset_shape = demo_presets[demo_option].get("shape", None)
preset_random_lines = demo_presets[demo_option].get("random_lines", None)
preset_darkness = demo_presets[demo_option].get("darkness", None)
preset_blur = demo_presets[demo_option].get("blur", None)
preset_group_orders = demo_presets[demo_option].get("group_orders", None)
preset_palette = demo_presets[demo_option].get("palette", None)
preset_darkness = demo_presets[demo_option].get("darkness", None)
preset_lines = demo_presets[demo_option].get("lines", None)
preset_step_size = demo_presets[demo_option].get("step_size", None)

# Number of Colors (user control). Placed BEFORE image quantize so suggestions can read it.
num_colors = st.number_input(
"Number of Colors",
min_value=1,
max_value=10,
value=(len(preset_palette) if (preset_palette and isinstance(preset_palette, (list, tuple))) else 3),
key="num_colors_input",
help="We recommend always including black and white, as well as between 1 and 4 other colors depending on your image.",
)

image_selected = False
image = None

if demo_option == "Custom":
# User uploads their own image
uploaded_file = st.file_uploader("Upload an image", type=["jpg", "jpeg", "png"])
if uploaded_file is not None:
image_bytes = uploaded_file.read()
image_selected = True
else:
# Read the image from `images/` and display it
demo_image_path = Path(__file__).parent.parent / "images" / preset_filename
with demo_image_path.open("rb") as f:
image_bytes = f.read()
image_selected = True

if image_selected:
image = Image.open(io.BytesIO(image_bytes))
st.image(
image,
width='stretch',
)
# --- Schnell-Histogramm erzeugen, sobald ein Bild ausgewählt wurde ---
try:
est_n_colors = st.session_state.get("num_colors_input", len(preset_palette) if (preset_palette and isinstance(preset_palette, (list, tuple))) else 3)
# Verkleinern für Geschwindigkeit
thumb_w = 200
thumb_h = max(1, int(image.height * thumb_w / max(1, image.width)))
img_small = image.convert("RGB").resize((thumb_w, thumb_h), Image.BILINEAR)

# Quantisiere auf mehr Farben als gewünscht, damit wir dann mergen können
quant = img_small.quantize(colors=est_n_colors * 3, method=Image.MEDIANCUT)

# quant.getcolors() liefert Liste von (count, palette_index)
colors_info = quant.getcolors(maxcolors=est_n_colors * 3)
palette_list = []
hist_list = []
if colors_info:
# Die Palette der quantisierten Image enthält RGB-Tripel in einer flachen Liste
flat_pal = quant.getpalette()
total_pixels = sum(cnt for cnt, idx in colors_info)
for cnt, idx in colors_info:
# Index im Palette-Array
r = flat_pal[idx * 3]
g = flat_pal[idx * 3 + 1]
b = flat_pal[idx * 3 + 2]
palette_list.append((r, g, b))
hist_list.append(cnt / total_pixels)

            # --- Merge ähnliche Farben zusammen und behalte nur starke Kontraste ---
            # --- Wähle kontrastierende Farben aus (verhindert zu ähnliche Farben) ---
def color_distance(c1, c2):
"""Berechnet Euklidische Distanz zwischen zwei RGB-Farben"""
return ((c1[0] - c2[0])**2 + (c1[1] - c2[1])**2 + (c1[2] - c2[2])**2) ** 0.5

            if palette_list:
                # Minimum Distanz für zwei unterschiedliche Farben (höher = weniger Farben, mehr Kontrast)
                MIN_COLOR_DISTANCE = 60  # Werte zwischen 40-80 sind sinnvoll
            if palette_list and len(palette_list) > est_n_colors:
                # Minimum Distanz zwischen ausgewählten Farben (niedriger = mehr Variation erlaubt)
                MIN_COLOR_DISTANCE = 40  # Werte zwischen 30-60 sind sinnvoll

                merged_palette = []
                merged_hist = []
                # Sortiere erst nach Häufigkeit
                sorted_pairs = sorted(zip(palette_list, hist_list), key=lambda x: x[1], reverse=True)

                for color, freq in zip(palette_list, hist_list):
                    # Prüfe, ob diese Farbe zu einer bereits vorhandenen ähnlich ist
                    merged = False
                    for i, existing_color in enumerate(merged_palette):
                # Greedy-Auswahl: Nimm häufigste Farben, die hinreichend unterschiedlich sind
                selected_palette = []
                selected_hist = []
                
                for color, freq in sorted_pairs:
                    # Prüfe, ob diese Farbe zu ähnlich zu bereits gewählten ist
                    is_distinct = True
                    for existing_color in selected_palette:
if color_distance(color, existing_color) < MIN_COLOR_DISTANCE:
                            # Merge: addiere Frequenz zur existierenden Farbe
                            # Gewichte die Farbe nach Häufigkeit
                            total_freq = merged_hist[i] + freq
                            merged_palette[i] = tuple(
                                int((existing_color[j] * merged_hist[i] + color[j] * freq) / total_freq)
                                for j in range(3)
                            )
                            merged_hist[i] = total_freq
                            merged = True
                            is_distinct = False
break

                    if not merged:
                        merged_palette.append(color)
                        merged_hist.append(freq)
                    if is_distinct:
                        selected_palette.append(color)
                        selected_hist.append(freq)
                    else:
                        # Addiere Häufigkeit zur ähnlichsten Farbe
                        closest_idx = min(range(len(selected_palette)), 
                                        key=lambda i: color_distance(color, selected_palette[i]))
                        selected_hist[closest_idx] += freq
                    
                    # Stoppe, wenn wir genug Farben haben
                    if len(selected_palette) >= est_n_colors:
                        break
                
                # Falls wir zu wenig distinkte Farben gefunden haben, fülle auf
                while len(selected_palette) < est_n_colors and len(sorted_pairs) > len(selected_palette):
                    # Nimm einfach die nächste verfügbare Farbe
                    for color, freq in sorted_pairs:
                        if color not in selected_palette:
                            selected_palette.append(color)
                            selected_hist.append(freq)
                            break

                # Sortiere nach Häufigkeit und nimm die Top est_n_colors
                sorted_pairs = sorted(zip(merged_palette, merged_hist), key=lambda x: x[1], reverse=True)
                palette_list = [p for p, h in sorted_pairs[:est_n_colors]]
                hist_list = [h for p, h in sorted_pairs[:est_n_colors]]
                palette_list = selected_palette[:est_n_colors]
                hist_list = selected_hist[:est_n_colors]

# Renormalisiere Histogramm
total = sum(hist_list)
if total > 0:
hist_list = [h / total for h in hist_list]
            elif palette_list:
                # Wenn wir schon weniger oder gleich est_n_colors haben, behalte alle
                pass

# Falls quantize weniger Farben zurückgibt (oder leer), fallback auf eine gleichverteilte Schätzung
if not palette_list:
palette_list = [(128, 128, 128)] * est_n_colors
hist_list = [1.0 / est_n_colors] * est_n_colors

# Speichere die Schätzung in session_state, damit der Decompose-Button sie nutzen kann
st.session_state.decompose_data = {"palette": palette_list, "color_histogram": hist_list}
except Exception:
st.session_state.decompose_data = None
# -----------------------------------------------------------------

# ======= Add automatic UI suggestions based on quantize result (insert after quantize try/except) =======
try:
# get palette/hist from locals (quantize) or from session_state fallback
if "palette_list" in locals() and "hist_list" in locals():
pl = palette_list
hl = hist_list
else:
dd = st.session_state.get("decompose_data")
if dd:
pl = dd.get("palette", []) or []
hl = dd.get("color_histogram", []) or []
else:
pl = []
hl = []

# Only proceed if we have a palette estimate
if pl:
# Only auto-fill when there isn't already a demo preset palette
if not preset_palette:
DEFAULT_TOTAL_SUGGESTED_LINES = 10000

# normalize palette items to tuples of ints
suggested_palette = [tuple(map(int, c)) for c in pl]

# compute suggested lines; avoid zeros
suggested_lines = [max(100, int(h * DEFAULT_TOTAL_SUGGESTED_LINES)) for h in hl]

# fix rounding remainder by adding to the darkest color (same heuristic as elsewhere)
remainder = DEFAULT_TOTAL_SUGGESTED_LINES - sum(suggested_lines)
if remainder != 0:
try:
sums = [sum(c) for c in suggested_palette]
darkest_idx = sums.index(max(sums))
except Exception:
darkest_idx = 0
suggested_lines[darkest_idx] += remainder

# default darkness values (adjust if you want heuristics here)
suggested_darkness = [0.17] * len(suggested_palette)

# set local preset_* variables used later to render the UI
preset_palette = suggested_palette
preset_lines = suggested_lines
preset_darkness = suggested_darkness

# also keep session_state in sync
st.session_state.decompose_data = {"palette": suggested_palette, "color_histogram": hl}
except Exception:
# don't break the UI if anything fails here
pass
# =======================================================================================================
# Prefill widgets from suggested palette/lines if they are not already set in session_state
try:
if 'preset_palette' in locals() and preset_palette:
for i, col in enumerate(preset_palette):
# color picker expects hex string
hex_col = f"#{int(col[0]):02x}{int(col[1]):02x}{int(col[2]):02x}"
# color picker key: color_pick_{i}
key_color = f"color_pick_{i}"
if key_color not in st.session_state:
st.session_state[key_color] = hex_col

if 'preset_lines' in locals() and preset_lines:
for i, val in enumerate(preset_lines):
key_lines = f"lines_{i}"
# only set if the widget key not already present (so we don't clobber user edits)
if key_lines not in st.session_state:
st.session_state[key_lines] = int(val)

if 'preset_darkness' in locals() and preset_darkness:
for i, val in enumerate(preset_darkness):
key_dark = f"darkness_{i}"
if key_dark not in st.session_state:
st.session_state[key_dark] = float(val)

# Optional: ensure the visible "Number of Colors" control shows the suggested number
# (this requires you to give the num_colors number_input a key; see note below)
# desired_num_colors = len(preset_palette)
# if "num_colors_input" not in st.session_state:
#     st.session_state["num_colors_input"] = desired_num_colors
except Exception:
# fail silently - do not break the UI
pass

# Basic parameters
col1, col2, col3 = st.columns(3)
with col1:
x_size = st.number_input(
"Width",
min_value=100,
max_value=1400,
value=preset_x or 600,
help="The width we reshape the image to before creating the art. Higher-width images take more time (and require more lines) but will look better.",
)
with col2:
n_nodes = st.number_input(
"Number of Nodes",
min_value=60,
max_value=400,
value=preset_nodes or 320,
step=20,
help="Number of nodes on the perimeter of the image to generate lines between. This increases resolution but also time to create the image.",
)
n_nodes_real = n_nodes + (4 - n_nodes % 4)  # Ensure n_nodes is a multiple of 4
with col3:
shape = st.selectbox(
"Shape",
["Rectangle", "Ellipse"],
index=0 if preset_shape == "Rectangle" or preset_shape is None else 1,
help="Options are Rectangle or Ellipse. If Ellipse then the nodes we generate lines between will be placed in an ellipse shape (cropping the image appropriately).",
)

# Advanced parameters
with st.expander("Advanced Parameters"):
n_random_lines = st.number_input(
"Random Lines to Consider",
min_value=10,
max_value=500,
value=preset_random_lines or 150,
help="Number of random lines to consider each time we draw a new line. More lines takes longer, but leads to a better looking image (although past about 150 you get diminishing returns).",
)

blur_rad = st.number_input(
"Blur Radius",
min_value=0,
max_value=20,
value=preset_blur or 4,
help="Amount we blur the monochrome images when we split them off from the main image. You can try increasing this if the lines seem too sharp and you want the color gradients to be smoother, but mostly this doesn't have a big effect on the final output.",
)

group_orders = st.text_input(
"Group Orders",
value=preset_group_orders or "4",
help="""Sequence we'll use to layer the colored lines onto the image. If this is a comma-separated list of integers, they are interpreted as the indices of colors you've listed, e.g. if our colors were white, red and black then '1,2,1,2,3' means we'd add half the white lines (1), then half the red lines (2), then half the white again (1), then half the red again (2), then all the black lines on top (3). Alternatively, if you just enter a single number then this will be interpreted as a number of loops over all colors, e.g. for three colors, '4' would be interpreted as the sequence '1,2,3,1,2,3,1,2,3,1,2,3'.

We have 2 main tips here: firstly make sure to include enough loops so that no one color dominates the other colors by going on top and masking them all, and secondly make sure the darker colors are on top since this looks a lot better (in particular, we strongly recommend having black on top).
""",
)

# Color management
st.subheader("Colors")

if preset_palette:
palette = list(preset_palette)
n_lines = preset_lines
darkness_values = list(preset_darkness)
else:
# Default to 3 colors if custom
palette = [(0, 0, 0), (255, 0, 0), (255, 255, 255)]
n_lines = [1000, 800, 600]
darkness_values = [0.17, 0.17, 0.17]

# Adjust palette based on num_colors (already defined above)
num_colors_current = len(palette)
if num_colors != num_colors_current:
if num_colors > num_colors_current:
# Add more colors
for i in range(num_colors_current, num_colors):
palette.append([128, 128, 128])  # Default to gray
n_lines.append(1000)  # Default number of lines
darkness_values.append(0.17)
else:
# Remove colors
palette = palette[:num_colors]
n_lines = n_lines[:num_colors]
darkness_values = darkness_values[:num_colors]

# Color editors
new_palette = []
new_n_lines = []
new_darkness = []

for i in range(num_colors):
# st.markdown(f"##### Color {i + 1}")
col1, col2, col3 = st.columns([1, 2, 2])

with col1:
color_hex = st.color_picker(
"Color",
f"#{palette[i][0]:02x}{palette[i][1]:02x}{palette[i][2]:02x}",
key=f"color_pick_{i}",
)
r, g, b = int(color_hex[1:3], 16), int(color_hex[3:5], 16), int(color_hex[5:7], 16)

with col2:
lines = st.number_input(
"Lines",
min_value=100,
max_value=15000,
value=n_lines[i],
key=f"lines_{i}",
help="The total number of lines we'll draw for this color. 3 guidelines to consider here: (1) the line numbers should be roughly in proportion with their density in your image, (2) you should make sure to include a lot of black lines for most images because that's an important component of making a good piece of thread art, and (3) you should aim for about 6000 - 20000 total lues when summed over all colors (the exact number depends on some of your other parameters, and how detailed you want the piece to be).",
)

with col3:
darkness = st.number_input(
"Darkness",
min_value=0.05,
max_value=0.3,
value=darkness_values[i],
key=f"darkness_{i}",
step=0.01,
help="The float value we'll subtract from pixels after each line is drawn (pixels start at a maximum value of 1.0). Lines are constantly drawn through the regions whose pixels have the highest average value. Smaller values here will produce images with a higher contrast (because we draw more lines in the dark areas before moving to the light areas).",
)

new_palette.append([r, g, b])
new_n_lines.append(lines)
new_darkness.append(darkness)

# Update colors and lines
palette = new_palette
n_lines = new_n_lines
darkness = new_darkness

# HTML output options
st.subheader("Output")

cols = st.columns(2)
with cols[0]:
html_line_width = st.number_input(
"Line width (output)",
min_value=0.05,
max_value=0.3,
value=preset_html_line_width or 0.13,
step=0.01,
help="Width of the lines in the output image. Generally this can be kept at 0.14; smaller values mean thinner lines and look better when your images are very large and have a lot of lines.",
)
with cols[1]:
html_width = st.number_input(
"Image width (output)",
min_value=300,
max_value=2000,
value=preset_html_x or preset_x or 800,
step=50,
help="Width of the output image in pixels. Increasing this will mean the final image takes longer to generate, but looks higher-resolution.",
)

# Generate button
generate_button = st.button("Generate Thread Art", type="primary")

# Process the image and generate thread art
if generate_button:
if not image_selected:
st.error("Please upload an image or select a demo.")
st.stop()

name = preset_name or "custom_thread_art"

# if isinstance(demo_image_path, Path) and demo_image_path.exists():
#     image_path = demo_image_path.name
#     w_filename = None
# elif uploaded_file is not None:
#     # Save the uploaded file to a temporary location
#     temp_img = Path(st.session_state.temp_dir.name) / f"uploaded_image.{uploaded_file.name.split('.')[-1]}"
#     with open(temp_img, "wb") as f:
#         f.write(uploaded_file.getbuffer())
#     image_path = temp_img.name
#     w_filename = None
# else:
#     st.error("Please upload an image or select a demo.")
#     st.stop()

# TODO - why is this necessary?
palette = [tuple(color) for color in palette]

# Display a status message
try:
with st.spinner("Preprocessing (takes about 10-20 seconds) ..."):
# Set up parameters
args = ThreadArtColorParams(
name=name,
x=x_size,
n_nodes=n_nodes_real,
filename=None,
w_filename=preset_w_filename,
palette=palette,
n_lines_per_color=n_lines,
shape=shape,
n_random_lines=n_random_lines,
darkness=darkness,
blur_rad=blur_rad,
group_orders=group_orders,
image=image,
step_size=preset_step_size or 1.618,  # golden ratio for the lulz
)

# Create image object
my_img = Img(args)

# Get the line dictionary (using progress bar)
line_dict = defaultdict(list)
total_lines = sum(my_img.args.n_lines_per_color)
progress_bar = st.progress(0, text="Generating lines...")
progress_count = 0
for color, i, j in my_img.create_canvas_generator():
line_dict[color].append((i, j))
progress_count += 1
progress_bar.progress(progress_count / total_lines, text="Generating lines...")

# Generate HTML
html_content = my_img.generate_thread_art_html(
line_dict,
x=html_width,
line_width=html_line_width,
steps_per_slider=150,
rand_perm=0.0025,
bg_color=(0, 0, 0),
)

# Success message
st.success("Thread art generated successfully!")

# Store the generated HTML, and delete what we don't need any more
st.session_state.generated_html = html_content
st.session_state.sf = my_img.y / my_img.x

# Versuche, echte Palette/Historgrammdaten vom my_img Objekt zu speichern (falls vorhanden).
try:
pal = getattr(my_img, "palette", None)
if pal is None:
pal = getattr(my_img.args, "palette", None)
hist = getattr(my_img, "color_histogram", None)
if hist is None:
hist = getattr(my_img.args, "color_histogram", None)

# Wenn vorhanden, in session_state speichern (überschreibt die Upload-Schätzung)
if pal is not None and hist is not None:
st.session_state.decompose_data = {"palette": pal, "color_histogram": hist}
else:
# falls nicht vorhanden, belasse vorhandene Schätzung (aus Upload) unverändert
st.session_state.decompose_data = st.session_state.get("decompose_data", None)
except Exception:
st.session_state.decompose_data = st.session_state.get("decompose_data", None)

del args
del my_img
del line_dict
gc.collect()

except Exception as e:
st.error(f"Error generating thread art: {str(e)}")
st.code(traceback.format_exc())


# Display the generated thread art if available
if st.session_state.generated_html:
st.header("Generated Thread Art")

# Display the HTML output
html_height = html_width * st.session_state.sf
st_html(st.session_state.generated_html, height=html_height + 150, scrolling=True)

# Download options
st.subheader("Download Options")

# Provide HTML download
b64_html = base64.b64encode(st.session_state.generated_html.encode()).decode()
href_html = f'<a href="data:text/html;base64,{b64_html}" download="{name}.html">Download HTML File</a>'
st.markdown(href_html, unsafe_allow_html=True)
# Vorschlag / Button für Linienverteilung (immer sichtbar, mit Fallback)
st.subheader("Vorgeschlagene Linienverteilung")

n_lines_total_input = st.number_input(
"Gesamtzahl Linien (für Vorschlag)",
min_value=100,
max_value=200000,
value=10000,
step=100,
key="decompose_total_lines_input",
)

if st.button("Vorschlag anzeigen", key="show_decompose_global"):
if st.session_state.get("decompose_data"):
data = st.session_state.decompose_data
obj = SimpleNamespace(palette=data["palette"], color_histogram=data["color_histogram"])
try:
decompose_image(obj, n_lines_total=n_lines_total_input)
except Exception as e:
st.error(f"Fehler beim Anzeigen der Verteilung: {e}")
else:
st.info("Keine Farbhistogrammdaten gefunden — ich verwende eine Schätzung basierend auf den aktuellen UI-Einstellungen.")
try:
pal = globals().get("palette") or st.session_state.get("palette")
nl = globals().get("n_lines") or st.session_state.get("n_lines")
if isinstance(pal, list) and pal and isinstance(pal[0], list):
pal = [tuple(c) for c in pal]
if pal is None or nl is None:
raise RuntimeError("Aktuelle Palette/Zeilen-Einstellungen sind nicht verfügbar. Erzeuge zuerst ein Bild oder wähle ein Demo.")

total_lines_from_ui = sum(nl) if sum(nl) > 0 else n_lines_total_input
hist = [float(x) / total_lines_from_ui for x in nl]
obj = SimpleNamespace(palette=pal, color_histogram=hist)
decompose_image(obj, n_lines_total=n_lines_total_input)
except Exception as e:
st.error(f"Keine ausreichenden Daten für eine Schätzung vorhanden: {e}")
st.write("Hinweis: Die echte Histogramm-basierte Auswertung wird nur angezeigt, wenn das erzeugende Img-Objekt ein Attribut `color_histogram` liefert und dieses beim Generieren in `st.session_state.decompose_data` gespeichert wurde.")
# # Show embed code for Squarespace
# st.subheader("Embed Code for Squarespace")
# st.text_area("Copy this code into a Code Block in Squarespace:", st.session_state.generated_html, height=200)
# st.markdown("""
# Instructions:
# 1. Copy the code above
# 2. In Squarespace, add a "Code" block to your page
# 3. Paste the code into the block
# 4. Save your changes
# """)

# netstat -ano | findstr "0.0.0.0:8501.*LISTENING"
# psrecord 49256 --plot plot.png

# # simpler / longer versions:
# netstat -ano | findstr :8501
# netstat -ano | findstr ":8501.*LISTENING" | for /f "tokens=5" %a in ('findstr /i "listening"') do @echo %a
