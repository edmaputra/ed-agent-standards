#!/usr/bin/env python3
"""
Automated Project Structure Scanner for AI Agent Discovery.

Scans a project workspace and generates a classified JSON structure map tailored for
Hexagonal Java/Kotlin, Feature-First Flutter, Feature-First Angular, and shared stacks.

Usage:
    python3 scan-structure.py [workspace_path] [--output path] [--force] [--stdout]
"""

import argparse
import datetime
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

IGNORED_DIRS: Set[str] = {
    ".git",
    ".github",
    ".gradle",
    ".idea",
    ".vscode",
    ".angular",
    ".dart_tool",
    ".gemini",
    ".system_generated",
    ".turbo",
    ".next",
    ".nuxt",
    ".cache",
    ".venv",
    "venv",
    "env",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "node_modules",
    "build",
    "target",
    "dist",
    "out",
    "bin",
    "obj",
    "coverage",
    "__pycache__",
}

IGNORED_EXTENSIONS: Set[str] = {
    ".class",
    ".jar",
    ".war",
    ".pyc",
    ".pyo",
    ".pyd",
    ".DS_Store",
    ".lock",
}


def should_ignore_dir(dir_name: str, parent_path: Optional[Path] = None) -> bool:
    if dir_name in IGNORED_DIRS:
        if dir_name == "out" and parent_path is not None:
            lower_parts = [p.lower() for p in parent_path.parts]
            if any(p in lower_parts for p in ["src", "adapter", "adapters", "lib", "port", "ports"]):
                return False
        return True
    return dir_name.startswith(".") and dir_name not in {".agents"}


def should_ignore_file(file_name: str) -> bool:
    _, ext = os.path.splitext(file_name)
    return ext in IGNORED_EXTENSIONS or file_name.startswith(".")


def detect_stacks(workspace: Path) -> List[str]:
    stacks = []

    def check_java_kotlin(p: Path) -> bool:
        return (
            (p / "pom.xml").exists()
            or (p / "build.gradle").exists()
            or (p / "build.gradle.kts").exists()
            or (p / "settings.gradle").exists()
            or (p / "settings.gradle.kts").exists()
            or (p / "src" / "main" / "java").exists()
            or (p / "src" / "main" / "kotlin").exists()
        )

    def check_flutter(p: Path) -> bool:
        return (p / "pubspec.yaml").exists()

    def check_angular(p: Path) -> bool:
        if (p / "angular.json").exists() or (p / "src" / "app").exists():
            return True
        pkg_json = p / "package.json"
        if pkg_json.exists():
            try:
                with open(pkg_json, "r", encoding="utf-8") as f:
                    content = f.read()
                    if "@angular/core" in content:
                        return True
            except Exception:
                pass
        return False

    has_java_or_kotlin = check_java_kotlin(workspace)
    has_flutter = check_flutter(workspace)
    has_angular = check_angular(workspace)

    # Check 1-2 level subdirectories for monorepo layouts
    if not (has_java_or_kotlin and has_flutter and has_angular):
        try:
            for item in workspace.iterdir():
                if item.is_dir() and not should_ignore_dir(item.name, workspace):
                    if not has_java_or_kotlin and check_java_kotlin(item):
                        has_java_or_kotlin = True
                    if not has_flutter and check_flutter(item):
                        has_flutter = True
                    if not has_angular and check_angular(item):
                        has_angular = True
        except Exception:
            pass

    if has_java_or_kotlin:
        stacks.append("java-kotlin")
    if has_flutter:
        stacks.append("flutter")
    if has_angular:
        stacks.append("angular")

    if (workspace / "rules").exists() and (workspace / "README.md").exists():
        stacks.append("agent-standards")

    if not stacks:
        stacks.append("generic")

    return stacks


def scan_java_kotlin_hexagonal(workspace: Path) -> Dict[str, Any]:
    hex_data: Dict[str, Any] = {
        "architecture": "hexagonal",
        "modules": {},
    }

    # Search for source directories (supports root and multi-module Gradle/Maven)
    src_roots = []
    for root, dirs, _ in os.walk(workspace):
        dirs[:] = [d for d in dirs if not should_ignore_dir(d, Path(root))]
        p = Path(root)
        if (p / "src" / "main").exists():
            src_roots.append(p)

    if not src_roots and (workspace / "src").exists():
        src_roots.append(workspace)

    for src_root in src_roots:
        rel_mod = str(src_root.relative_to(workspace))
        module_name = "root" if rel_mod == "." else rel_mod

        mod_layers: Dict[str, Any] = {
            "domain": {"models": [], "ports": [], "events": [], "exceptions": []},
            "application": {"usecases": [], "services": [], "ports": []},
            "adapter": {"inbound": {}, "outbound": {}},
            "config": [],
        }
        entry_points: List[str] = []

        scan_dir = src_root / "src" / "main" if (src_root / "src" / "main").exists() else src_root
        for root, dirs, files in os.walk(scan_dir):
            dirs[:] = [d for d in dirs if not should_ignore_dir(d, Path(root))]
            for file in sorted(files):
                if should_ignore_file(file):
                    continue
                if not (file.endswith(".java") or file.endswith(".kt")):
                    continue

                full_path = Path(root) / file
                rel_file = str(full_path.relative_to(workspace))
                lower_parts = [p.lower() for p in full_path.parts]
                lower_file = file.lower()

                if "domain" in lower_parts:
                    if any(p in lower_parts for p in ["model", "models", "entity", "entities", "vo"]) or any(
                        lower_file.endswith(s) for s in ["entity.java", "entity.kt", "vo.java", "vo.kt", "record.java", "record.kt"]
                    ):
                        mod_layers["domain"]["models"].append(rel_file)
                    elif any(p in lower_parts for p in ["port", "ports", "spi", "spis", "repository", "repositories"]) or any(
                        lower_file.endswith(s) for s in ["repository.java", "repository.kt", "port.java", "port.kt", "spi.java", "spi.kt"]
                    ):
                        mod_layers["domain"]["ports"].append(rel_file)
                    elif any(p in lower_parts for p in ["event", "events"]) or any(
                        lower_file.endswith(s) for s in ["event.java", "event.kt"]
                    ):
                        mod_layers["domain"]["events"].append(rel_file)
                    elif any(p in lower_parts for p in ["exception", "exceptions", "error", "errors"]) or any(
                        lower_file.endswith(s) for s in ["exception.java", "exception.kt"]
                    ):
                        mod_layers["domain"]["exceptions"].append(rel_file)
                    else:
                        mod_layers["domain"].setdefault("other", []).append(rel_file)

                elif "application" in lower_parts:
                    if any(p in lower_parts for p in ["usecase", "usecases", "command", "commands", "query", "queries"]) or any(
                        lower_file.endswith(s) for s in ["usecase.java", "usecase.kt", "command.java", "command.kt", "query.java", "query.kt"]
                    ):
                        mod_layers["application"]["usecases"].append(rel_file)
                    elif any(p in lower_parts for p in ["service", "services"]) or any(
                        lower_file.endswith(s) for s in ["service.java", "service.kt"]
                    ):
                        mod_layers["application"]["services"].append(rel_file)
                    elif any(p in lower_parts for p in ["port", "ports", "spi", "spis"]) or any(
                        lower_file.endswith(s) for s in ["port.java", "port.kt", "spi.java", "spi.kt"]
                    ):
                        mod_layers["application"]["ports"].append(rel_file)
                    else:
                        mod_layers["application"].setdefault("other", []).append(rel_file)

                elif "adapter" in lower_parts or "adapters" in lower_parts:
                    # Determine whether inbound or outbound
                    in_keywords = {"in", "inbound", "driving"}
                    out_keywords = {"out", "outbound", "driven"}

                    found_in = next((p for p in in_keywords if p in lower_parts), None)
                    found_out = next((p for p in out_keywords if p in lower_parts), None)

                    if found_in:
                        idx = lower_parts.index(found_in)
                        sub = full_path.parts[idx + 1] if idx + 1 < len(full_path.parts) - 1 else "general"
                        mod_layers["adapter"]["inbound"].setdefault(sub, []).append(rel_file)
                    elif found_out:
                        idx = lower_parts.index(found_out)
                        sub = full_path.parts[idx + 1] if idx + 1 < len(full_path.parts) - 1 else "general"
                        mod_layers["adapter"]["outbound"].setdefault(sub, []).append(rel_file)
                    else:
                        # Direct sub-adapter check (e.g. adapter.rest, adapter.persistence)
                        adapter_kw = "adapter" if "adapter" in lower_parts else "adapters"
                        idx = lower_parts.index(adapter_kw)
                        sub = full_path.parts[idx + 1] if idx + 1 < len(full_path.parts) - 1 else "general"
                        sub_lower = sub.lower()

                        inbound_subs = {"rest", "web", "controller", "controllers", "messaging", "kafka", "amqp", "rabbitmq", "graphql", "grpc"}
                        outbound_subs = {"persistence", "jpa", "database", "r2dbc", "client", "clients", "http", "feign", "webclient", "redis"}

                        if sub_lower in inbound_subs:
                            mod_layers["adapter"]["inbound"].setdefault(sub, []).append(rel_file)
                        elif sub_lower in outbound_subs:
                            mod_layers["adapter"]["outbound"].setdefault(sub, []).append(rel_file)
                        else:
                            mod_layers["adapter"].setdefault("other", []).append(rel_file)

                elif any(p in lower_parts for p in ["config", "configuration", "infrastructure", "autoconfiguration", "autoconfigure"]):
                    mod_layers["config"].append(rel_file)

                elif lower_file.endswith("application.java") or lower_file.endswith("application.kt"):
                    entry_points.append(rel_file)
                else:
                    mod_layers.setdefault("other", []).append(rel_file)

        if entry_points:
            mod_layers["entryPoints"] = entry_points

        hex_data["modules"][module_name] = mod_layers

    return hex_data


def scan_flutter_features(workspace: Path) -> Dict[str, Any]:
    lib_path = workspace / "lib"
    if not lib_path.exists():
        # Check subdirectories (e.g. monorepo mobile/lib or app/lib)
        for sub in sorted(workspace.iterdir()):
            if sub.is_dir() and not should_ignore_dir(sub.name, workspace):
                if (sub / "pubspec.yaml").exists() and (sub / "lib").exists():
                    lib_path = sub / "lib"
                    break

    if not lib_path.exists():
        return {"architecture": "flutter", "status": "lib directory not found"}

    flutter_data: Dict[str, Any] = {
        "architecture": "feature-first",
        "entryPoints": [],
        "core": {},
        "features": {},
    }

    # Entry points
    if (lib_path / "main.dart").exists():
        flutter_data["entryPoints"].append(str((lib_path / "main.dart").relative_to(workspace)))

    # Core directory
    core_path = lib_path / "core"
    if core_path.exists():
        for item in sorted(core_path.iterdir()):
            if should_ignore_dir(item.name, core_path) or should_ignore_file(item.name):
                continue
            if item.is_dir():
                dart_files = []
                for root, dirs, files in os.walk(item):
                    dirs[:] = [d for d in dirs if not should_ignore_dir(d, Path(root))]
                    for f in sorted(files):
                        if f.endswith(".dart") and not should_ignore_file(f):
                            dart_files.append(str((Path(root) / f).relative_to(workspace)))
                if dart_files:
                    flutter_data["core"][item.name] = dart_files
            elif item.is_file() and item.name.endswith(".dart"):
                flutter_data["core"].setdefault("general", []).append(str(item.relative_to(workspace)))

    # Features directory
    features_path = lib_path / "features"
    if features_path.exists():
        for feat in sorted(features_path.iterdir()):
            if feat.is_dir() and not should_ignore_dir(feat.name, features_path):
                feat_dict: Dict[str, Any] = {
                    "presentation": [],
                    "domain": [],
                    "data": [],
                }
                captured: Set[str] = set()
                for layer in ["presentation", "domain", "data"]:
                    layer_dir = feat / layer
                    if layer_dir.exists():
                        layer_files = []
                        for root, dirs, files in os.walk(layer_dir):
                            dirs[:] = [d for d in dirs if not should_ignore_dir(d, Path(root))]
                            for f in sorted(files):
                                if f.endswith(".dart") and not should_ignore_file(f):
                                    rel = str((Path(root) / f).relative_to(workspace))
                                    layer_files.append(rel)
                                    captured.add(rel)
                        feat_dict[layer] = layer_files

                # Check for other dart files inside the feature
                other_files = []
                for root, dirs, files in os.walk(feat):
                    dirs[:] = [d for d in dirs if not should_ignore_dir(d, Path(root))]
                    for f in sorted(files):
                        if f.endswith(".dart") and not should_ignore_file(f):
                            rel = str((Path(root) / f).relative_to(workspace))
                            if rel not in captured:
                                other_files.append(rel)
                if other_files:
                    feat_dict["other"] = other_files

                flutter_data["features"][feat.name] = feat_dict

    return flutter_data


def scan_angular_features(workspace: Path) -> Dict[str, Any]:
    app_path = workspace / "src" / "app"
    if not app_path.exists():
        # Search safely skipping ignored directories
        found_app = None
        for root, dirs, _ in os.walk(workspace):
            dirs[:] = [d for d in dirs if not should_ignore_dir(d, Path(root))]
            p = Path(root)
            if (p / "src" / "app").exists():
                found_app = p / "src" / "app"
                break
        if found_app:
            app_path = found_app
        else:
            return {"architecture": "angular", "status": "src/app directory not found"}

    angular_data: Dict[str, Any] = {
        "architecture": "feature-first-standalone",
        "entryPoints": [],
        "core": {},
        "shared": {},
        "features": {},
    }

    # Entry points
    src_path = app_path.parent
    for entry in ["main.ts", "index.html"]:
        entry_file = src_path / entry
        if entry_file.exists():
            angular_data["entryPoints"].append(str(entry_file.relative_to(workspace)))

    # Core
    core_path = app_path / "core"
    if core_path.exists():
        for item in sorted(core_path.iterdir()):
            if should_ignore_dir(item.name, core_path) or should_ignore_file(item.name):
                continue
            if item.is_dir():
                ts_files = []
                for root, dirs, files in os.walk(item):
                    dirs[:] = [d for d in dirs if not should_ignore_dir(d, Path(root))]
                    for f in sorted(files):
                        if f.endswith(".ts") and not should_ignore_file(f):
                            ts_files.append(str((Path(root) / f).relative_to(workspace)))
                if ts_files:
                    angular_data["core"][item.name] = ts_files
            elif item.is_file() and item.name.endswith(".ts"):
                angular_data["core"].setdefault("general", []).append(str(item.relative_to(workspace)))

    # Shared
    shared_path = app_path / "shared"
    if shared_path.exists():
        for item in sorted(shared_path.iterdir()):
            if should_ignore_dir(item.name, shared_path) or should_ignore_file(item.name):
                continue
            if item.is_dir():
                ts_files = []
                for root, dirs, files in os.walk(item):
                    dirs[:] = [d for d in dirs if not should_ignore_dir(d, Path(root))]
                    for f in sorted(files):
                        if f.endswith(".ts") and not should_ignore_file(f):
                            ts_files.append(str((Path(root) / f).relative_to(workspace)))
                if ts_files:
                    angular_data["shared"][item.name] = ts_files
            elif item.is_file() and item.name.endswith(".ts"):
                angular_data["shared"].setdefault("general", []).append(str(item.relative_to(workspace)))

    # Features
    features_path = app_path / "features"
    if features_path.exists():
        for feat in sorted(features_path.iterdir()):
            if feat.is_dir() and not should_ignore_dir(feat.name, features_path):
                feat_dict: Dict[str, Any] = {
                    "components": [],
                    "services": [],
                    "store": [],
                    "models": [],
                    "routes": [],
                }
                other_files = []

                for root, dirs, files in os.walk(feat):
                    dirs[:] = [d for d in dirs if not should_ignore_dir(d, Path(root))]
                    for file in sorted(files):
                        if should_ignore_file(file):
                            continue
                        p = Path(root) / file
                        rel = str(p.relative_to(workspace))
                        name = p.name
                        lower_name = name.lower()
                        lower_parts = [part.lower() for part in p.parts]

                        if any(lower_name.endswith(ext) for ext in [".component.ts", ".component.html", ".component.scss", ".component.css"]):
                            feat_dict["components"].append(rel)
                        elif lower_name.endswith(".service.ts"):
                            feat_dict["services"].append(rel)
                        elif any(lower_name.endswith(ext) for ext in [".state.ts", ".actions.ts", ".reducer.ts", ".selectors.ts", ".effects.ts"]) or "store" in lower_parts:
                            feat_dict["store"].append(rel)
                        elif any(lower_name.endswith(ext) for ext in [".model.ts", ".types.ts"]) or "models" in lower_parts:
                            feat_dict["models"].append(rel)
                        elif lower_name.endswith(".routes.ts") or lower_name.endswith("-routing.module.ts"):
                            feat_dict["routes"].append(rel)
                        else:
                            other_files.append(rel)

                if other_files:
                    feat_dict["other"] = other_files

                angular_data["features"][feat.name] = feat_dict

    return angular_data


def scan_standards_repo(workspace: Path) -> Dict[str, Any]:
    rules_dir = workspace / "rules"
    if not rules_dir.exists():
        return {}

    rules_by_stack: Dict[str, List[Dict[str, Any]]] = {}
    for stack_dir in sorted(rules_dir.iterdir()):
        if stack_dir.is_dir() and not should_ignore_dir(stack_dir.name, rules_dir):
            stack_rules = []
            for rule_file in sorted(stack_dir.glob("*.md")):
                # Read description and globs from frontmatter if available
                desc = ""
                globs: List[str] = []
                try:
                    with open(rule_file, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    in_fm = False
                    in_globs = False
                    for line in lines:
                        stripped = line.strip()
                        if stripped == "---":
                            if in_fm:
                                break
                            in_fm = True
                            continue
                        if in_fm:
                            if stripped.startswith("description:"):
                                in_globs = False
                                desc = line.split("description:", 1)[1].strip().strip('"\'')
                            elif stripped.startswith("globs:"):
                                in_globs = True
                            elif in_globs:
                                if stripped.startswith("-"):
                                    glob_val = stripped.lstrip("-").strip().strip('"\'')
                                    if glob_val:
                                        globs.append(glob_val)
                                elif stripped and not stripped.startswith("#"):
                                    in_globs = False
                except Exception:
                    pass

                rule_entry: Dict[str, Any] = {
                    "file": str(rule_file.relative_to(workspace)),
                    "name": rule_file.stem,
                    "description": desc,
                }
                if globs:
                    rule_entry["globs"] = globs

                stack_rules.append(rule_entry)

            rules_by_stack[stack_dir.name] = stack_rules

    return {
        "architecture": "standards-repository",
        "stacks": rules_by_stack,
    }


def scan_workspace(workspace_path: str) -> Dict[str, Any]:
    workspace = Path(workspace_path).resolve()
    stacks = detect_stacks(workspace)

    output_data: Dict[str, Any] = {
        "schemaVersion": "1.0.0",
        "generatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "workspaceName": workspace.name,
        "workspaceRoot": str(workspace),
        "detectedStacks": stacks,
        "stackDetails": {},
    }

    if "java-kotlin" in stacks:
        output_data["stackDetails"]["java-kotlin"] = scan_java_kotlin_hexagonal(workspace)

    if "flutter" in stacks:
        output_data["stackDetails"]["flutter"] = scan_flutter_features(workspace)

    if "angular" in stacks:
        output_data["stackDetails"]["angular"] = scan_angular_features(workspace)

    if "agent-standards" in stacks:
        output_data["stackDetails"]["agent-standards"] = scan_standards_repo(workspace)

    # General top-level summary
    top_level_files = []
    top_level_dirs = []
    for item in sorted(workspace.iterdir()):
        if should_ignore_dir(item.name, workspace) or should_ignore_file(item.name):
            continue
        if item.is_dir():
            top_level_dirs.append(item.name)
        else:
            top_level_files.append(item.name)

    output_data["rootSummary"] = {
        "topLevelDirectories": top_level_dirs,
        "topLevelFiles": top_level_files,
    }

    return output_data


def main():
    parser = argparse.ArgumentParser(description="Scan project structure for AI agent discovery.")
    parser.add_argument("workspace", nargs="?", default=".", help="Root path of the workspace (default: current directory)")
    parser.add_argument("-o", "--output", help="Custom output JSON path")
    parser.add_argument("-f", "--force", action="store_true", help="Force overwrite existing output file")
    parser.add_argument("--stdout", action="store_true", help="Print JSON to stdout")

    args = parser.parse_args()
    workspace = Path(args.workspace).resolve()

    if not workspace.exists() or not workspace.is_dir():
        print(f"Error: Workspace path '{workspace}' does not exist or is not a directory.", file=sys.stderr)
        sys.exit(1)

    result = scan_workspace(str(workspace))
    json_str = json.dumps(result, indent=2)

    if args.stdout:
        print(json_str)
        if not args.output:
            return

    # Determine default output file
    if args.output:
        out_path = Path(args.output).resolve()
    else:
        agents_dir = workspace / ".agents"
        if agents_dir.exists() and agents_dir.is_dir():
            out_path = agents_dir / "project-structure.json"
        else:
            out_path = workspace / "project-structure.json"

    if out_path.exists() and not args.force:
        # File already exists, skip unless force
        print(f"[scan-structure] Notice: {out_path} already exists. Use --force to overwrite.", file=sys.stderr)
        return

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(json_str)
        f.write("\n")

    print(f"[scan-structure] Generated project map at {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
