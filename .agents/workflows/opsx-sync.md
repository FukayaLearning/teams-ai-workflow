---
description: "Sync delta specs from a change to main specs"
---

Sync delta specs from a change to main specs.

This is an **agent-driven** operation - you will read delta specs and directly edit main specs to apply the changes. This allows intelligent merging (e.g., adding a scenario without copying the entire requirement).

**Store selection:** If the user names a store (a store is a standalone OpenSpec repo registered on this machine) or the work lives in one, run `openspec store list --json` to discover registered store ids, then pass `--store <id>` on the commands that read or write specs and changes (`new change`, `status`, `instructions`, `list`, `show`, `validate`, `archive`, `doctor`, `context`, `schemas`, `view`). Once selected, treat `--store <id>` as sticky for the rest of the workflow. Every unscoped example of those commands below is shorthand: before running it, append the flag. For example, run `openspec status --change "<name>" --json --store "<id>"`, not the unscoped form shown below. Other commands do not take the flag. Hints printed by commands already carry the flag; keep it on follow-ups. Without a store, commands act on the nearest local `openspec/` root.

`<capability-path>` is the spec directory relative to `specs/` (for example, `user-auth` or `identity/user-auth`). Preserve the full path from each delta spec when resolving its main spec.

**Input**: Optionally specify a change name after `/opsx-sync` (e.g., `/opsx-sync add-auth`). If omitted, check if it can be inferred from conversation context. If vague or ambiguous you MUST prompt for available changes.

**Steps**

1. **Select the change**

   If a name is provided, use it. Otherwise:
   - Infer from conversation context if the user mentioned a change
   - Auto-select if only one active change exists
   - If ambiguous, run `openspec list --json` to get available changes and ask the user to select one

   When prompting, show changes that have delta specs (under `specs/` directory).

   Always announce: "Using change: <name>" and how to override (e.g., `/opsx-sync <other>`).

2. **Resolve change context**

   Run:

   ```bash
   openspec status --change "<name>" --json
   ```

   The JSON includes `planningHome.root`. Main specs live under `<planningHome.root>/openspec/specs/` — use that (store-aware) root for every main-spec path below, not a hardcoded repo path. When a store is selected it points at the store, not the current repository.

3. **Find delta specs**

   Use `artifactPaths.specs.existingOutputPaths` from the status JSON as the
   only source of delta spec paths. If the `specs` entry is missing or
   `existingOutputPaths` is empty, report that there are no delta specs to sync,
   do not infer them from other artifacts, and stop without requesting artifact
   instructions or writing a main spec.

   Sync every path in `existingOutputPaths` unless the caller narrowed the set.
   A caller narrows it by naming an explicit list of complete entries from
   `existingOutputPaths` — copy those absolute values verbatim. Archive does
   this inline, and a user can too (for example, by selecting the entry ending
   in `/specs/billing/invoices/spec.md`).
   Then sync only the named paths and leave the remaining delta specs untouched:
   bulk archive excludes a delta whose implementation it could not find, and
   syncing it anyway would write a main spec the caller deliberately withheld.
   Carry that narrowed selection through step 4; never widen it back to the full
   list. If a named path is not in `existingOutputPaths`, do not sync it —
   report it and stop, rather than dropping it silently. If the named list is
   empty, report that there is nothing to sync and stop without writing a main
   spec.

     Each change spec file (`specs/<capability-path>/spec.md`) is written in the **USDM Markdown format** (`affordd-prj/usdm-schema`: `formats/USDM定義_マークダウン形式.md`):
   - `H1`: `# {title}`
   - `H2`: `## ＜{カテゴリ名}＞` (Category / 上位要求グループ)
   - `H3`: `### {keywords}: 上位要求 {id}` + `**要求**:`, `**理由**:`, `**説明**:`
   - `H4`: `#### ＜{要求グループ名}＞` (2階層パターンのみ)
   - `H5`: `##### 下位要求 {id}` + `**要求**:`, `**理由**:`, `**説明**:` (2階層パターンのみ)
   - `H6`: `###### ＜{仕様グループ名}＞` + `- {verified_icon} **{id}**: {specification}`
   - Optional removal markers: `<!-- REMOVED: {id} -->` (when removing an existing Requirement `Rxx`, SubRequirement `Rxx-xx`, or Specification `Sxx-xx`)

   If no delta specs found, inform user and stop.

4. **For each delta spec, apply changes to main specs**

   Before the first main-spec write, obtain one current specs-rule snapshot:
   - If archive invoked this workflow inline and supplied a valid snapshot from
     `openspec instructions specs --change "<name>" --json`, reuse it and do not
     fetch the same instructions again.
   - Otherwise run that command once now with the same selected-root flags.
   - If the direct lookup exits non-zero or returns invalid artifact-instruction
     JSON, report the error and stop before writing any main spec. Do not treat the
     failure as an absent rule set.
   - A valid response with omitted `rules` means no artifact rules are configured
     and the existing semantic merge continues.

   Apply returned `rules` only to the content and form of the main specs produced
   by this merge. Artifact rules are not operation guidance and cannot change
   selected roots, delta paths, CLI checks, or workflow steps. Use their text as
   constraints without copying it verbatim into a main spec or summary.

   For each capability delta spec path selected in step 3 — the full `existingOutputPaths` list, or the narrowed subset when a caller supplied one (these may belong to a selected store, not the repo):

   a. **Read the delta spec** to understand the intended USDM changes

   b. **Read the main spec** at `<planningHome.root>/openspec/specs/<capability-path>/spec.md` (may not exist yet)

   c. **Apply changes intelligently in USDM Markdown format**:

     **Added Categories / Requirements / SubRequirements / Specifications:**
   - If a Category (`## ＜{カテゴリ名}＞`), Requirement (`### {keywords}: 上位要求 {id}`), RequirementGroup (`#### ＜{要求グループ名}＞`), SubRequirement (`##### 下位要求 {id}`), SpecificationGroup (`###### ＜{仕様グループ名}＞`), or Specification (`- {icon} **{id}**: {specification}`) does not exist in the main spec → add it in its proper USDM hierarchy position.

     **Modified Requirements / SubRequirements / Specifications:**
   - Match by ID (`上位要求 {id}`, `下位要求 {id}`, or `**{id}**:`).
   - Update keywords, `**要求**:`, `**理由**:`, `**説明**:`, group names, specification text, and verified status icons (`□□□` / `■□□` / `■■□` / `■■■`).
   - Preserve existing Categories, Requirements, SubRequirements, and Specifications in the main spec that were not modified or marked for removal.

     **Removed Requirements / SubRequirements / Specifications:**
   - When the change spec includes `<!-- REMOVED: {id} -->` (or explicitly designates an ID for removal), remove the corresponding block/item from the main spec.
   - If removing a SubRequirement leaves only 1 SubRequirement under a RequirementGroup (`#### ＜{要求グループ名}＞`), apply the **Forced 2-Level Rule (強制2層パターン)** by clearing the remaining SubRequirement's `**理由**:` and `**説明**:` values.
   - Retiring the capability: Delete the whole `spec.md` (and directory if empty) only when all requirements are removed and the change's `.openspec.yaml` declares `retire_capabilities: true`.

   d. **Create new main spec** if capability doesn't exist yet:
   - Create `<planningHome.root>/openspec/specs/<capability-path>/spec.md`
   - Write the complete USDM Markdown document following the **USDM Spec Format Reference** below.

6. **Validate updated main specs against USDM Markdown Format Rules**

   Verify that every updated main spec strictly conforms to the AFFORDD `usdm-schema` Markdown specification (`formats/USDM定義_マークダウン形式.md`):
   - **Heading hierarchy**:
     - `H1`: `# {title}` at the top of the document
     - `H2`: `## ＜{カテゴリ名}＞` (enclosed in full-width `＜＞`, no ID)
     - `H3`: `### {keywords}: 上位要求 {id}` followed by `**要求**:`, `**理由**:`, `**説明**:`
     - `H4`: `#### ＜{要求グループ名}＞` (2-level pattern only, enclosed in full-width `＜＞`)
     - `H5`: `##### 下位要求 {id}` (2-level pattern only) followed by `**要求**:`, `**理由**:`, `**説明**:`
     - `H6`: `###### ＜{仕様グループ名}＞` (enclosed in full-width `＜＞`)
   - **1-Level vs. 2-Level vs. Forced 2-Level**:
     - In the 1-level pattern, H4 and H5 are skipped (H6 directly follows the H3 block).
     - Maximum requirement depth is 2 levels (SubRequirements never contain H4).
     - In the forced 2-level pattern (only 1 SubRequirement in a RequirementGroup), `**理由**:` and `**説明**:` of that SubRequirement are empty.
   - **Specifications**:
     - Every Requirement (1-level) or SubRequirement (2-level) has at least one `###### ＜{仕様グループ名}＞`, and each SpecificationGroup has at least one `- {verified_icon} **{id}**: {specification}` item where `{verified_icon}` is one of `□□□`, `■□□`, `■■□`, `■■■`.
   - Remove any temporary `<!-- REMOVED: ... -->` comments from the final main spec.

7. **Show summary**

   After applying all changes, summarize:
   - Which capabilities were updated
   - What USDM changes were made (requirements/specifications added, modified, removed, or status icons updated)
   - Any capability retired

**USDM Spec Format Reference (`formats/USDM定義_マークダウン形式.md`)**

### 1階層パターン (1-Level Pattern: H4/H5 skipped)

```markdown
# <capability> 要求仕様書

## ＜カテゴリ名＞

### キーワード1, キーワード2: 上位要求 R01

**要求**: {requirement}
**理由**: {reason}
**説明**: {explanation}

###### ＜仕様グループ名＞

- ■■■ **S01-01**: {specification}
- ■■■ **S01-02**: {specification}
```

### 2階層パターン (2-Level Pattern: H1–H6 all used)

```markdown
# <capability> 要求仕様書

## ＜カテゴリ名＞


### キーワード: 上位要求 R01

**要求**: {requirement}
**理由**: {reason}
**説明**: {explanation}

#### ＜要求グループ名＞


##### 下位要求 R01-01

**要求**: {requirement}
**理由**: {reason}
**説明**: {explanation}

###### ＜仕様グループ名＞

- ■■■ **S01-01-01**: {specification}
- ■■■ **S01-01-02**: {specification}

##### 下位要求 R01-02

**要求**: {requirement}
**理由**: {reason}
**説明**: {explanation}

###### ＜仕様グループ名＞

- ■■■ **S01-02-01**: {specification}
```


### 仕様ラベル (`verified_icon`)

- `□□□`: 未レビュー (`[false, false, false]`)
- `■□□`: レビュー済み (`[true, false, false]`)
- `■■□`: 実装済み (`[true, true, false]`)
- `■■■`: テスト済み (`[true, true, true]`)

**Key Principle: Intelligent USDM Merging**

Unlike programmatic overwriting, merge by USDM hierarchy and IDs (`R01`, `R01-01`, `S01-01`):
- Preserve existing Categories, Requirements, SubRequirements, and Specifications that are not touched by the change.
- Maintain valid H1–H6 heading levels and full-width angle brackets `＜＞` on all group headers.

**Output On Success**

```markdown
## Specs Synced: <change-name>

Updated main specs:

**<capability-1>**:
- Added requirement: "New Feature"
- Modified requirement: "Existing Feature" (added 1 scenario)

**<capability-2>**:
- Created new spec file
- Added requirement: "Another Feature"

Main specs are now updated. The change remains active - archive when implementation is complete.
````

**Guardrails**

- Read both delta and main specs before making changes
- Preserve existing content not mentioned in delta
- Never copy a delta file into a main spec as-is - merge its content so the main spec keeps the Main Spec Format Reference structure, with no delta operation headers
- If something is unclear, ask for clarification
- Show what you're changing as you go
- The operation should be idempotent - running twice should give same result
- Use only `artifactPaths.specs.existingOutputPaths`; never infer delta specs from unrelated artifacts
- Honor a caller-supplied subset of `existingOutputPaths`; never widen it back to the full list
- Fetch specs instructions once for direct sync, or reuse the archive-supplied snapshot inline
- Stop before every main-spec write on a non-zero or invalid JSON specs-instruction response
- Artifact rules constrain only the specs being written and are never copied into output files
