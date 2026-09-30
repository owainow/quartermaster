import json
from pathlib import Path
import pytest
import quartermaster


class TestDetectStack:
    def test_detect_python_project(self, tmp_path, sample_skills_library):
        proj = tmp_path / "py-proj"
        proj.mkdir()
        (proj / "pyproject.toml").write_text("[project]\nname = 'demo'\ndependencies = ['fastapi', 'flask', 'django', 'antigravity']\n")
        (proj / "requirements.txt").write_text("fastapi>=0.100\npytest>=8.0\n")

        res = quartermaster.detect_stack(str(proj), library_path=str(sample_skills_library))
        assert res["status"] == "active_project"
        tech_names = [t["name"].lower() for t in res["technologies"]]
        assert any("python" in name for name in tech_names)
        details = " ".join(t["details"].lower() for t in res["technologies"])
        assert "fastapi" in details
        assert "flask" in details
        assert "django" in details

        # python-stack plugin recommended from library
        rec_plugin_names = [p["name"] for p in res["recommended_plugins"]]
        assert "python-stack" in rec_plugin_names

    def test_detect_node_project(self, tmp_path):
        proj = tmp_path / "node-proj"
        proj.mkdir()
        (proj / "package.json").write_text(json.dumps({
            "name": "node-app",
            "dependencies": {
                "react": "^18.0.0",
                "next": "^14.0.0",
                "vue": "^3.0.0",
                "svelte": "^4.0.0",
                "tailwind": "^3.0.0",
                "vite": "^5.0.0",
                "express": "^4.0.0",
                "fastify": "^4.0.0",
            },
        }))
        (proj / "tsconfig.json").write_text("{}")

        res = quartermaster.detect_stack(str(proj))
        tech_names = [t["name"].lower() for t in res["technologies"]]
        assert any("web & node.js" in name for name in tech_names)
        details = " ".join(t["details"].lower() for t in res["technologies"])
        assert "react" in details
        assert "next.js" in details
        assert "typescript" in details
        assert "vue" in details
        assert "fastify" in details

    def test_detect_static_web_html(self, tmp_path):
        proj = tmp_path / "static-web"
        proj.mkdir()
        (proj / "index.html").write_text("<!DOCTYPE html><html><body><h1>Hello</h1></body></html>")

        res = quartermaster.detect_stack(str(proj))
        tech_names = [t["name"].lower() for t in res["technologies"]]
        assert any("static web" in name for name in tech_names)

    def test_detect_android_gradle(self, tmp_path):
        proj = tmp_path / "android-proj"
        proj.mkdir()
        (proj / "build.gradle.kts").write_text('plugins { id("com.android.application") }\n')

        res = quartermaster.detect_stack(str(proj))
        tech_names = [t["name"].lower() for t in res["technologies"]]
        assert any("android" in name for name in tech_names)

    def test_detect_chrome_extension(self, tmp_path):
        proj = tmp_path / "ext-proj"
        proj.mkdir()
        (proj / "manifest.json").write_text('{"manifest_version": 3, "name": "MyExt"}')

        res = quartermaster.detect_stack(str(proj))
        tech_names = [t["name"].lower() for t in res["technologies"]]
        assert any("chrome extension" in name for name in tech_names)

    def test_detect_firebase_platform(self, tmp_path):
        proj = tmp_path / "fb-proj"
        proj.mkdir()
        (proj / "firebase.json").write_text('{"hosting": {}}')

        res = quartermaster.detect_stack(str(proj))
        tech_names = [t["name"].lower() for t in res["technologies"]]
        assert any("firebase" in name for name in tech_names)

    def test_detect_container_and_infra(self, tmp_path):
        proj = tmp_path / "infra-proj"
        proj.mkdir()
        (proj / "Dockerfile").write_text("FROM alpine:latest\n")
        (proj / "docker-compose.yml").write_text("version: '3.8'\nservices:\n  web:\n    image: nginx\n")

        res = quartermaster.detect_stack(str(proj))
        tech_names = [t["name"].lower() for t in res["technologies"]]
        assert any("containerization" in name or "docker" in name for name in tech_names)

    def test_detect_flutter_and_dart(self, tmp_path):
        proj = tmp_path / "flutter-proj"
        proj.mkdir()
        (proj / "pubspec.yaml").write_text(
            "name: flutter_app\n"
            "dependencies:\n"
            "  flutter:\n"
            "    sdk: flutter\n"
            "  http: ^1.0.0\n"
            "  json_serializable: ^6.0.0\n"
            "  go_router: ^12.0.0\n"
        )
        res = quartermaster.detect_stack(str(proj))
        tech_names = [t["name"].lower() for t in res["technologies"]]
        assert any("flutter" in name or "dart" in name for name in tech_names)
        details = " ".join(t["details"].lower() for t in res["technologies"])
        assert "flutter sdk" in details

    def test_detect_brand_new_project_scoping(self, tmp_path, sample_skills_library):
        empty = tmp_path / "brand-new"
        empty.mkdir()
        res = quartermaster.detect_stack(str(empty), library_path=str(sample_skills_library))
        assert res["is_brand_new"] is True
        assert res["status"] == "unscoped_new_project"
        assert "scoping_dialogue" in res
        assert len(res["scoping_dialogue"]["options"]) > 0
        assert len(res["recommended_skills"]) > 0
        rec_skill_names = [s["name"] for s in res["recommended_skills"]]
        assert "spec" in rec_skill_names

    def test_detect_stack_with_library_matching(self, tmp_path, sample_skills_library):
        proj = tmp_path / "matching-proj"
        proj.mkdir()
        (proj / "Dockerfile").write_text("FROM python:3.11\n")
        (proj / "pyproject.toml").write_text("[project]\nname = 'test'\n")

        res = quartermaster.detect_stack(str(proj), library_path=str(sample_skills_library))
        assert res["status"] == "active_project"
        assert len(res["technologies"]) > 0
        rec_names = [s["name"] for s in res["recommended_skills"]]
        assert "spec" in rec_names  # core from library
