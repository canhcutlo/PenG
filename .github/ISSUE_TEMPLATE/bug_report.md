---
name: Bug report
about: Report a reproducible problem in PenG
title: "[Bug]: "
labels: bug
assignees: ""
---

## Summary

Describe what went wrong and what you expected to happen.

## Reproduction

1. Steps to reproduce:
2. Input type and approximate file size:
3. Endpoint or UI tab:

## Environment

- Commit or version:
- Python version:
- CPU/GPU and CUDA version, if relevant:
- Local or Google Colab:

## Evidence

Paste a redacted traceback, job status, or API response. Do not include
documents, API keys, ngrok tokens, or personal data.

## Additional context

Mention whether the issue reproduces with `pytest tests/ -v -m "not integration"`
or requires model/integration dependencies.
