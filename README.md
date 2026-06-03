# feed-sync

A small scheduled job that periodically collects posts from a configured list of
sources and syncs a compact SQLite store to cloud storage. It runs on GitHub
Actions every 30 minutes (and can be triggered manually).

Configuration and all credentials are supplied at runtime via encrypted GitHub
Secrets; nothing sensitive is stored in this repository.
