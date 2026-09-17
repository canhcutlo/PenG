# Upload safety verification

Tested on 2026-09-17 with Python 3.14.6 and Node.js 24.19.0 on Windows.

## Automated checks

### Focused upload-storage tests

Command:

```powershell
python -m pytest tests/test_file_storage.py -q
```

Result: `8 passed in 0.39s`

Covered cases:

- Uploads are read in bounded 1 MiB chunks instead of one full in-memory read.
- The returned size and SHA-256 checksum match the saved content.
- A successful upload leaves no `.part` file behind.
- An oversized upload returns HTTP 413 and removes its partial directory.
- A simulated disk failure removes its partial directory.
- Duplicate-upload cleanup removes the newly written duplicate directory.
- Configured `.webm` uploads are accepted and unsupported legacy `.doc` files are rejected.
- Backend extension validation reads from `Settings`, avoiding a second hard-coded list.

### Frontend checks

Command:

```powershell
npm run check
```

Result: `10 passed, 0 failed`. JavaScript syntax checks also passed.

### Python syntax and diff checks

Commands:

```powershell
python -m compileall -q app tests
git diff --check
```

Result: both commands completed successfully.

## Manual before/after verification

A 16 MiB `.webm` file was saved once with the previous whole-file algorithm and
once with the new streaming `save_upload` implementation.

| Check | Previous behavior | New behavior |
| --- | ---: | ---: |
| Peak Python allocation | 16.14 MiB | 3.40 MiB |
| Elapsed time in this small local run | 0.053 s | 0.099 s |
| SHA-256 matches the source | Yes | Yes |
| Newly written duplicate remains on disk | Yes | No |

The timing is not intended as a speed benchmark. The purpose of the change is
bounded application memory, checksum calculation during the same read pass,
atomic finalization, and cleanup of failed or duplicate uploads.

## Full-suite note

The full AI/integration suite was not run in the lightweight local virtual
environment because it requires the project's model and processing stack. The
focused upload tests above do not download or initialize AI models.
