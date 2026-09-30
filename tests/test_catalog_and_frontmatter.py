import json
from pathlib import Path
import pytest
import quartermaster


class TestFrontmatterAndManifest:
    def test_parse_skill_frontmatter_valid(self):
        content = (
            "---\n"
            "name: my-skill\n"
            "description: A description with colon: inside\n"
            "version: 1.2.3\n"
            "tags: [python, testing, cli]\n"
            "---\n"
            "# Markdown Content Here\n"
        )
        fm = quartermaster.parse_skill_frontmatter(content)
        assert fm["name"] == "my-skill"
        assert fm["description"] == "A description with colon: inside"
        assert fm["version"] == "1.2.3"
        assert fm["tags"] == ["python", "testing", "cli"]

    def test_parse_skill_frontmatter_no_frontmatter(self):
        content = "# Just plain markdown without frontmatter\n"
        fm = quartermaster.parse_skill_frontmatter(content)
        assert fm == {}

    def test_parse_skill_frontmatter_unclosed(self):
        content = "---\nname: unclosed-skill\n"
        fm = quartermaster.parse_skill_frontmatter(content)
        assert fm == {}

    def test_parse_plugin_manifest_valid(self, tmp_path):
        manifest_file = tmp_path / "plugin.json"
        manifest_file.write_text(json.dumps({
            "name": "sample-plugin",
            "version": "2.0.0",
            "description": "Sample plugin description",
            "skills": ["s1", "s2"],
        }))
        res = quartermaster.parse_plugin_manifest(str(manifest_file))
        assert res["name"] == "sample-plugin"
        assert res["version"] == "2.0.0"
        assert res["skills"] == ["s1", "s2"]

    def test_parse_plugin_manifest_invalid_json(self, tmp_path):
        manifest_file = tmp_path / "plugin.json"
        manifest_file.write_text("{invalid json here")
        res = quartermaster.parse_plugin_manifest(str(manifest_file))
        assert res == {}

    def test_parse_plugin_manifest_missing_file(self, tmp_path):
        manifest_file = tmp_path / "nonexistent.json"
        res = quartermaster.parse_plugin_manifest(str(manifest_file))
        assert res == {}


class TestCatalog:
    def test_get_catalog_empty_library(self, tmp_path):
        empty_lib = tmp_path / "empty-lib"
        empty_lib.mkdir()
        catalog = quartermaster.get_catalog(str(empty_lib))
        assert catalog["skills"] == []
        assert catalog["plugins"] == []
        assert catalog["library_path"] == str(empty_lib)

    def test_get_catalog_populated(self, sample_skills_library):
        catalog = quartermaster.get_catalog(str(sample_skills_library))
        assert len(catalog["skills"]) >= 3
        assert len(catalog["plugins"]) >= 2

        skill_names = [s["name"] for s in catalog["skills"]]
        assert "python-test" in skill_names
        assert "spec" in skill_names
        assert "docker-compose" in skill_names

        plugin_names = [p["name"] for p in catalog["plugins"]]
        assert "python-stack" in plugin_names
        assert "preflight" in plugin_names

        # Check core detection
        spec_skill = next(s for s in catalog["skills"] if s["name"] == "spec")
        assert spec_skill["tier"] == "core"

        docker_skill = next(s for s in catalog["skills"] if s["name"] == "docker-compose")
        assert docker_skill["tier"] == "stack"

        preflight_plugin = next(p for p in catalog["plugins"] if p["name"] == "preflight")
        assert preflight_plugin["tier"] == "core"
