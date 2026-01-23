import base64
import json
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
import numpy as np
from sklearn.cluster import KMeans

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

# ===== HSV-basierte Farberkennung (aus color_extractor.py) =====
def rgb_to_hsv(img_rgb):
    """Vectorized RGB->HSV conversion. Input uint8 RGB image, returns H,S,V in [0,1]."""
    arr = img_rgb.astype('float32') / 255.0
    r = arr[..., 0]
    g = arr[..., 1]
    b = arr[..., 2]
    maxc = np.max(arr, axis=-1)
    minc = np.min(arr, axis=-1)
    v = maxc
    delta = maxc - minc
    # Fix division by zero warning
    s = np.divide(delta, maxc, out=np.zeros_like(delta), where=maxc!=0)

    h = np.zeros_like(maxc)
    mask = delta != 0
    # Where max is r
    idx = (maxc == r) & mask
    h[idx] = ( (g[idx] - b[idx]) / delta[idx] ) % 6
    # Where max is g
    idx = (maxc == g) & mask
    h[idx] = ( (b[idx] - r[idx]) / delta[idx] ) + 2
    # Where max is b
    idx = (maxc == b) & mask
    h[idx] = ( (r[idx] - g[idx]) / delta[idx] ) + 4

    h = h / 6.0  # now in [0,1]
    h[~mask] = 0.0
    hsv = np.stack([h, s, v], axis=-1)
    return hsv

def hue_in_ranges(hue_array, ranges_deg):
    """hue_array in [0,1]. ranges_deg is list of (min_deg, max_deg) - may include negative for wrap."""
    h_deg = (hue_array * 360.0) % 360.0
    mask = np.zeros(h_deg.shape, dtype=bool)
    for (mn, mx) in ranges_deg:
        mn_norm = mn % 360
        mx_norm = mx % 360
        if mn_norm <= mx_norm:
            mask |= (h_deg >= mn_norm) & (h_deg <= mx_norm)
        else:
            mask |= (h_deg >= mn_norm) | (h_deg <= mx_norm)
    return mask

def get_top_colors_kmeans(pixels_rgb, top_n=3):
    """Extract top N colors from pixels using KMeans"""
    if len(pixels_rgb) == 0:
        return []
    # Limit sample size
    max_pixels = 100000
    n_samples = min(len(pixels_rgb), max_pixels)
    if len(pixels_rgb) > n_samples:
        idx = np.random.choice(len(pixels_rgb), n_samples, replace=False)
        sample = pixels_rgb[idx]
    else:
        sample = pixels_rgb

    k = min(top_n, len(sample))
    kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
    kmeans.fit(sample)
    centers = np.clip(kmeans.cluster_centers_.astype(int), 0, 255)
    labels = kmeans.predict(pixels_rgb)
    results = []
    total = len(pixels_rgb)
    for i, center in enumerate(centers):
        cnt = int((labels == i).sum())
        percent = cnt / total
        hexcol = '#{:02x}{:02x}{:02x}'.format(int(center[0]), int(center[1]), int(center[2]))
        results.append({'hex': hexcol, 'percent': percent, 'rgb': tuple(center)})
    results.sort(key=lambda x: x['percent'], reverse=True)
    return results

def extract_colors_hsv(image_pil):
    """Extract colors from image using HSV-based categorization"""
    # Resize if too large
    arr = np.array(image_pil.convert('RGB'))
    H, W = arr.shape[:2]
    max_side = 1000
    if max(H, W) > max_side:
        scale = max_side / max(H, W)
        image_pil = image_pil.resize((int(W*scale), int(H*scale)), Image.LANCZOS)
    
    arr = np.array(image_pil.convert('RGB'))
    pixels = arr.reshape(-1, 3)
    hsv = rgb_to_hsv(arr).reshape(-1, 3)
    h = hsv[:, 0]
    s = hsv[:, 1]
    v = hsv[:, 2]

    # Thresholds
    BLACK_V_THRESHOLD = 0.15
    WHITE_V_THRESHOLD = 0.92
    WHITE_S_THRESHOLD = 0.18
    MIN_SAT = 0.12

    # Black & white
    black_mask = v <= BLACK_V_THRESHOLD
    white_mask = (v >= WHITE_V_THRESHOLD) & (s <= WHITE_S_THRESHOLD)
    black_pct = black_mask.mean()
    white_pct = white_mask.mean()

    # Colored pixels
    non_grey_mask = ~(black_mask | white_mask)

    # Hue ranges
    red_mask = hue_in_ranges(h, [(-20, 20)]) & non_grey_mask & (s >= MIN_SAT)
    green_mask = hue_in_ranges(h, [(60, 170)]) & non_grey_mask & (s >= MIN_SAT)
    blue_mask = hue_in_ranges(h, [(200, 280)]) & non_grey_mask & (s >= MIN_SAT)

    def gather(mask, top_n=5):
        pixels_sel = pixels[mask]
        if len(pixels_sel) == 0:
            return []
        # Convert cluster share (relative to this subset) into a global share of all pixels
        subset_ratio = len(pixels_sel) / len(pixels)
        results = get_top_colors_kmeans(pixels_sel, top_n=top_n)
        for r in results:
            r['percent'] *= subset_ratio
        return results

    results = {
        'black': ({'hex': '#000000', 'percent': black_pct, 'rgb': (0, 0, 0)} if black_pct > 0.01 else None),
        'white': ({'hex': '#ffffff', 'percent': white_pct, 'rgb': (255, 255, 255)} if white_pct > 0.01 else None),
        'red': gather(red_mask),
        'green': gather(green_mask),
        'blue': gather(blue_mask),
    }
    return results

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
        
        # Speichere n_lines_per_color für "Vorschlag übernehmen"
        return n_lines_per_color

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
        
        # Speichere n_lines_per_color für "Vorschlag übernehmen"
        return n_lines_per_color

    else:
        st.warning("Unrecognized palette format. Expected dict or list of RGB tuples.")
        return None
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
    # Initialize session_state if not set (but don't use value= parameter to avoid warning)
    if "num_colors_input" not in st.session_state:
        default_num_colors = (len(preset_palette) if (preset_palette and isinstance(preset_palette, (list, tuple))) else 3)
        st.session_state["num_colors_input"] = default_num_colors
    
    num_colors = st.number_input(
        "Number of Colors",
        min_value=1,
        max_value=10,
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
        
        # === Neue HSV-basierte Farberkennung mit Checkbox-Selection ===
        # Only recompute if image changed (hash the bytes to detect changes)
        import hashlib
        image_hash = hashlib.md5(image_bytes).hexdigest()
        image_changed = st.session_state.get("last_image_hash") != image_hash
        
        if image_changed:
            try:
                hsv_colors = extract_colors_hsv(image)
                
                # Flatten all colors into one list with category info
                all_found_colors = []
                
                # Add black & white if present
                if hsv_colors['black']:
                    all_found_colors.append(('Schwarz', hsv_colors['black']))
                if hsv_colors['white']:
                    all_found_colors.append(('Weiß', hsv_colors['white']))
                
                # Add colored categories
                for color_info in hsv_colors['red']:
                    all_found_colors.append(('Rot', color_info))
                for color_info in hsv_colors['green']:
                    all_found_colors.append(('Grün', color_info))
                for color_info in hsv_colors['blue']:
                    all_found_colors.append(('Blau', color_info))
                
                # Store in session state
                st.session_state.all_found_colors = all_found_colors
                st.session_state.last_image_hash = image_hash
                
                # Initialize checkbox states (alle Farben sind initial ausgewählt)
                st.session_state.color_checkbox_states = [True] * len(all_found_colors)
                    
            except Exception as e:
                st.session_state.all_found_colors = []
                st.session_state.color_checkbox_states = []
        
        # Falls noch keine Farben geladen, verwende decompose_data fallback
        if not st.session_state.get("all_found_colors"):
            # For demo images or when color detection is not available
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

                        # Validate histogram format - ensure it's a list of numbers
                        try:
                            # If hl contains dicts or tuples, extract 'percent' field or first element
                            if hl and isinstance(hl[0], dict):
                                hl = [item.get('percent', 0) for item in hl]
                            elif hl and isinstance(hl[0], (list, tuple)):
                                hl = [float(item[0]) if item else 0 for item in hl]
                            # Ensure all elements are numbers
                            hl = [float(h) if not isinstance(h, (list, tuple, dict)) else 0 for h in hl]
                        except Exception:
                            # Fallback: distribute evenly if histogram is invalid
                            hl = [1.0 / len(suggested_palette)] * len(suggested_palette)

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

        # =======================================================================================================
            # Prefill widgets from suggested palette/lines if they are not already set in session_state
            # WICHTIG: Nur ausführen wenn NICHT durch "Vorschlag generieren" Button befüllt wurde
            # (User soll explizit "Vorschlag übernehmen" klicken)
        try:
            # Prefill nur wenn nicht durch "Vorschlag generieren" ausgelöst
            skip_prefill = st.session_state.get("skip_prefill_after_suggestion", False)
            is_from_button = st.session_state.get("decompose_data") and not preset_palette
            
            if 'preset_palette' in locals() and preset_palette and not is_from_button and not skip_prefill:
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
        # Ensure n_nodes is a multiple of 4, but don't add an extra 4 when already divisible
        n_nodes_real = n_nodes if (n_nodes % 4 == 0) else n_nodes + (4 - n_nodes % 4)
        st.session_state["n_nodes_real"] = n_nodes_real  # Store for later use in PDF export
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

        # Initialize group_orders in session_state if not set
        if "group_orders_input" not in st.session_state:
            st.session_state["group_orders_input"] = preset_group_orders or "2,3,4,1,3,2,1"
        
        # Apply optimized group_orders if available (from Auto-Optimize button)
        if st.session_state.get("apply_optimized_orders", False):
            st.session_state["group_orders_input"] = st.session_state.get("optimized_group_orders", st.session_state["group_orders_input"])
            st.session_state["apply_optimized_orders"] = False
        
        group_orders = st.text_input(
            "Group Orders",
            key="group_orders_input",
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

    # === KRITISCH: Prüfe, ob neue Werte vom "Vorschlag übernehmen" Button in session_state gespeichert sind ===
    # Zähle wie viele color_pick_i Keys in session_state existieren (mit aktuellem Suffix)
    widget_version = st.session_state.get("widget_version", 0)
    widget_suffix = f"_v{widget_version}"
    
    num_saved_colors = 0
    for i in range(20):  # Check up to 20 colors
        # Prüfe Keys BOTH mit und ohne Suffix
        key_with_suffix = f"color_pick_{i}{widget_suffix}"
        key_without_suffix = f"color_pick_{i}"
        if key_with_suffix in st.session_state or key_without_suffix in st.session_state:
            num_saved_colors = i + 1
        else:
            break
    
    # WICHTIG: Wenn Vorschlag vorhanden, ignoriere num_colors Widget komplett!
    if num_saved_colors > 0:
        # Lade alle gespeicherten Farben (mit Suffix oder ohne)
        palette = []
        n_lines = []
        darkness_values = []
        for i in range(num_saved_colors):
            # Prüfe zuerst mit Suffix, dann ohne
            hex_col = st.session_state.get(f"color_pick_{i}{widget_suffix}")
            if not hex_col:
                hex_col = st.session_state.get(f"color_pick_{i}")
                
            if hex_col:
                r, g, b = int(hex_col[1:3], 16), int(hex_col[3:5], 16), int(hex_col[5:7], 16)
                palette.append([r, g, b])
                
                # Lese Lines (mit Suffix oder ohne)
                lines_val = st.session_state.get(f"lines_{i}{widget_suffix}")
                if not lines_val:
                    lines_val = st.session_state.get(f"lines_{i}", 1000)
                n_lines.append(lines_val)
                
                # Lese Darkness (mit Suffix oder ohne)
                dark_val = st.session_state.get(f"darkness_{i}{widget_suffix}")
                if not dark_val:
                    dark_val = st.session_state.get(f"darkness_{i}", 0.17)
                darkness_values.append(dark_val)
        
        # Verwende die Anzahl gespeicherter Farben für Rendering (NICHT das Widget!)
        num_colors_to_render = num_saved_colors
    else:
        # Kein Vorschlag vorhanden - verwende num_colors Widget
        num_colors_to_render = num_colors
        
        # Adjust palette based on num_colors (from widget)
        num_colors_current = len(palette)
        if num_colors_to_render != num_colors_current:
            if num_colors_to_render > num_colors_current:
                # Add more colors
                for i in range(num_colors_current, num_colors_to_render):
                    palette.append([128, 128, 128])  # Default to gray
                    n_lines.append(1000)  # Default number of lines
                    darkness_values.append(0.17)
            else:
                # Remove colors
                palette = palette[:num_colors_to_render]
                n_lines = n_lines[:num_colors_to_render]
                darkness_values = darkness_values[:num_colors_to_render]

    # Color editors
    new_palette = []
    new_n_lines = []
    new_darkness = []
    
    # KRITISCH: Benutze den aktuellen Widget-Version Counter für Keys
    widget_version = st.session_state.get("widget_version", 0)
    widget_suffix = f"_v{widget_version}"
    
    # Initialisiere die session_state Keys VOR der Widget-Erstellung (um Warnings zu vermeiden)
    for i in range(num_colors_to_render):
        # Color picker
        if f"color_pick_{i}{widget_suffix}" not in st.session_state:
            hex_default = f"#{palette[i][0]:02x}{palette[i][1]:02x}{palette[i][2]:02x}"
            st.session_state[f"color_pick_{i}{widget_suffix}"] = hex_default
        
        # Lines
        if f"lines_{i}{widget_suffix}" not in st.session_state:
            lines_default = max(100, int(n_lines[i]))
            st.session_state[f"lines_{i}{widget_suffix}"] = lines_default
        
        # Darkness
        if f"darkness_{i}{widget_suffix}" not in st.session_state:
            st.session_state[f"darkness_{i}{widget_suffix}"] = darkness_values[i]

    for i in range(num_colors_to_render):
        # st.markdown(f"##### Color {i + 1}")
        col1, col2, col3 = st.columns([1, 2, 2])

        with col1:
            # Widget liest automatisch aus session_state wenn key verwendet wird
            color_hex = st.color_picker(
                "Color",
                key=f"color_pick_{i}{widget_suffix}",
            )
            r, g, b = int(color_hex[1:3], 16), int(color_hex[3:5], 16), int(color_hex[5:7], 16)

        with col2:
            # Widget liest automatisch aus session_state wenn key verwendet wird
            lines = st.number_input(
                "Lines",
                min_value=100,
                max_value=15000,
                key=f"lines_{i}{widget_suffix}",
                help="The total number of lines we'll draw for this color. 3 guidelines to consider here: (1) the line numbers should be roughly in proportion with their density in your image, (2) you should make sure to include a lot of black lines for most images because that's an important component of making a good piece of thread art, and (3) you should aim for about 6000 - 20000 total lues when summed over all colors (the exact number depends on some of your other parameters, and how detailed you want the piece to be).",
            )

        with col3:
            # Widget liest automatisch aus session_state wenn key verwendet wird
            darkness = st.number_input(
                "Darkness",
                min_value=0.05,
                max_value=0.3,
                key=f"darkness_{i}{widget_suffix}",
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
        # Store group_orders in session_state for PDF export
        st.session_state["group_orders"] = group_orders
        
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

            # Store pin coordinates/meta for later visualization (avoid recomputing)
            try:
                st.session_state.pins_shape = str(my_img.args.shape)
                st.session_state.pins_n_nodes = int(my_img.args.n_nodes)
                st.session_state.pins_base_x = int(my_img.args.x)
                st.session_state.pins_base_y = int(my_img.args.y)
                # Convert torch tensors to plain floats for session_state
                st.session_state.pins_d_coords = {
                    int(k): [float(v[0].item()), float(v[1].item())] for k, v in my_img.args.d_coords.items()
                }
            except Exception:
                # Fail silently; don't break generation UI
                pass

        # Get the line dictionary (using progress bar) and capture full draw sequence
        line_dict = defaultdict(list)
        line_sequence = []
        total_lines = sum(my_img.args.n_lines_per_color)
        progress_bar = st.progress(0, text="Generating lines...")
        progress_count = 0
        for color, i, j in my_img.create_canvas_generator():
            # Per-color aggregation
            line_dict[color].append((i, j))
            # Sequence with color + pins
            try:
                color_tuple = tuple(int(x) for x in color)
            except Exception:
                color_tuple = (int(color[0]), int(color[1]), int(color[2]))
            hex_col = f"#{color_tuple[0]:02x}{color_tuple[1]:02x}{color_tuple[2]:02x}"
            try:
                color_index_0 = my_img.args.palette.index(color_tuple)
            except ValueError:
                # Fallback: match by nearest
                color_index_0 = 0
            line_sequence.append({
                "step": progress_count + 1,
                "color_index": color_index_0 + 1,  # 1-based for human readability
                "color_hex": hex_col,
                "rgb": list(color_tuple),
                "from_pin": int(i),
                "to_pin": int(j),
            })
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
        # Store sequence for export
        st.session_state.line_sequence = line_sequence

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

    # Pin visualization
    st.subheader("📍 Pins (Nägel/Hooks)")
    if st.button("Show pins", key="show_pins"):
        try:
            pins_d_coords = st.session_state.get("pins_d_coords")
            pins_shape = st.session_state.get("pins_shape")
            pins_n_nodes = int(st.session_state.get("pins_n_nodes") or 0)
            pins_base_x = int(st.session_state.get("pins_base_x") or 0)
            pins_base_y = int(st.session_state.get("pins_base_y") or 0)

            if not pins_d_coords or pins_n_nodes <= 0 or pins_base_x <= 0 or pins_base_y <= 0:
                st.warning("No pin data available yet. Generate the thread art first.")
            else:
                out_w = int(html_width)
                out_h = int(out_w * (pins_base_y / pins_base_x))
                sx = out_w / pins_base_x
                sy = out_h / pins_base_y

                pin_r = max(2.0, out_w * 0.004)
                stroke_w = max(0.8, out_w * 0.0012)
                font_size = max(8, int(out_w * 0.015))
                text_dy = font_size * 0.35

                svg_lines = [
                    f'<svg xmlns="http://www.w3.org/2000/svg" width="{out_w}" height="{out_h}" viewBox="0 0 {out_w} {out_h}">',
                    f'<rect width="{out_w}" height="{out_h}" fill="rgb(0,0,0)"/>'
                ]

                # Outline to match chosen shape; for square images ellipse becomes a circle naturally.
                if str(pins_shape) == "Ellipse":
                    cx = out_w / 2
                    cy = out_h / 2
                    rx = (out_w - 2) / 2
                    ry = (out_h - 2) / 2
                    svg_lines.append(
                        f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" '
                        f'stroke="rgb(90,90,90)" stroke-width="{stroke_w:.2f}" fill="none"/>'
                    )
                else:
                    svg_lines.append(
                        f'<rect x="1" y="1" width="{out_w-2}" height="{out_h-2}" '
                        f'stroke="rgb(90,90,90)" stroke-width="{stroke_w:.2f}" fill="none"/>'
                    )

                # Pins: label pin 1 and then every 5th (1, 5, 10, 15, ...)
                for idx in range(pins_n_nodes):
                    coord = pins_d_coords.get(idx)
                    if coord is None:
                        continue
                    y0, x0 = float(coord[0]), float(coord[1])
                    x_px = x0 * sx
                    y_px = y0 * sy

                    svg_lines.append(
                        f'<circle cx="{x_px:.1f}" cy="{y_px:.1f}" r="{pin_r:.1f}" '
                        f'fill="rgb(255,0,0)" stroke="rgb(200,0,0)" stroke-width="{stroke_w:.2f}"/>'
                    )

                    pin_no = idx + 1
                    if pin_no == 1 or (pin_no % 5) == 0:
                        svg_lines.append(
                            f'<text x="{x_px:.1f}" y="{(y_px + text_dy):.1f}" text-anchor="middle" '
                            f'fill="rgb(255,255,255)" font-size="{font_size}" font-weight="700">{pin_no}</text>'
                        )

                svg_lines.append("</svg>")
                pins_svg = "\n".join(svg_lines)

                st_html(pins_svg, height=out_h + 20, scrolling=True)
                st.download_button(
                    label="Download pins SVG",
                    data=pins_svg.encode("utf-8"),
                    file_name=f"{name or 'thread_art'}_pins.svg",
                    mime="image/svg+xml",
                )
        except Exception as e:
            st.error(f"Error generating pins SVG: {str(e)}")
            st.code(traceback.format_exc())

    # Download options
    st.subheader("📥 Download Options")

    # Provide HTML download
    b64_html = base64.b64encode(st.session_state.generated_html.encode()).decode()
    href_html = f'<a href="data:text/html;base64,{b64_html}" download="{name}.html">Download HTML File</a>'
    st.markdown(href_html, unsafe_allow_html=True)

    # Export line sequence (CSV / JSON / PDF)
    if st.session_state.get("line_sequence"):
        seq = st.session_state.line_sequence
        
        col1, col2, col3 = st.columns(3)
        
        # CSV Export
        with col1:
            import io as _io
            csv_buf = _io.StringIO()
            csv_buf.write("step,color_index,color_hex,r,g,b,from_pin,to_pin\n")
            for row in seq:
                r, g, b = row["rgb"]
                csv_buf.write(f"{row['step']},{row['color_index']},{row['color_hex']},{r},{g},{b},{row['from_pin']},{row['to_pin']}\n")
            csv_bytes = csv_buf.getvalue().encode("utf-8")
            st.download_button(
                label="📊 CSV",
                data=csv_bytes,
                file_name=f"{name or 'thread_art'}_sequence.csv",
                mime="text/csv",
            )

        # JSON Export
        with col2:
            json_bytes = json.dumps(seq, ensure_ascii=False, indent=2).encode("utf-8")
            st.download_button(
                label="📄 JSON",
                data=json_bytes,
                file_name=f"{name or 'thread_art'}_sequence.json",
                mime="application/json",
            )
        
        # PDF Export (Picture Hangers)
        with col3:
            # Checkbox für Haken vs Nägel
            use_hangers = st.checkbox(
                "🔧 Haken verwenden (statt Nägel)", 
                value=True,
                help="Aktiviert: 1 Haken = 2 Nodes (L/R). Deaktiviert: 1 Nagel = 1 Node"
            )
            
            if st.button("🖨️ Generate PDF Instructions", key="gen_pdf"):
                try:
                    from pdf_export import export_to_pdf
                    
                    # Get color information
                    detected_colors = st.session_state.get("all_found_colors", [])
                    group_orders = st.session_state.get("group_orders", "")
                    n_nodes = st.session_state.get("n_nodes_real", 320)
                    
                    # Extract unique colors from line_sequence in order of appearance
                    # This ensures color_names matches the order intended in group_orders
                    hex_to_category_info = {}
                    for category, color_info in detected_colors:
                        hex_val = color_info.get('hex', '').lower()
                        if hex_val:
                            hex_to_category_info[hex_val] = (category, color_info)
                    
                    # Build color_names and color_info_list based on appearance order in seq
                    seen_hexes = []
                    for row in seq:
                        hex_val = str(row.get("color_hex", "")).lower()
                        if hex_val and hex_val not in seen_hexes:
                            seen_hexes.append(hex_val)
                    
                    # Helper function to categorize unknown hex colors based on HSV
                    def categorize_hex_by_hsv(hex_str):
                        """Categorize a hex color by its HSV hue using the existing rgb_to_hsv function"""
                        try:
                            # Parse hex to RGB
                            hex_clean = hex_str.lstrip('#').lower()
                            if len(hex_clean) != 6:
                                return "Color"
                            r = int(hex_clean[0:2], 16)
                            g = int(hex_clean[2:4], 16)
                            b = int(hex_clean[4:6], 16)
                            
                            # Use existing rgb_to_hsv function
                            rgb_arr = np.array([[[r, g, b]]], dtype=np.uint8)
                            hsv_arr = rgb_to_hsv(rgb_arr)
                            h = hsv_arr[0, 0, 0] * 360  # Convert to 0-360 range
                            s = hsv_arr[0, 0, 1]
                            v = hsv_arr[0, 0, 2]
                            
                            # Categorize by hue (allowing wider red range for brown/dark reds)
                            # Red: -30 to 30 degrees (includes browns around 10-20)
                            if h < 30 or h >= 330:
                                return "Rot"
                            # Green: 60-170 degrees
                            elif 60 <= h < 170:
                                return "Grün"
                            # Blue: 200-280 degrees
                            elif 200 <= h < 280:
                                return "Blau"
                            else:
                                return "Color"
                        except Exception as e:
                            print(f"Error categorizing {hex_str}: {e}")
                            return "Color"
                    
                    # Create color_names and color_info_list in the order they appear in seq
                    color_names = []
                    color_info_list = []
                    for i, hex_val in enumerate(seen_hexes):
                        if hex_val in hex_to_category_info:
                            category, color_info = hex_to_category_info[hex_val]
                            color_names.append(category)
                            color_info_list.append(color_info)
                        else:
                            # Fallback: Categorize by HSV hue
                            category = categorize_hex_by_hsv(hex_val)
                            color_names.append(category)
                            color_info_list.append({"hex": hex_val, "name": category})
                    
                    # IMPORTANT: Re-index seq with new color_index values!
                    # Build mapping from old hex → new 1-based index
                    hex_to_new_index = {}
                    for i, hex_val in enumerate(seen_hexes):
                        hex_to_new_index[hex_val] = i + 1  # 1-based index for PDF
                    
                    # Update seq with new color_index values
                    for row in seq:
                        old_hex = str(row.get("color_hex", "")).lower()
                        if old_hex in hex_to_new_index:
                            row["color_index"] = hex_to_new_index[old_hex]
                    
                    # Debug info display
                    with st.expander("🔍 Debug Info", expanded=False):
                        st.write(f"**line_sequence**: {len(seq)} entries")
                        if seq and len(seq) > 0:
                            st.write(f"**First entry type**: {type(seq[0])}")
                            st.write(f"**First entry**: {seq[0]}")
                            # Quick glance at the first 20 colors in the sequence
                            first_colors = [row.get("color_hex", "") for row in seq[:20]]
                            st.write(f"**First 20 color_hex**: {first_colors}")
                            # Order of colors by first appearance (hex-based)
                            color_order = []
                            for row in seq:
                                hx = str(row.get("color_hex", "")).lower()
                                if hx and hx not in color_order:
                                    color_order.append(hx)
                                if len(color_order) > 20:
                                    break
                            st.write(f"**Color order (first appearance)**: {color_order}")
                        st.write(f"**hex_to_new_index mapping**: {hex_to_new_index}")
                        st.write(f"**color_names**: {color_names}")
                        st.write(f"**group_orders**: `{repr(group_orders)}`")
                        st.write(f"**n_nodes**: {n_nodes}")
                    
                    # Generate PDF
                    output_path = f"outputs_drawing/{name or 'thread_art'}_instructions"
                    pdf_path = export_to_pdf(
                        line_sequence=seq,
                        color_names=color_names,
                        color_info_list=color_info_list,
                        group_orders=group_orders,
                        output_path=output_path,
                        n_nodes=n_nodes,
                        num_cols=3,
                        num_rows=18,
                        include_stats=True,
                        version="n+1",
                        use_hangers=use_hangers
                    )
                    
                    if pdf_path and os.path.exists(pdf_path):
                        with open(pdf_path, "rb") as f:
                            pdf_data = f.read()
                        
                        st.download_button(
                            label="💾 Download PDF",
                            data=pdf_data,
                            file_name=os.path.basename(pdf_path),
                            mime="application/pdf",
                        )
                        st.success(f"✅ PDF generated: {os.path.basename(pdf_path)}")
                    else:
                        st.error("❌ PDF generation failed")
                
                except ImportError as e:
                    st.error(f"❌ reportlab and PyPDF2 required: `pip install reportlab PyPDF2`")
                    st.exception(e)
                except Exception as e:
                    st.error(f"❌ Error generating PDF: {str(e)}")
                    st.exception(e)  # Shows full traceback
# === Gefundene Farben - Ausklappbarer Bereich (nur bei Custom Upload) ===
if st.session_state.get("all_found_colors"):
    # Initialisiere expanded state falls nicht vorhanden
    if "color_palette_expanded" not in st.session_state:
        st.session_state.color_palette_expanded = True
    
    # Zähle ausgewählte Farben
    num_selected = sum(1 for selected in st.session_state.get("color_checkbox_states", []) if selected)
    if num_selected > 0:
        expander_title = f"🎨 Gefundene Farben ({num_selected} gewählt)"
    else:
        expander_title = "🎨 Gefundene Farben - Wähle aus, welche du möchtest:"
    
    with st.expander(expander_title, expanded=st.session_state.color_palette_expanded):
        cols_per_row = 5
        for row_idx in range(0, len(st.session_state.all_found_colors), cols_per_row):
            cols = st.columns(cols_per_row)
            for col_idx, col in enumerate(cols):
                color_idx = row_idx + col_idx
                if color_idx >= len(st.session_state.all_found_colors):
                    break
                
                category, color_info = st.session_state.all_found_colors[color_idx]
                hex_color = color_info['hex']
                percent = color_info['percent']
                
                with col:
                    # Checkbox
                    selected = st.checkbox(
                        f"{category}",
                        value=st.session_state.color_checkbox_states[color_idx],
                        key=f"color_select_{color_idx}",
                        help=f"{hex_color}"
                    )
                    st.session_state.color_checkbox_states[color_idx] = selected
                    
                    # Color swatch
                    st.markdown(
                        f'<div style="background-color: {hex_color}; height: 50px; border-radius: 5px; border: 2px solid #ccc;"></div>',
                        unsafe_allow_html=True
                    )
                    st.caption(f"{percent:.1%}")
        
        # Button zum generieren
        if st.button("✨ Vorschlag generieren"):
            # === Intelligente Prozentverteilung: Nicht-gewählte Farben auf nächste gewählte verteilen ===
            
            # Gruppiere nach Kategorie
            category_groups = {}  # {category: [(color_idx, color_info, selected), ...]}
            for color_idx, (category, color_info) in enumerate(st.session_state.all_found_colors):
                if category not in category_groups:
                    category_groups[category] = []
                is_selected = st.session_state.color_checkbox_states[color_idx]
                category_groups[category].append((color_idx, color_info, is_selected))
            
            # Verteile nicht-gewählte Prozente auf nächste gewählte innerhalb jeder Kategorie
            adjusted_percents = {}  # {color_idx: adjusted_percent}
            
            for category, items in category_groups.items():
                # Sortiere nach Prozent (absteigend)
                items_sorted = sorted(items, key=lambda x: x[1]['percent'], reverse=True)
                
                selected_items = [(idx, info) for idx, info, sel in items_sorted if sel]
                
                if not selected_items:
                    continue
                
                # Für jede gewählte Farbe: Starte mit ihrem Original-Prozent
                for idx, info in selected_items:
                    adjusted_percents[idx] = info['percent']
                
                # Für jede nicht-gewählte Farbe: Finde gewählte mit kleinstem Abstand
                for idx, info, sel in items_sorted:
                    if sel:
                        continue  # Überspringe gewählte
                    
                    # Finde gewählte Farbe mit kleinstem Abstand (in derselben Kategorie)
                    target_idx = None
                    min_distance = float('inf')
                    
                    for sel_idx, sel_info in selected_items:
                        distance = abs(sel_info['percent'] - info['percent'])
                        if distance < min_distance:
                            min_distance = distance
                            target_idx = sel_idx
                    
                    # Addiere nicht-gewählten Prozent auf nächste gewählte
                    if target_idx is not None:
                        adjusted_percents[target_idx] += info['percent']
            
            # Erstelle finale Listen
            selected_colors = []
            selected_hists = []
            
            for color_idx in adjusted_percents:
                category, color_info = st.session_state.all_found_colors[color_idx]
                selected_colors.append(color_info['rgb'])
                selected_hists.append(adjusted_percents[color_idx])
            
            if selected_colors:
                # KEINE globale Normalisierung! Das würde Schwarz/Weiß verfälschen.
                # Die Prozente bleiben wie sie sind (Summe < 100% ist OK, da wir Farben abgewählt haben)
                
                # === Berechne Group Order Vorschlag ===
                # Berechne Luminanz für jede Farbe (0.299*R + 0.587*G + 0.114*B)
                luminances = []
                for color in selected_colors:
                    lum = 0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]
                    luminances.append(lum)
                
                # Sortiere Farben nach Luminanz (hell -> dunkel)
                sorted_indices = sorted(range(len(selected_colors)), key=lambda i: luminances[i], reverse=True)
                
                # Erstelle Group Order: 1-basiert!
                num_colors = len(selected_colors)
                base_sequence = [idx + 1 for idx in sorted_indices]  # +1 weil 1-basiert
                
                # Anzahl der Basis-Loops basierend auf Farbanzahl
                if num_colors <= 2:
                    num_loops = 4
                elif num_colors <= 4:
                    num_loops = 4
                elif num_colors <= 6:
                    num_loops = 3
                else:
                    num_loops = 2
                
                # Erstelle Sequenz mit mehreren Durchläufen
                group_order_list = []
                for loop in range(num_loops):
                    group_order_list.extend(base_sequence)
                
                # Extra: Dunkelste Farbe(n) nochmal am Ende hinzufügen
                num_darkest = min(2, num_colors)
                darkest_indices = sorted(range(len(selected_colors)), key=lambda i: luminances[i])[:num_darkest]
                for idx in darkest_indices:
                    group_order_list.append(idx + 1)
                    group_order_list.append(idx + 1)
                
                suggested_group_order = ",".join(map(str, group_order_list))
                
                st.session_state.decompose_data = {
                    "palette": selected_colors,
                    "color_histogram": selected_hists
                }
                # Speichere Group Order Vorschlag in separatem Key (nicht das Widget selbst)
                st.session_state["suggested_group_order"] = suggested_group_order
                # Flag setzen: nach Vorschlag generieren kein automatisches Prefill
                st.session_state["skip_prefill_after_suggestion"] = True
                
                # Klappe Farben-Palette ein
                st.session_state.color_palette_expanded = False
                st.rerun()
            else:
                st.warning("⚠️ Wähle mindestens eine Farbe!")

# Callback-Funktion für "Vorschlag übernehmen" Button
def apply_suggestion_callback():
    """Diese Funktion wird aufgerufen wenn der Button geklickt wird."""
    if not st.session_state.get("decompose_data"):
        return
    
    data = st.session_state.decompose_data
    palette = data["palette"]
    
    # Verwende die vorberechneten Linienzahlen aus decompose_image
    if "n_lines_per_color" in data:
        suggested_lines = data["n_lines_per_color"]
    else:
        # Fallback: Verwende einfache Prozentverteilung
        histogram = data.get("color_histogram", [])
        n_lines_total = st.session_state.get("decompose_total_lines_input", 10000)
        
        # Normalize histogram
        try:
            if histogram and isinstance(histogram[0], dict):
                histogram = [item.get('percent', 0) for item in histogram]
            elif histogram and isinstance(histogram[0], (list, tuple)):
                histogram = [float(item[0]) if item else 0 for item in histogram]
            histogram = [float(h) if not isinstance(h, (list, tuple, dict)) else 0 for h in histogram]
        except Exception:
            histogram = [1.0 / len(palette)] * len(palette)
        
        suggested_lines = [int(h * n_lines_total) for h in histogram]
        # Adjust remainder to darkest color
        remainder = n_lines_total - sum(suggested_lines)
        if remainder != 0:
            try:
                luminances = [0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2] for c in palette]
                darkest_idx = min(range(len(luminances)), key=lambda i: luminances[i])
            except Exception:
                darkest_idx = 0
            suggested_lines[darkest_idx] += remainder
    
    # === Berechne intelligente Group Order basierend auf Farbhistogramm ===
    num_colors = len(palette)
    
    # Verwende Luminanz (Helligkeit) um eine intelligente Reihenfolge zu bauen
    luminances = []
    for color in palette:
        lum = 0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]
        luminances.append(lum)
    
    # Sortiere Farben nach Helligkeit
    color_indices_by_brightness = sorted(range(num_colors), key=lambda i: luminances[i], reverse=True)  # Hell zu Dunkel
    
    # Teile in Hell und Dunkel
    luminance_threshold = sum(luminances) / len(luminances)  # Durchschnitt als Schwelle
    bright_colors = [i for i in color_indices_by_brightness if luminances[i] >= luminance_threshold]
    dark_colors = [i for i in color_indices_by_brightness if luminances[i] < luminance_threshold]
    
    # Baue Sequenz: Alterniere Hell-Dunkel um Übersteurung zu vermeiden
    suggested_sequence = []
    
    if num_colors == 1:
        suggested_sequence = [1]
    elif num_colors == 2:
        # Hell, Dunkel, Hell, Dunkel (alternierend)
        bright_idx = color_indices_by_brightness[0] + 1
        dark_idx = color_indices_by_brightness[1] + 1
        suggested_sequence = [bright_idx, dark_idx, bright_idx, dark_idx]
    elif num_colors == 3:
        # Bright, Dark, Bright, Dark, Mid, Dark (alternierend hell-dunkel)
        bright_idx = color_indices_by_brightness[0] + 1
        mid_idx = color_indices_by_brightness[1] + 1
        dark_idx = color_indices_by_brightness[2] + 1
        suggested_sequence = [bright_idx, dark_idx, mid_idx, dark_idx, bright_idx, dark_idx]
    elif num_colors == 4:
        # Strategie: Hellste, dann mittlere (dunkel zu hell), dann hellste wieder, dann dunkelste, dann mittlere wieder, dann dunkelste
        # Beispiel: [1=Schwarz, 2=#311007, 3=#853921, 4=#AFB52A(hell)]
        # Sortiert nach Helligkeit: [4, 3, 2, 1]
        # Sequenz: 4, 2, 3, 4, 1, 2, 3, 1
        indices = [color_indices_by_brightness[i] + 1 for i in range(4)]
        brightest = indices[0]
        darkest = indices[3]
        mid1 = indices[2]  # dunklere mittlere
        mid2 = indices[1]  # hellere mittlere
        suggested_sequence = [brightest, mid1, mid2, brightest, darkest, mid1, mid2, darkest]
    else:
        # Mehr als 4 Farben: Alterniere zwischen hell und dunkel
        suggested_sequence = []
        bi, di = 0, 0
        while len(suggested_sequence) < min(20, num_colors * 3) and (bi < len(bright_colors) or di < len(dark_colors)):
            if bi < len(bright_colors):
                suggested_sequence.append(bright_colors[bi] + 1)
                bi += 1
            if di < len(dark_colors) and len(suggested_sequence) < min(20, num_colors * 3):
                suggested_sequence.append(dark_colors[di] + 1)
                di += 1
    
    suggested_group_order = ",".join(map(str, suggested_sequence))
    
    # Speichere in session_state
    st.session_state["suggested_group_order"] = suggested_group_order
    
    # Inkrementiere Widget-Version Counter
    current_version = st.session_state.get("widget_version", 0)
    new_version = current_version + 1
    st.session_state["widget_version"] = new_version
    widget_suffix = f"_v{new_version}"
    
    # Setze die neuen Werte mit dem NEUEN Widget-Suffix
    for i in range(len(palette)):
        color = palette[i]
        # Color picker
        hex_col = f"#{int(color[0]):02x}{int(color[1]):02x}{int(color[2]):02x}"
        st.session_state[f"color_pick_{i}{widget_suffix}"] = hex_col
        
        # Lines
        st.session_state[f"lines_{i}{widget_suffix}"] = suggested_lines[i]
        
        # Darkness (default)
        st.session_state[f"darkness_{i}{widget_suffix}"] = 0.17
    
    # Update num_colors widget to show correct number
    st.session_state["num_colors_input"] = len(palette)
    
    # Update group_orders widget mit vorgeschlagener Sequenz
    st.session_state["group_orders_input"] = st.session_state.get("suggested_group_order", preset_group_orders or "4")
    # Prefill-Flag zurücksetzen, da jetzt bewusst übernommen wurde
    st.session_state["skip_prefill_after_suggestion"] = False
    
    # Lösche ALTE Widget-Keys (aber nicht die neuen mit new_version!)
    for version in range(new_version):  # Nur alte Versionen, nicht die neue!
        for i in range(20):
            for key_prefix in ["color_pick_", "lines_", "darkness_"]:
                # Lösche Keys ohne Suffix (nur wenn version == 0)
                if version == 0:
                    key = f"{key_prefix}{i}"
                    if key in st.session_state:
                        del st.session_state[key]
                # Lösche Keys mit alten Versionen
                old_key = f"{key_prefix}{i}_v{version}"
                if old_key in st.session_state:
                    del st.session_state[old_key]

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
    # Setze Flag dass Vorschlag angezeigt wurde
    st.session_state["suggestion_displayed"] = True
    
    if st.session_state.get("decompose_data"):
        data = st.session_state.decompose_data
        obj = SimpleNamespace(palette=data["palette"], color_histogram=data["color_histogram"])
        try:
            n_lines_per_color = decompose_image(obj, n_lines_total=n_lines_total_input)
            # Speichere die berechneten Linienzahlen
            if n_lines_per_color:
                st.session_state.decompose_data["n_lines_per_color"] = n_lines_per_color
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

# Button zum Übernehmen - nur anzeigen wenn Vorschlag angezeigt wurde
if st.session_state.get("suggestion_displayed", False):
    st.button(
        "📝 Vorschlag übernehmen",
        key="apply_suggestion_to_ui",
        on_click=apply_suggestion_callback
    )
    
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
