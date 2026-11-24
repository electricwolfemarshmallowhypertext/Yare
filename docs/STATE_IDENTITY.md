# State Identity and Execution Receipts

New packets use `hash_version: work-state.v2`. Their state hash covers the task, compiled state and normalized artifact content. Source-file locations, compile-time Git state, workspace validation and prior receipt/context pointers are not part of this content identity.

Receipts remain execution records. Each new receipt includes the full packet snapshot and its hash, then hashes the entire receipt. Repository metadata is therefore preserved and checked separately rather than silently trusted or used to change the work-state identity.

Packets without the new hash version retain their historical whole-packet verification. Existing stored rows and published record identifiers are not rewritten. Python readers, the producer, the assertion bench and the public verifier support both forms.

Artifact source identifiers use filename plus SHA-256 instead of an absolute path. Default discovery reads `.yare/captures/` and workspace-owned `lead-artifacts/`, not Yare's receipts, previous resolved context or bundled sample fixtures. Explicit artifact arguments remain supported.

These changes are local and have not been executed, migrated or deployed in this audit pass. Compatibility fixtures were added; execution remains on HOLD pending approval.
