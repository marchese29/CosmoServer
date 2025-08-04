# CosmoServer Plugin Architecture Plan

## Overview

This document outlines the plugin system architecture for CosmoServer, focusing on a **separate XDG environment approach** that maintains clean separation between core server dependencies and plugin dependencies while leveraging UV's dependency resolution in isolated environments.

## Core Architecture: Separate XDG Environment

### Design Principles

1. **Core server repository stays pristine** - can run clean server without any plugins
2. **Plugins managed via database + separate environment** - installed plugins tracked in database, bundled environment in XDG data directory
3. **Isolated bundled environment** - separate virtual environment with plugin dependencies in XDG-compliant location
4. **UV handles all dependency resolution** - leverages UV's superior conflict detection in isolated environment
5. **Restart-based workflow** - plugin changes require server restart for activation
6. **Symlinked source code** - bundled environment links back to main repository source

### File Structure

```
# Main Repository (stays completely clean)
cosmo-server/
├── pyproject.toml              # Clean server-only dependencies
├── uv.lock                     # Clean server lock file
└── src/cosmoserver/            # Source code in src layout
    ├── __init__.py
    ├── main.py
    ├── startup.py
    ├── util.py
    ├── exec_utils.py
    ├── mcps.py
    ├── routes/
    │   ├── __init__.py
    │   ├── crud.py
    │   ├── rpc.py
    │   └── plugins.py
    ├── models/
    │   ├── __init__.py
    │   ├── actions.py
    │   ├── api.py
    │   └── rules.py
    ├── database/
    │   ├── __init__.py
    │   ├── base.py
    │   └── models.py
    └── agent/
        ├── __init__.py
        ├── simple_prompt.txt
        └── complex_prompt.txt

# XDG Data Directory (~/.local/share/cosmoserver/)
~/.local/share/cosmoserver/
├── cosmo.db                    # Database (existing)
├── plugins/                    # Plugin installation directory (existing)
│   ├── plugin1_package/
│   ├── plugin2_package/
│   └── ...
└── bundled/                    # NEW: Separate bundled environment
    ├── pyproject.toml          # Generated with plugin dependencies
    ├── uv.lock                 # Resolved bundled dependencies
    ├── .venv/                  # Separate virtual environment
    └── src/cosmoserver/        # Symlinked source tree
        ├── __init__.py -> ../../../../../cosmo-server/src/cosmoserver/__init__.py
        ├── main.py -> ../../../../../cosmo-server/src/cosmoserver/main.py
        ├── startup.py -> ../../../../../cosmo-server/src/cosmoserver/startup.py
        ├── util.py -> ../../../../../cosmo-server/src/cosmoserver/util.py
        ├── exec_utils.py -> ../../../../../cosmo-server/src/cosmoserver/exec_utils.py
        ├── mcps.py -> ../../../../../cosmo-server/src/cosmoserver/mcps.py
        ├── routes/ -> ../../../../../cosmo-server/src/cosmoserver/routes/
        ├── models/ -> ../../../../../cosmo-server/src/cosmoserver/models/
        ├── database/ -> ../../../../../cosmo-server/src/cosmoserver/database/
        └── agent/ -> ../../../../../cosmo-server/src/cosmoserver/agent/
```

### Workflow

1. **Development**: Use clean environment - `uv run fastapi dev src/cosmoserver/main.py` from main repository
2. **Plugin Addition**: Create database record via CRUD API, test for conflicts in temporary environment  
3. **Bundled Mode**: Generate bundled environment with symlinks, run from XDG data directory
4. **Clean Mode**: Run directly from main repository without plugins

### Bundled Environment Commands

```bash
# Clean mode (default) - runs directly from main repository
uv run fastapi dev src/cosmoserver/main.py --port 8000

# Bundled mode - sets up and runs from XDG bundled environment (when implemented)
python scripts/bundle_start.py --fastapi-dev --port 8001

# Clean mode via script - runs directly from main repository
python scripts/bundle_start.py --clean --fastapi-dev --port 8001
```

## Database Schema

### Plugin Model with Enums

```python
from enum import Enum

class PluginSourceType(str, Enum):
    PYPI = "pypi"
    GIT = "git"

class PluginInstallStatus(str, Enum):
    UNINSTALLED = "uninstalled"  # Found in directory but not in bundled env
    PENDING = "pending"          # Added to DB, needs restart to install
    INSTALLED = "installed"      # Currently active in bundled env
    FAILED = "failed"           # Installation failed

class Plugin(Base, UUIDTimestampMixin):
    __tablename__ = "plugins"
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)  # PyPI package or git URL
    source_type: Mapped[PluginSourceType] = mapped_column(Enum(PluginSourceType), nullable=False)
    installed_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    updated_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    install_status: Mapped[PluginInstallStatus] = mapped_column(Enum(PluginInstallStatus), default=PluginInstallStatus.PENDING)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
```

### Version Management Flow

**Plugin Creation:**
- User creates plugin via `POST /plugins/` with source + version
- System tests bundled build for conflicts using UV in temporary environment
- If successful: save with `updated_version` set, `installed_version` null, status="pending"
- If failed: save with status="failed" and error message

**Startup Process:**
- For each plugin with `updated_version` set:
  - Move `updated_version` → `installed_version`
  - Clear `updated_version`
  - Set status="installed"
- Load and register plugins with status="installed"

## Plugin Manifest Format

Each plugin must include `cosmo.json` in package root:

```json
{
  "name": "Smart Switch Plugin",
  "version": "1.0.0",
  "plugin_class": "my_plugin.switches.SmartSwitchPlugin",
  "description": "Controls smart switches via Zigbee",
  "url_prefix": "/zigbee"
}
```

**Key Changes from Original Plan:**
- Removed webhook-specific fields - routing is handled by the plugin code itself
- `url_prefix` is optional and applies to any routes the plugin registers
- `plugin_class` must be fully qualified module path (no import games)

## Plugin Installation Process

### 1. CRUD-Only Approach (No RPC)

```python
# CRUD Operations
POST /plugins/          # Create plugin record + test conflicts
GET /plugins/           # List all plugins with status  
GET /plugins/{id}       # Get specific plugin
PUT /plugins/{id}       # Update only updated_version field
DELETE /plugins/{id}    # Remove plugin record
```

### 2. Conflict Detection During Creation

```python
async def create_plugin(plugin_data: PluginCreate):
    # Test bundle generation with new plugin in temporary environment
    current_plugins = get_plugins_for_bundle()
    test_plugins = current_plugins + [format_plugin_dependency(plugin_data)]
    
    # Create temporary bundled environment and test with UV
    success, error = await test_bundled_dependencies_in_temp_env(test_plugins)
    if not success:
        raise HTTPException(409, f"Dependency conflict: {error}")
    
    # Create database record with updated_version set
    return create_plugin_record(plugin_data)
```

### 3. Bundled Environment Setup

```python
import tomlkit
import shutil
from pathlib import Path

def get_bundled_env_dir() -> Path:
    """Get bundled environment directory in XDG data location."""
    return get_user_data_dir() / "bundled"

def setup_bundled_environment(plugins: list[Plugin]):
    """Set up complete bundled environment with symlinks."""
    bundled_dir = get_bundled_env_dir()
    
    # Clean and recreate bundled directory
    if bundled_dir.exists():
        shutil.rmtree(bundled_dir)
    bundled_dir.mkdir(parents=True)
    
    # Generate bundled pyproject.toml in bundled directory
    generate_bundled_config(plugins, bundled_dir)
    
    # Create symlinked source tree
    create_source_symlinks(bundled_dir)
    
    # Initialize UV environment in bundled directory
    run_uv_lock_and_sync(bundled_dir)

def generate_bundled_config(plugins: list[Plugin], bundled_dir: Path):
    """Generate pyproject.toml in bundled directory."""
    # Read server dependencies from main repository
    main_repo_path = Path(__file__).parent.parent  # Adjust as needed
    with open(main_repo_path / "pyproject.toml", "r") as f:
        server_config = tomlkit.parse(f.read())
    
    # Create bundled config
    bundled = deepcopy(server_config)
    bundled["project"]["name"] = "cosmo-server-bundled"
    
    # Add plugin dependencies
    for plugin in plugins:
        dependency_spec = format_plugin_dependency(plugin)
        bundled["project"]["dependencies"].append(dependency_spec)
    
    # Write bundled toml
    with open(bundled_dir / "pyproject.toml", "w") as f:
        f.write(tomlkit.dumps(bundled))

def create_source_symlinks(bundled_dir: Path):
    """Create symlinks to main repository source code."""
    main_repo_path = Path(__file__).parent.parent  # Adjust as needed
    bundled_src_dir = bundled_dir / "src" / "cosmoserver"
    bundled_src_dir.mkdir(parents=True, exist_ok=True)
    
    # Source directory in main repository
    main_src_dir = main_repo_path / "src" / "cosmoserver"
    
    # Files to symlink
    files_to_link = [
        "__init__.py", "main.py", "startup.py", "util.py", 
        "exec_utils.py", "mcps.py"
    ]
    
    # Directories to symlink
    dirs_to_link = [
        "routes", "models", "database", "agent"
    ]
    
    # Create file symlinks
    for file_name in files_to_link:
        source = main_src_dir / file_name
        target = bundled_src_dir / file_name
        if source.exists():
            target.symlink_to(source)
    
    # Create directory symlinks
    for dir_name in dirs_to_link:
        source = main_src_dir / dir_name
        target = bundled_src_dir / dir_name
        if source.exists():
            target.symlink_to(source)

def run_uv_lock_and_sync(bundled_dir: Path):
    """Run UV commands in bundled directory."""
    import subprocess
    import os
    
    # Change to bundled directory and run UV commands
    original_cwd = Path.cwd()
    try:
        os.chdir(bundled_dir)
        
        # Generate lock file
        subprocess.run(["uv", "lock"], check=True)
        
        # Sync dependencies
        subprocess.run(["uv", "sync"], check=True)
        
    finally:
        os.chdir(original_cwd)
```

## Plugin Discovery & Loading

### Runtime Discovery

```python
def discover_plugins_in_directory():
    """Scan plugin directory for cosmo.json manifests."""
    plugin_dir = get_plugin_data_dir()
    manifests = []
    
    for package_dir in plugin_dir.iterdir():
        if package_dir.is_dir():
            manifest_file = package_dir / "cosmo.json"
            if manifest_file.exists():
                try:
                    manifest_data = json.loads(manifest_file.read_text())
                    manifests.append(PluginManifest(**manifest_data))
                except (json.JSONDecodeError, ValidationError) as e:
                    logger.warning(f"Invalid manifest in {package_dir}: {e}")
    
    return manifests

async def startup_plugin_management():
    """Complete plugin management at startup."""
    # 1. Discover plugins in directory
    found_manifests = discover_plugins_in_directory()
    
    # 2. Sync with database (create "uninstalled" records for new finds)
    sync_database_with_found_plugins(found_manifests)
    
    # 3. Process version updates (pending → installed)
    process_plugin_version_updates()
    
    # 4. Load and register installed plugins
    await load_and_register_installed_plugins()

async def load_and_register_installed_plugins():
    """Load plugins marked as installed in database."""
    installed_plugins = get_installed_plugins()
    
    for plugin_record in installed_plugins:
        try:
            # Load manifest from directory
            manifest = get_plugin_manifest(plugin_record.source)
            
            # Import plugin class (fully qualified path)
            module_name, class_name = manifest.plugin_class.rsplit(".", 1)
            module = importlib.import_module(module_name)
            plugin_class = getattr(module, class_name)
            plugin_instance = plugin_class()
            
            # Register with PluginService
            PLUGIN_SERVICE.get().register_plugin(plugin_instance)
            
            # Register routes if plugin has url_prefix
            if manifest.url_prefix:
                register_plugin_routes(plugin_instance, manifest.url_prefix)
                
        except Exception as e:
            logger.error(f"Failed to load plugin {plugin_record.name}: {e}")
            update_plugin_status(plugin_record.id, PluginInstallStatus.FAILED, str(e))
```

## Production Deployment

### Environment Setup

```bash
# Clean mode (no plugins) - runs from main repository
python scripts/bundle_start.py --clean --fastapi-dev --port 8001

# Bundled mode (with plugins) - sets up XDG environment and runs from there
python scripts/bundle_start.py --fastapi-dev --port 8001
```

### Bundle Start Script Flow

```python
def bundled_startup(args):
    """Start server in bundled mode with plugins."""
    # 1. Get plugins from database
    plugins = get_plugins_for_bundle(db)
    
    # 2. Set up bundled environment in XDG data directory
    setup_bundled_environment(plugins)
    
    # 3. Change to bundled directory and start server
    bundled_dir = get_bundled_env_dir()
    os.chdir(bundled_dir)
    
    # 4. Run server from bundled environment
    subprocess.run([
        "uv", "run", "fastapi", "dev", "src/cosmoserver/main.py",
        "--host", args.host, "--port", args.port
    ], check=True)

def clean_startup(args):
    """Start server in clean mode without plugins."""
    # Run directly from main repository
    subprocess.run([
        "uv", "run", "fastapi", "dev", "src/cosmoserver/main.py", 
        "--host", args.host, "--port", args.port
    ], check=True)
```

## Implementation Priority

1. **Add TOML manipulation dependency** (tomlkit)
2. **Database model with enums and version tracking**
3. **Plugin manifest Pydantic model**  
4. **Bundled environment utilities** (XDG directory setup, symlinks)
5. **Modified bundle_start.py** with --clean flag and separate environment support
6. **Bundle generation and conflict testing utilities**
7. **CRUD endpoints with conflict detection**
8. **Startup discovery and loading integration**
9. **Remove hardcoded HubitatPlugin, use dynamic loading**

## Key Architectural Decisions

### Separate Environment Approach
- **XDG-compliant data directory** - follows standard data directory conventions
- **Symlinked source code** - bundled environment links back to main repository
- **Isolated virtual environments** - separate .venv for bundled vs clean
- **Clean repository** - main repository never modified by plugin system
- **Simple switching** - easy to toggle between clean and bundled modes

### Dependencies & Conflicts
- **Isolated Python environment** - plugins and server dependencies resolved separately
- **UV-based conflict detection** - test bundle generation in temporary environment before commit
- **Restart required** for all plugin changes (acceptable for production)
- **Dual version tracking** - clear indication when restart needed

### Trade-offs Accepted
- **Restart required** for plugin changes (acceptable for production systems)
- **Separate environments** (clean development vs bundled production)
- **Git plugin risks** (advertised as power-user feature)
- **Symlink dependency** (works on all modern platforms)
- **XDG data directory usage** (follows system conventions, easy cleanup)
