#!/bin/bash
# Run script for Rider-PC Client

# Set Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Run the application
python -m pc_client.main "$@"
