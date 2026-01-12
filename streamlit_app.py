import base64
import gc
import io
import os
import sys

print("Working directory:", os.getcwd())
print("Directory contents:", os.listdir())
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
        swatch = f"<span style='display:inline-block;width:64px;height:16px;background:rgb{(r,g,b)};border:1px solid #333;margin:0 8px;vertical-align:middle'></span>"
        text = f"<code>{color_string.ljust(18)}</code>{swatch}<code>{name_str}</code> = {n_lines}"
        st.markdown(text, unsafe_allow_html=True)

    # palette as dict (name -> rgb)
    if isinstance(pal, dict):
        keys = list(pal.keys())
        try:
            n_lines_per_color = [int(hist.get(k, 0) * n_lines_total) for k in keys]
        except Exception:
            st.warning("Unexpected format for color_histogram; expected dict mapping color-name -> frequency.")
            return

        try:
            sums = [sum(tuple(pal[k])) for k in keys]
            darkest_idx = sums.index(max(sums))
        except Exception:
            darkest_idx = 0

        n_lines_per_color[darkest_idx] += (n_lines_total - sum(n_lines_per_color))

        max_len_color_name = max(len(k) for k in keys) if keys else 0
        for idx, k in enumerate(keys):
            render_color_line(pal[k], k.ljust(max_len_color_name), n_lines_per_color[idx])

        st.code(f"`n_lines_per_color` for you to copy: {n_lines_per_color}")

    # palette as list/tuple
    elif isinstance(pal, (list, tuple)):
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

Note that the quality of output varies a lot based on small parameter changes, so we encourage you to start by looking at some of the demos and see what works well for them, and then try and upload yo[...]
"
)

# Initialize session state
if "generated_html" not in st.session_state:
    st.session_state.generated_html = None
if "output_name" not in st.session_state:
    st.session_state.output_name = None
if "temp_dir" not in st.session_state:
    st.session_state.temp_dir = tempfile.TemporaryDirectory()

# Container for storing palette/histogram for the decompose button
if "decompose_data" not in st.session_state:
    st.session_state.decompose_data = None

name = None

# parameters
# (The rest of the file remains unchanged from the earlier version; full contents include all sidebar, processing, debug and display logic)
