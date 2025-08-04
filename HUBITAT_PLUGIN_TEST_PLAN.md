# CosmoHubitatPlugin Test Plan

## Overview
Testing the plugin system using the real CosmoHubitatPlugin from https://github.com/marchese29/CosmoHubitatPlugin

## Plugin Details
- **Package name**: `cosmohubitatplugin`
- **Plugin class**: `cosmohubitatplugin.HubitatPlugin`
- **Expected routes**: `POST /hubitat/he_event`
- **Dependencies**: `cosmocore` (shared with main server)

## Test Steps

### Step 1: Start bundled server in fastapi-dev mode
```bash
uv run python scripts/bundle_start.py --fastapi-dev
```
**Expected**: Server starts successfully with auto-reload enabled

### Step 2: Create plugin via CREATE CRUD route
```bash
curl -X POST "http://localhost:8000/plugins/" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "CosmoHubitatPlugin",
    "source": "https://github.com/marchese29/CosmoHubitatPlugin",
    "source_type": "git",
    "version": "main"
  }'
```
**Expected**: 
- Success response with plugin ID
- Plugin record created with `install_status: "pending"`

### Step 3: Verify plugin status
```bash
curl "http://localhost:8000/plugins/"
```
**Expected**: 
- Plugin exists in list
- Status is "pending"
- No error messages

### Step 4: Kill the bundled server
Stop server with Ctrl+C

### Step 5: Create manifest file
Since the plugin doesn't have a cosmo.json manifest:

1. Check plugin data directory: `~/.local/share/cosmoserver/plugins/`
2. Look for `cosmohubitatplugin` directory 
3. Create `cosmo.json` with:
```json
{
  "name": "CosmoHubitatPlugin",
  "version": "0.1.0",
  "plugin_class": "cosmohubitatplugin.HubitatPlugin",
  "description": "Hubitat plugin for the cosmo server",
  "url_prefix": "/hubitat"
}
```

### Step 6: Restart bundled server
```bash
uv run python scripts/bundle_start.py --fastapi-dev
```
**Expected**: 
- Server starts successfully
- Plugin status moves from "pending" to "installed"

### Step 7: Verify bundled TOML configuration
Check `pyproject.bundled.toml` contains:

**Name change**:
```toml
[project]
name = "cosmo-server-bundled"
```

**Plugin dependency added**:
```toml
dependencies = [
    # ... existing dependencies ...
    "cosmohubitatplugin"
]
```

**Git sources (both preserved and new)**:
```toml
[tool.uv.sources]
cosmocore = { git = "https://github.com/marchese29/CosmoCore" }  # PRESERVED
cosmohubitatplugin = { git = "https://github.com/marchese29/CosmoHubitatPlugin" }  # NEW
```

### Step 8: Verify Hubitat plugin routes are present
```bash
curl "http://localhost:8000/docs"
```
**Expected**: OpenAPI docs show `/hubitat/he_event` endpoint

**Alternative verification**:
```bash
curl -X POST "http://localhost:8000/hubitat/he_event" \
  -H "Content-Type: application/json" \
  -d '{"device_id": "123", "attribute": "switch", "value": "on"}'
```
**Expected**: Route exists (may return error due to missing data, but should not be 404)

## Verification Points

### Critical Success Criteria
1. ✅ Plugin created successfully via API
2. ✅ Bundled config includes both existing and new git sources  
3. ✅ Plugin status transitions from "pending" to "installed"
4. ✅ Plugin routes are accessible under `/hubitat` prefix
5. ✅ No dependency conflicts during bundling

### Common Issues to Watch For
- Package name extraction from git URL
- Plugin class path resolution
- Dependency conflict with shared `cosmocore` dependency
- Route registration and prefix handling
- Plugin manifest discovery and validation

## Notes
- Stop and check in if any unexpected behavior occurs
- Ready to fix issues and restart if needed
- All plugin data stored in `~/.local/share/cosmoserver/plugins/`
- Database stores plugin state independently of filesystem
