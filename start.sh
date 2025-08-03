#!/bin/bash

# Load environment variables from .env file if it exists
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Create working directory if it doesn't exist
mkdir -p ./_tmp

# Run the application
python3 main.py