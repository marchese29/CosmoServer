# CosmoServer Plugin Architecture Plan

## Overview

This document outlines the plugin system architecture for CosmoServer, focusing on a **bundled pyproject.toml approach** that maintains clean separation between core server dependencies and plugin dependencies while leveraging UV's dependency resolution.

## Core Architecture: Bundled Dependencies

### Design Principles

1. **Core server pyproject.toml stays pristine** - can run clean server without any plugins
2. **Plugins managed via separate tracking** - installed plugins tracked in user data directory
3. **Bundled environment for production** - generated pyproject.bundled.toml combines server + plugin dependencies
4. **UV handles all dependency resolution** - leverages UV's superior conflict detection

### File Structure

```
cosmo-server/
├── pyproject.toml              # Clean server-only dependencies
├── pyproject.bundled.toml      # Generated: server + plugins (gitignored)
├── scripts/
│   └── bundle_plugins.py       # Generates bundled.toml
└── ~/.local/share/cosmoserver/plugins/
    └── installed_plugins.txt   # List of installed plugin sources
```

**Note**: Add `pyproject.bundled.toml` to `.gitignore` since it's a generated file that shouldn't be committed to version control.

### Workflow

1. **Development**: Use clean `pyproject.toml` - `uv run python main.py`
2. **Plugin Installation**: Add to `installed_plugins.txt`, test for conflicts
3. **Production**: Generate bundled config, sync dependencies, restart with bundled environment
4. **Plugin Discovery**: At startup, discover plugins via manifests and register them

## Plugin Installation Process

Please note: the below is ILLUSTRATIVE but not rote.  We will need to adapt these things as we implement the feature.

### 1. Install Plugin Endpoint

```python
async def install_plugin(plugin_source: str):
    # Add to plugins tracking file
    plugins_file = get_user_data_dir() / "plugins" / "installed_plugins.txt"
    
    # Test for conflicts before committing
    conflict_check = await test_plugin_compatibility(plugin_source)
    if conflict_check["conflict"]:
        raise HTTPException(409, f"Dependency conflict: {conflict_check['details']}")
    
    # Add to file
    with open(plugins_file, "a") as f:
        f.write(f"{plugin_source}\n")
    
    return {"message": "Plugin added. Generate bundled environment and restart."}
```

### 2. Conflict Detection

```python
async def test_plugin_compatibility(new_plugin_source: str):
    # Create temporary bundled config with new plugin
    current_plugins = get_current_plugins()
    test_plugins = current_plugins + [new_plugin_source]
    
    # Generate test bundle
    temp_config = create_bundled_config_with_plugins(test_plugins)
    
    # Test UV resolution
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml") as f:
        toml.dump(temp_config, f)
        f.flush()
        
        result = subprocess.run([
            "uv", "lock", "--project", f.name
        ], capture_output=True, text=True)
        
        return {
            "conflict": result.returncode != 0,
            "details": result.stderr if result.returncode != 0 else None
        }
```

### 3. Bundle Generation Script

```python
def generate_bundled_config():
    # Read server dependencies
    with open("pyproject.toml") as f:
        server_config = toml.load(f)
    
    # Read installed plugins
    plugins_file = get_user_data_dir() / "plugins" / "installed_plugins.txt"
    plugin_sources = []
    if plugins_file.exists():
        plugin_sources = [line.strip() for line in plugins_file.read_text().split("\n") if line.strip()]
    
    # Create bundled config
    bundled = deepcopy(server_config)
    bundled["project"]["name"] = "cosmo-server-bundled"
    bundled["project"]["dependencies"].extend(plugin_sources)
    
    # Write bundled toml
    with open("pyproject.bundled.toml", "w") as f:
        toml.dump(bundled, f)
```

## Plugin Discovery & Loading

### Plugin Manifest Requirement

Each plugin must include `cosmo.json` in package root (some change may come during implementation):

```json
{
  "name": "Smart Switch Plugin",
  "version": "1.0.0",
  "plugin_class": "smart_switch.SmartSwitchPlugin",
  "description": "Controls smart switches via Zigbee",
  "requires_webhooks": true,
  "webhook_prefix": "/zigbee"
}
```

### Runtime Discovery

```python
def discover_installed_plugins():
    plugins = []
    
    # Look through installed packages for cosmo-plugin.json
    for dist in importlib.metadata.distributions():
        try:
            manifest_text = dist.read_text("cosmo.json")
            if manifest_text:
                manifest = json.loads(manifest_text)
                plugins.append({
                    "package_name": dist.metadata["Name"],
                    "manifest": manifest
                })
        except (FileNotFoundError, json.JSONDecodeError):
            continue
    
    return plugins

async def load_plugins_at_startup():
    plugins = discover_installed_plugins()
    
    for plugin_info in plugins:
        manifest = plugin_info["manifest"]
        
        # Import plugin class
        module_name, class_name = manifest["plugin_class"].split(":")
        module = importlib.import_module(module_name)
        plugin_class = getattr(module, class_name)
        plugin_instance = plugin_class()
        
        # Register with PluginService
        PLUGIN_SERVICE.get().register_plugin(plugin_instance)
        
        # Register webhooks if needed
        if manifest.get("requires_webhooks"):
            register_plugin_routes(plugin_instance, manifest["webhook_prefix"])
```

## Dependency Management Gotchas

### Critical Python Import System Limitations

1. **Global sys.modules cache** - Once a package is imported, that version is cached for the entire process
2. **sys.path ordering matters** - First location found wins for initial import
3. **No true isolation in single process** - All imports share the same namespace

### Why Other Approaches Don't Work

- **Runtime loading with --target**: Plugin dependencies can override server dependencies, potentially breaking core functionality
- **MCP-only approach**: Too narrow for plugin needs (webhooks, direct function calls, etc.)  
- **Process isolation**: Adds significant complexity for limited benefit in this domain

### Dependency Conflict Reality

Even with conflict detection, plugins and server share the same Python environment. This means:

- Plugin dependencies can theoretically override server dependencies
- Testing needs to include plugin combinations
- Some plugin combinations may be mutually exclusive
- Documentation should warn about dependency risks for git-based plugins

## Production Deployment

### Environment Setup

```bash
# Generate bundled environment
python scripts/bundle_plugins.py

# Install bundled dependencies
uv sync --project pyproject.bundled.toml

# Run with plugins
uv run --project pyproject.bundled.toml python main.py
```

### Debugging & Support

- Include `uv.lock` (from bundled environment) in bug reports
- List of installed plugins helps reproduce issues
- Core server can always be run clean for comparison

## API Endpoints

### CRUD Operations
- `POST /plugins/` - Add plugin metadata (source URL/package name)
- `GET /plugins/` - List all plugins with installation status  
- `DELETE /plugins/{plugin_id}` - Remove plugin metadata

### RPC Operations
- `POST /plugins/{plugin_id}/install` - Add to bundle, test conflicts
- `POST /plugins/{plugin_id}/uninstall` - Remove from bundle
- `GET /plugins/installed` - List currently registered plugins

## Database Schema

```python
class Plugin(Base, UUIDTimestampMixin):
    name: str                    # Display name
    source: str                  # PyPI package or git URL
    install_status: str          # "pending", "installed", "failed"
    error_message: str | None    # Installation error details
```

## Implementation Priority

1. **Basic plugin database model and CRUD endpoints**
2. **Bundle generation script and conflict detection**
3. **Plugin manifest support and discovery**
4. **Integration with startup process**
5. **Enhanced error handling and rollback**

## Trade-offs Accepted

- **Restart required** for plugin changes (acceptable for production systems)
- **Two environments** (development vs bundled production)
- **Git plugin risks** (advertised as power-user feature)
- **Shared dependency space** (conflicts possible but manageable with good tooling)
