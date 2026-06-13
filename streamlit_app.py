"""
streamlit_app.py

Convenience entry point for Streamlit Community Cloud / sharing.

This allows one-click deploy from GitHub without changing default settings.
It simply bootstraps the full daily_x_posts dashboard.
"""

import sys
from pathlib import Path

# Make sure we can import local modules when deployed
sys.path.insert(0, str(Path(__file__).parent))

from main import launch_dashboard  # re-uses the same launch function
# Note: main.py already contains the full bootstrap + launch_dashboard call

# When Streamlit Cloud runs this file it will execute the top level of main
# which detects the streamlit context and launches the UI.
# We import to trigger any side effects if needed, but main.py is designed
# to work directly.

if __name__ == "__main__":
    # Fallback for direct python -m streamlit run streamlit_app.py
    from main import cli_main
    cli_main()
