"""Public evaluation entrypoint; connection settings remain server controlled."""
import os
from hashlib import sha256
from pathlib import Path
import runpy

import streamlit as st

os.environ["EVALUATION_MODE"] = "true"
root = Path(__file__).resolve().parent

# Keep this at the deployed entrypoint so older UI modules also omit the
# retired introductory subtitle and footer. Style-only HTML uses Streamlit's
# event container and does not add a visible row or extra spacing.
st.html("""
<style>
.stApp:has(.welcome) .case-header .case-meta,
.stApp .workspace-foot {
    display: none !important;
}
</style>
""")

# Deployment diagnostics contain only a build label and a source-file digest.
# They never include credentials, user input or document contents.
desk_digest = sha256((root / "finance_assistant" / "review_desk.py").read_bytes()).hexdigest()
print(f"[ui-text-removal-20261107] entry=judge_app.py review_desk_sha256={desk_digest}", flush=True)

runpy.run_path(str(root / "app.py"), run_name="__main__")
