"""Career Decision Board engine.

Pipeline: ingest_gmail (Gmail API) → classify → store (SQLite)
         → analytics + recommend → render (dashboard JSON, xlsx, encrypted blob)
"""
__version__ = "2.0.0"
