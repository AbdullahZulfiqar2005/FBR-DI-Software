#!/bin/bash

#Install dependencies
pip install -r requirements.txt

# Run the Python application in the background
python3 app.py &

# Wait a few seconds to ensure the server starts
sleep 3

# Open Firefox pointing to localhost:5000
firefox http://localhost:5000
