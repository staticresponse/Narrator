#!/bin/bash
python -m nltk.downloader -d /usr/local/share/nltk_data wordnet
exec "$@"