---
name: fix-i18n-namespace-mismatch
description: Fix i18n translations silently not rendering when template uses $t('namespace.key') but translations are stored in a different namespace
source: auto-skill
extracted_at: '2026-06-12T06:00:00.000Z'
---

# Fix i18n Namespace Mismatch — Translations Silently Not Rendering

When UI text shows as the **fallback key** (e.g., `step3.snapshotPanelTitle`) or **blank** instead of the actual translated text, the template's `$t()` namespace does not match where the translation is stored in the locale JSON.

## Symptoms

- Template: `{{ $t('step3.snapshotPanelTitle') }}`
- Translation exists in JSON: `"step3Snapshots": { "snapshotPanelTitle": "..." }`
- Result: **nothing renders** — i18n library can't find `step3.snapshotPanelTitle` because it lives under `step3Snapshots`

## Diagnosis Procedure

### Step 1: Extract All $t() Calls From the Template

Grep for all `$t('` or `$t("` patterns:

```bash
grep -oP "\$t\('\K[^']+" frontend/src/components/SomeComponent.vue
```

This gives you the list of **namespaced keys the template actually references**.

### Step 2: Find Where Those Keys Exist in Locale Files

For each key, search in `locales/en.json` and `locales/zh.json`:

```bash
grep -n "snapshotPanelTitle" locales/*.json
```

Check which **top-level namespace** contains the key. Compare with what the template uses.

### Step 3: Identify the Mismatch

Common mismatch patterns:
- Template uses `step3.key` but translation is in `step3Snapshots.key`
- Template uses `log.key` but translation is in `step3.log.key`
- Typos in namespace prefix: `step3` vs `step_3` vs `step3simulation`

## Fix Patterns

### Pattern A: Move Translations to Correct Namespace

Move keys from the wrong namespace to the correct one in **both** `en.json` and `zh.json`:

```json
// Before — split across wrong namespace
"step3Snapshots": {
  "snapshotPanelTitle": "Simulation Snapshots"
}

// After — moved to correct namespace
"step3": {
  "snapshotPanelTitle": "Simulation Snapshots"
}
```

### Pattern B: Add to Correct Namespace (Duplicate if Needed)

If the same key legitimately needs to exist under two namespaces (e.g., `step3` for component use and `step3Snapshots` for API messages), add it to **both**:

```json
"step3": {
  "snapshotPanelTitle": "Simulation Snapshots"
},
"step3Snapshots": {
  "snapshotPanelTitle": "Simulation Snapshots"
}
```

### Pattern C: Fix the Template

If the translation location is correct but the template has a typo, fix the `$t()` call:

```vue
<!-- Before -->
{{ $t('step3.snapshotPanelTitle') }}

<!-- After — matches actual namespace -->
{{ $t('step3Snapshots.snapshotPanelTitle') }}
```

## Prevention Checklist

1. **Establish a naming convention**: Component translations should live under the same namespace as the component's `$t()` prefix (e.g., `Step3Simulation.vue` → `step3.*`)
2. **After adding any translation key**, grep the component to verify the namespace matches
3. **Test both en and zh** — sometimes one locale has the key and the other doesn't, causing partial blank rendering
4. **Beware of namespace renaming**: When you rename or merge namespaces (e.g., `step3Snapshots` → `step3`), update ALL references across templates AND locale files

## Key Takeaway

> **i18n silently fails with no error.** If a key doesn't exist, the template renders the raw key string (e.g., `step3.snapshotPanelTitle`) or blank. Always verify that every `$t()` call's namespace prefix matches where the key is actually stored in the locale JSON files.
