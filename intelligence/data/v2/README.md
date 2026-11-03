# Assistant Response Dataset v2

`assistant-sft.jsonl` contains 72 project-authored response examples. The training
script deterministically divides this source into training and validation subsets
using `sha256(seed:id)`; its default seed is 42 and validation fraction is 0.2.
`assistant-eval.jsonl` contains 34 separate held-out examples and is never used by
the training script. `manifest.json` records provenance, license, roles, counts,
checksums, split policy, coverage, and known limitations.

The examples are manually written from PK-OS documentation and capability
descriptions under the repository's GPL-2.0-or-later license. No personal files,
microphone recordings, or user conversations were collected. This small dataset
only covers assistant responses about PK-OS; it does not teach intent routing,
argument extraction, planning, or tool selection. The evaluation topics overlap
with training topics, so it is a limited regression set rather than a broad
generalization benchmark. The held-out questions use varied wording and cover
additional edge cases around permissions, recovery, updates, keyboard access,
and evidence provenance, but topics still overlap with training. Passing the
50-example preflight gate does not establish data sufficiency or model quality.

Validate the bundle with:

```powershell
py -3.12 -m intelligence.scripts.validate_dataset
```

The validator uses only the Python standard library and checks schema, provenance,
counts, checksums, duplicate IDs, and train/test ID separation. Any edit to either
JSONL file requires updating the manifest checksum and count.

Checksums cover the exact committed UTF-8/LF bytes. `.gitattributes` keeps the
JSONL files at LF on Windows and Linux; CRLF-transformed copies do not match the
manifest.
