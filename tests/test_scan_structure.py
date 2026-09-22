#!/usr/bin/env python3
"""
Unit tests for scan-structure.py.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# Add scripts directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import importlib
scan_structure = importlib.import_module("scan-structure")


class TestIgnoreFilters(unittest.TestCase):
    def test_should_ignore_dir(self):
        # Default ignored dirs
        self.assertTrue(scan_structure.should_ignore_dir(".git"))
        self.assertTrue(scan_structure.should_ignore_dir("node_modules"))
        self.assertTrue(scan_structure.should_ignore_dir("target"))
        self.assertTrue(scan_structure.should_ignore_dir("build"))
        self.assertTrue(scan_structure.should_ignore_dir(".turbo"))
        self.assertTrue(scan_structure.should_ignore_dir(".next"))
        self.assertTrue(scan_structure.should_ignore_dir("__pycache__"))

        # Hidden dirs except .agents
        self.assertTrue(scan_structure.should_ignore_dir(".custom_hidden"))
        self.assertFalse(scan_structure.should_ignore_dir(".agents"))

        # out dir handling
        self.assertTrue(scan_structure.should_ignore_dir("out"))
        self.assertFalse(scan_structure.should_ignore_dir("out", Path("/project/src/main/java/application/port/out")))
        self.assertFalse(scan_structure.should_ignore_dir("out", Path("/project/adapter/out/persistence")))

    def test_should_ignore_file(self):
        self.assertTrue(scan_structure.should_ignore_file(".DS_Store"))
        self.assertTrue(scan_structure.should_ignore_file("App.class"))
        self.assertTrue(scan_structure.should_ignore_file("lib.jar"))
        self.assertTrue(scan_structure.should_ignore_file("test.pyc"))
        self.assertTrue(scan_structure.should_ignore_file(".env"))
        self.assertFalse(scan_structure.should_ignore_file("User.java"))
        self.assertFalse(scan_structure.should_ignore_file("main.dart"))
        self.assertFalse(scan_structure.should_ignore_file("app.component.ts"))


class TestDetectStacks(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.workspace = Path(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_detect_generic_when_empty(self):
        stacks = scan_structure.detect_stacks(self.workspace)
        self.assertEqual(stacks, ["generic"])

    def test_detect_java_kotlin_root(self):
        (self.workspace / "pom.xml").touch()
        stacks = scan_structure.detect_stacks(self.workspace)
        self.assertIn("java-kotlin", stacks)

    def test_detect_flutter_root(self):
        (self.workspace / "pubspec.yaml").touch()
        stacks = scan_structure.detect_stacks(self.workspace)
        self.assertIn("flutter", stacks)

    def test_detect_angular_angular_json(self):
        (self.workspace / "angular.json").touch()
        stacks = scan_structure.detect_stacks(self.workspace)
        self.assertIn("angular", stacks)

    def test_detect_angular_package_json(self):
        pkg = self.workspace / "package.json"
        pkg.write_text(json.dumps({"dependencies": {"@angular/core": "^17.0.0"}}))
        stacks = scan_structure.detect_stacks(self.workspace)
        self.assertIn("angular", stacks)

    def test_detect_monorepo_subdirectories(self):
        backend = self.workspace / "backend"
        backend.mkdir()
        (backend / "build.gradle.kts").touch()

        frontend = self.workspace / "frontend"
        frontend.mkdir()
        (frontend / "angular.json").touch()

        stacks = scan_structure.detect_stacks(self.workspace)
        self.assertIn("java-kotlin", stacks)
        self.assertIn("angular", stacks)


class TestScanJavaKotlinHexagonal(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.workspace = Path(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_hexagonal_classification_singular_and_plural(self):
        pkg_base = self.workspace / "src" / "main" / "java" / "com" / "example"

        # Main application class
        pkg_base.mkdir(parents=True)
        (pkg_base / "DemoApplication.java").touch()

        # Domain with plural and singular
        models_dir = pkg_base / "domain" / "models"
        models_dir.mkdir(parents=True)
        (models_dir / "User.java").touch()

        ports_dir = pkg_base / "domain" / "ports"
        ports_dir.mkdir(parents=True)
        (ports_dir / "UserRepository.java").touch()

        events_dir = pkg_base / "domain" / "events"
        events_dir.mkdir(parents=True)
        (events_dir / "UserCreatedEvent.java").touch()

        exceptions_dir = pkg_base / "domain" / "exceptions"
        exceptions_dir.mkdir(parents=True)
        (exceptions_dir / "UserNotFoundException.java").touch()

        # Application with plural
        services_dir = pkg_base / "application" / "services"
        services_dir.mkdir(parents=True)
        (services_dir / "UserService.java").touch()

        usecases_dir = pkg_base / "application" / "usecases"
        usecases_dir.mkdir(parents=True)
        (usecases_dir / "CreateUserUseCase.java").touch()

        # Direct adapter layouts (e.g. adapter.rest and adapter.persistence)
        rest_dir = pkg_base / "adapter" / "rest"
        rest_dir.mkdir(parents=True)
        (rest_dir / "UserController.java").touch()

        persistence_dir = pkg_base / "adapter" / "persistence"
        persistence_dir.mkdir(parents=True)
        (persistence_dir / "UserJpaAdapter.java").touch()

        # Inbound/Outbound nested adapter layouts
        nested_in_dir = pkg_base / "adapter" / "in" / "messaging"
        nested_in_dir.mkdir(parents=True)
        (nested_in_dir / "UserKafkaConsumer.java").touch()

        # Config
        config_dir = pkg_base / "config"
        config_dir.mkdir(parents=True)
        (config_dir / "SecurityConfig.java").touch()

        res = scan_structure.scan_java_kotlin_hexagonal(self.workspace)
        mod = res["modules"]["root"]

        # Verify entry point
        self.assertIn("entryPoints", mod)
        self.assertTrue(any("DemoApplication.java" in f for f in mod["entryPoints"]))

        # Verify domain
        self.assertTrue(any("User.java" in f for f in mod["domain"]["models"]))
        self.assertTrue(any("UserRepository.java" in f for f in mod["domain"]["ports"]))
        self.assertTrue(any("UserCreatedEvent.java" in f for f in mod["domain"]["events"]))
        self.assertTrue(any("UserNotFoundException.java" in f for f in mod["domain"]["exceptions"]))

        # Verify application
        self.assertTrue(any("UserService.java" in f for f in mod["application"]["services"]))
        self.assertTrue(any("CreateUserUseCase.java" in f for f in mod["application"]["usecases"]))

        # Verify adapter inbound & outbound
        self.assertIn("rest", mod["adapter"]["inbound"])
        self.assertTrue(any("UserController.java" in f for f in mod["adapter"]["inbound"]["rest"]))

        self.assertIn("persistence", mod["adapter"]["outbound"])
        self.assertTrue(any("UserJpaAdapter.java" in f for f in mod["adapter"]["outbound"]["persistence"]))

        self.assertIn("messaging", mod["adapter"]["inbound"])
        self.assertTrue(any("UserKafkaConsumer.java" in f for f in mod["adapter"]["inbound"]["messaging"]))

        # Verify config
        self.assertTrue(any("SecurityConfig.java" in f for f in mod["config"]))


class TestScanFlutterFeatures(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.workspace = Path(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_flutter_feature_first_structure(self):
        lib = self.workspace / "lib"
        lib.mkdir()
        (lib / "main.dart").touch()

        # Core
        core_theme = lib / "core" / "theme"
        core_theme.mkdir(parents=True)
        (core_theme / "app_theme.dart").touch()
        (lib / "core" / "constants.dart").touch()

        # Features
        feat_auth = lib / "features" / "auth"
        (feat_auth / "presentation" / "pages").mkdir(parents=True)
        (feat_auth / "presentation" / "pages" / "login_page.dart").touch()

        (feat_auth / "domain" / "entities").mkdir(parents=True)
        (feat_auth / "domain" / "entities" / "user_entity.dart").touch()

        (feat_auth / "data" / "models").mkdir(parents=True)
        (feat_auth / "data" / "models" / "user_model.dart").touch()

        # Extra file in feature
        (feat_auth / "auth_barrel.dart").touch()

        res = scan_structure.scan_flutter_features(self.workspace)

        self.assertEqual(res["entryPoints"], ["lib/main.dart"])
        self.assertIn("theme", res["core"])
        self.assertIn("general", res["core"])
        self.assertTrue(any("constants.dart" in f for f in res["core"]["general"]))

        feat = res["features"]["auth"]
        self.assertTrue(any("login_page.dart" in f for f in feat["presentation"]))
        self.assertTrue(any("user_entity.dart" in f for f in feat["domain"]))
        self.assertTrue(any("user_model.dart" in f for f in feat["data"]))
        self.assertIn("other", feat)
        self.assertTrue(any("auth_barrel.dart" in f for f in feat["other"]))


class TestScanAngularFeatures(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.workspace = Path(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_angular_feature_first_structure(self):
        src = self.workspace / "src"
        app = src / "app"
        app.mkdir(parents=True)

        # Entry points
        (src / "main.ts").touch()
        (src / "index.html").touch()

        # Core & Shared
        (app / "core" / "services").mkdir(parents=True)
        (app / "core" / "services" / "auth.service.ts").touch()
        (app / "core" / "index.ts").touch()

        (app / "shared" / "components").mkdir(parents=True)
        (app / "shared" / "components" / "button.component.ts").touch()

        # Feature
        feat_orders = app / "features" / "orders"
        (feat_orders / "components").mkdir(parents=True)
        (feat_orders / "components" / "order-list.component.ts").touch()
        (feat_orders / "components" / "order-list.component.html").touch()
        (feat_orders / "components" / "order-list.component.scss").touch()

        (feat_orders / "services").mkdir(parents=True)
        (feat_orders / "services" / "order.service.ts").touch()

        (feat_orders / "store").mkdir(parents=True)
        (feat_orders / "store" / "orders.state.ts").touch()

        (feat_orders / "models").mkdir(parents=True)
        (feat_orders / "models" / "order.model.ts").touch()

        (feat_orders / "orders.routes.ts").touch()
        (feat_orders / "orders.guard.ts").touch()

        res = scan_structure.scan_angular_features(self.workspace)

        self.assertIn("src/main.ts", res["entryPoints"])
        self.assertIn("src/index.html", res["entryPoints"])
        self.assertIn("services", res["core"])
        self.assertIn("general", res["core"])
        self.assertIn("components", res["shared"])

        feat = res["features"]["orders"]
        # Verify scss is included in components
        self.assertTrue(any("order-list.component.scss" in f for f in feat["components"]))
        self.assertTrue(any("order-list.component.ts" in f for f in feat["components"]))
        self.assertTrue(any("order.service.ts" in f for f in feat["services"]))
        self.assertTrue(any("orders.state.ts" in f for f in feat["store"]))
        self.assertTrue(any("order.model.ts" in f for f in feat["models"]))
        self.assertTrue(any("orders.routes.ts" in f for f in feat["routes"]))
        self.assertIn("other", feat)
        self.assertTrue(any("orders.guard.ts" in f for f in feat["other"]))


class TestScanStandardsRepo(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.workspace = Path(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_standards_repo_frontmatter_extraction(self):
        rules_dir = self.workspace / "rules" / "test-stack"
        rules_dir.mkdir(parents=True)

        rule_file = rules_dir / "sample-rules.md"
        rule_file.write_text(
            """---
description: "Sample test standards description."
globs:
  - "**/*.sample"
  - "**/sample.config"
---

# Sample Rules
Rule body here.
"""
        )

        res = scan_structure.scan_standards_repo(self.workspace)
        self.assertEqual(res["architecture"], "standards-repository")
        self.assertIn("test-stack", res["stacks"])

        rule = res["stacks"]["test-stack"][0]
        self.assertEqual(rule["name"], "sample-rules")
        self.assertEqual(rule["description"], "Sample test standards description.")
        self.assertEqual(rule["globs"], ["**/*.sample", "**/sample.config"])


if __name__ == "__main__":
    unittest.main()
