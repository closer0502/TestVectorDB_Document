#!/usr/bin/env python
"""CLI wrapper to ingest files into Qdrant using vector_db.ingest utilities."""

from vector_db import ingest


if __name__ == "__main__":
    ingest.ingest_directory(ingest.parse_args())
