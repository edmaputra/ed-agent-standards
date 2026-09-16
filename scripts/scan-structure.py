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
from pathlib import Path
from typing import Any, Dict, List, Set

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
    "node_modules",
    "build",
    "target",
    "dist",
    "out",
    "bin",
    "obj",
    "coverage",
    ".pytest_cache",
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


def should_ignore_dir(dir_name: str, parent_path: Path = None) -> bool:
    if dir_name in IGNORED_DIRS:
        if dir_name == "out" and parent_path is not None:
            parts = parent_path.parts
            if "src" in parts or "adapter" in parts or "lib" in parts:
                return False
        return True
    return dir_name.startswith(".") and dir_name not in {".agents"}


def should_ignore_file(file_name: str) -> bool:
    _, ext = os.path.splitext(file_name)
    return ext in IGNORED_EXTENSIONS or file_name.startswith(".")


def detect_stacks(workspace: Path) -> List[str]:
    stacks = []
    has_java_or_kotlin = (
        (workspace / "pom.xml").exists()
        or (workspace / "build.gradle").exists()
        or (workspace / "build.gradle.kts").exists()
        or (workspace / "settings.gradle").exists()
        or (workspace / "settings.gradle.kts").exists()
        or any((workspace / p).exists() for p in ["src/main/java", "src/main/kotlin"])
    )
    if has_java_or_kotlin:
        stacks.append("java-kotlin")

    has_flutter = (workspace / "pubspec.yaml").exists()
    if has_flutter:
        stacks.append("flutter")

    has_angular = (
        (workspace / "angular.json").exists()
        or (workspace / "src" / "app").exists()
    )
    if not has_angular and (workspace / "package.json").exists():
        try:
            with open(workspace / "package.json", "r", encoding="utf-8") as f:
                content = f.read()
                if "@angular/core" in content:
                    has_angular = True
        except Exception:
            pass
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

        for root, dirs, files in os.walk(src_root / "src" / "main" if (src_root / "src" / "main").exists() else src_root):
            dirs[:] = [d for d in dirs if not should_ignore_dir(d, Path(root))]
            for file in sorted(files):
                if should_ignore_file(file):
                    continue
                if not (file.endswith(".java") or file.endswith(".kt")):
                    continue

                full_path = Path(root) / file
                rel_file = str(full_path.relative_to(workspace))
                parts = full_path.parts

                if "domain" in parts:
                    if "model" in parts or "entity" in parts:
                        mod_layers["domain"]["models"].append(rel_file)
                    elif "port" in parts or "spi" in parts:
                        mod_layers["domain"]["ports"].append(rel_file)
                    elif "event" in parts:
                        mod_layers["domain"]["events"].append(rel_file)
                    elif "exception" in parts:
                        mod_layers["domain"]["exceptions"].append(rel_file)
                    else:
                        mod_layers["domain"].setdefault("other", []).append(rel_file)
                elif "application" in parts:
                    if "usecase" in parts:
                        mod_layers["application"]["usecases"].append(rel_file)
                    elif "service" in parts:
                        mod_layers["application"]["services"].append(rel_file)
                    elif "port" in parts:
                        mod_layers["application"]["ports"].append(rel_file)
                    else:
                        mod_layers["application"].setdefault("other", []).append(rel_file)
                elif "adapter" in parts:
                    # check in vs out
                    if "in" in parts:
                        # find sub-adapter (e.g. rest, web, kafka)
                        idx = parts.index("in")
                        sub = parts[idx + 1] if idx + 1 < len(parts) - 1 else "general"
                        mod_layers["adapter"]["inbound"].setdefault(sub, []).append(rel_file)
                    elif "out" in parts:
                        idx = parts.index("out")
                        sub = parts[idx + 1] if idx + 1 < len(parts) - 1 else "general"
                        mod_layers["adapter"]["outbound"].setdefault(sub, []).append(rel_file)
                    else:
                        mod_layers["adapter"].setdefault("other", []).append(rel_file)
                elif "config" in parts or "infrastructure" in parts:
                    mod_layers["config"].append(rel_file)

        hex_data["modules"][module_name] = mod_layers

    return hex_data


def scan_flutter_features(workspace: Path) -> Dict[str, Any]:
    lib_path = workspace / "lib"
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
        flutter_data["entryPoints"].append("lib/main.dart")

    # Core directory
    core_path = lib_path / "core"
    if core_path.exists():
        for item in sorted(core_path.iterdir()):
            if item.is_dir() and not should_ignore_dir(item.name):
                flutter_data["core"][item.name] = [
                    str(p.relative_to(workspace))
                    for p in sorted(item.rglob("*.dart"))
                    if not should_ignore_file(p.name)
                ]

    # Features directory
    features_path = lib_path / "features"
    if features_path.exists():
        for feat in sorted(features_path.iterdir()):
            if feat.is_dir() and not should_ignore_dir(feat.name):
                feat_dict: Dict[str, Any] = {
                    "presentation": [],
                    "domain": [],
                    "data": [],
                }
                for layer in ["presentation", "domain", "data"]:
                    layer_dir = feat / layer
                    if layer_dir.exists():
                        feat_dict[layer] = [
                            str(p.relative_to(workspace))
                            for p in sorted(layer_dir.rglob("*.dart"))
                            if not should_ignore_file(p.name)
                        ]
                flutter_data["features"][feat.name] = feat_dict

    return flutter_data


def scan_angular_features(workspace: Path) -> Dict[str, Any]:
    app_path = workspace / "src" / "app"
    if not app_path.exists():
        # check alternative app dir
        alt = list(workspace.glob("**/src/app"))
        if alt:
            app_path = alt[0]
        else:
            return {"architecture": "angular", "status": "src/app directory not found"}

    angular_data: Dict[str, Any] = {
        "architecture": "feature-first-standalone",
        "core": {},
        "shared": {},
        "features": {},
    }

    # Core
    core_path = app_path / "core"
    if core_path.exists():
        for item in sorted(core_path.iterdir()):
            if item.is_dir() and not should_ignore_dir(item.name):
                angular_data["core"][item.name] = [
                    str(p.relative_to(workspace))
                    for p in sorted(item.rglob("*.ts"))
                    if not should_ignore_file(p.name)
                ]

    # Shared
    shared_path = app_path / "shared"
    if shared_path.exists():
        for item in sorted(shared_path.iterdir()):
            if item.is_dir() and not should_ignore_dir(item.name):
                angular_data["shared"][item.name] = [
                    str(p.relative_to(workspace))
                    for p in sorted(item.rglob("*.ts"))
                    if not should_ignore_file(p.name)
                ]

    # Features
    features_path = app_path / "features"
    if features_path.exists():
        for feat in sorted(features_path.iterdir()):
            if feat.is_dir() and not should_ignore_dir(feat.name):
                feat_dict: Dict[str, Any] = {
                    "components": [],
                    "services": [],
                    "store": [],
                    "models": [],
                    "routes": [],
                }
                for p in sorted(feat.rglob("*.*")):
                    if p.is_dir() or should_ignore_file(p.name):
                        continue
                    rel = str(p.relative_to(workspace))
                    name = p.name
                    if name.endswith(".component.ts") or name.endswith(".component.html"):
                        feat_dict["components"].append(rel)
                    elif name.endswith(".service.ts"):
                        feat_dict["services"].append(rel)
                    elif name.endswith(".state.ts") or name.endswith(".actions.ts") or name.endswith(".reducer.ts") or name.endswith(".selectors.ts") or name.endswith(".effects.ts") or "store" in p.parts:
                        feat_dict["store"].append(rel)
                    elif name.endswith(".model.ts") or name.endswith(".types.ts") or "models" in p.parts:
                        feat_dict["models"].append(rel)
                    elif name.endswith(".routes.ts") or name.endswith("-routing.module.ts"):
                        feat_dict["routes"].append(rel)

                angular_data["features"][feat.name] = feat_dict

    return angular_data


def scan_standards_repo(workspace: Path) -> Dict[str, Any]:
    rules_dir = workspace / "rules"
    if not rules_dir.exists():
        return {}

    rules_by_stack: Dict[str, List[Dict[str, str]]] = {}
    for stack_dir in sorted(rules_dir.iterdir()):
        if stack_dir.is_dir() and not should_ignore_dir(stack_dir.name):
            stack_rules = []
            for rule_file in sorted(stack_dir.glob("*.md")):
                # Read description from frontmatter if available
                desc = ""
                try:
                    with open(rule_file, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                        in_fm = False
                        for line in lines:
                            if line.strip() == "---":
                                if in_fm:
                                    break
                                in_fm = True
                                continue
                            if in_fm and line.startswith("description:"):
                                desc = line.split("description:", 1)[1].strip().strip('"\'')
                except Exception:
                    pass

                stack_rules.append({
                    "file": str(rule_file.relative_to(workspace)),
                    "name": rule_file.stem,
                    "description": desc,
                })
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
        if should_ignore_dir(item.name) or should_ignore_file(item.name):
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
        print(f"Error: Workspace path '{workspace}' does not exist or is not a directory.", file=os.sys.stderr)
        os.sys.exit(1)

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
        print(f"[scan-structure] Notice: {out_path} already exists. Use --force to overwrite.", file=os.sys.stderr)
        return

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(json_str)
        f.write("\n")

    print(f"[scan-structure] Generated project map at {out_path}", file=os.sys.stderr)


if __name__ == "__main__":
    main()
