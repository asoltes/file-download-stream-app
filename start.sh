#!/bin/bash
# Start Gunicorn in the background
gunicorn -w 4 -b 127.0.0.1:5000 app:app &

# Start NGINX in the foreground (keeps container alive)
nginx -g "daemon off;"
