# Memory System Development Guide
Created: 2025-11-02 20:06:54
Author: electricwolfemarshmallowhypertext

## Development Setup

### Prerequisites

```bash
# Required system packages
sudo apt-get update && sudo apt-get install -y \
    python3.11 \
    python3.11-dev \
    python3.11-venv \
    build-essential \
    redis-server \
    sqlite3 \
    zstd

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt