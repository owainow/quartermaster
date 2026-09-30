import pytest
import quartermaster


class TestFormatters:
    def test_format_catalog_text_populated(self):
        catalog = {
            "library_path": "/path/to/lib",
            "total_packages": 1,
            "total_plugins": 1,
            "total_skills": 1,
            "packages": {
                "python-stack": {
                    "is_plugin": True,
                    "plugin_info": {
                        "description": "Python bundle",
                        "components": ["skills", "rules"],
                    },
                    "skills": [
                        {
                            "name": "python-test",
                            "description": "Testing tools",
                            "tier": "stack",
                        }
                    ],
                }
            },
        }
        text = quartermaster.format_catalog_text(catalog)
        assert "QUARTERMASTER ARMORY CATALOG" in text
        assert "python-stack" in text
        assert "python-test" in text
        assert "[PLUGIN]" in text

    def test_format_catalog_text_empty(self):
        catalog = {
            "library_path": "/path/to/lib",
            "total_packages": 0,
            "total_plugins": 0,
            "total_skills": 0,
            "packages": {},
        }
        text = quartermaster.format_catalog_text(catalog)
        assert "QUARTERMASTER ARMORY CATALOG" in text

    def test_format_scan_text(self):
        scan_data = {
            "project_path": "/path/to/proj",
            "status": "active_project",
            "is_brand_new": True,
            "scoping_dialogue": {
                "prompt": "What are you building?",
                "options": [{"label": "Web App"}],
                "recommendation_on_unclear": "Equip core capabilities",
            },
            "manifests_found": ["pyproject.toml"],
            "technologies": [
                {"name": "Python Environment", "manifest": "pyproject.toml", "details": "FastAPI"}
            ],
            "recommended_plugins": [
                {"name": "python-stack", "reason": "Python framework"}
            ],
            "recommended_skills": [
                {"name": "python-test", "package": "python-stack", "tier": "stack", "priority": "High", "reason": "Testing"}
            ],
        }
        text = quartermaster.format_scan_text(scan_data)
        assert "QUARTERMASTER RECONNAISSANCE REPORT" in text
        assert "BRAND-NEW" in text
        assert "pyproject.toml" in text
        assert "Python Environment" in text
        assert "python-stack" in text
        assert "python-test" in text

    def test_format_provision_text(self):
        prov_data = {
            "project_path": "/path/to/proj",
            "provisioned_count": 1,
            "provisioned": [
                {
                    "name": "python-test",
                    "type": "skill",
                    "files_copied": 3,
                    "destination": "/path/to/proj/.agents/skills/python-test",
                }
            ],
            "not_found": ["unknown-skill"],
        }
        text = quartermaster.format_provision_text(prov_data)
        assert "QUARTERMASTER OUTFITTING REPORT" in text
        assert "python-test" in text
        assert "unknown-skill" in text

    def test_format_sweep_text(self):
        sweep_data = {
            "project_path": "/path/to/proj",
            "library_path": "/path/to/lib",
            "harness": "claude",
            "pruning_mode": "aggressive",
            "installed_plugins": [{"name": "plugin-1"}],
            "installed_skills": [{"name": "skill-1"}],
            "provisioned_additions": [
                {"name": "new-tool", "type": "skill", "destination": "/p/new-tool"}
            ],
            "pruning_candidates": [
                {"name": "old-tool", "type": "skill", "reason": "No longer needed"}
            ],
            "pruned_items": [
                {"name": "pruned-tool", "type": "skill", "reason": "Obsolescence"}
            ],
        }
        text = quartermaster.format_sweep_text(sweep_data)
        assert "QUARTERMASTER SWEEP AUDIT REPORT" in text
        assert "plugin-1" in text
        assert "skill-1" in text
        assert "new-tool" in text
        assert "pruned-tool" in text

    def test_format_import_text(self):
        res_installed = {
            "status": "installed",
            "name": "my-tool",
            "is_plugin": False,
            "destination": "/lib/my-tool",
            "skills_count": 1,
            "target_skill": "my-tool",
            "is_core": True,
            "project_path": "/path/to/proj",
            "project_provisioned": [
                {"type": "skill", "name": "my-tool", "destination": "/p/my-tool"}
            ],
        }
        text = quartermaster.format_import_text(res_installed)
        assert "Central Armory: Installed" in text
        assert "my-tool" in text
        assert "Designated as Core" in text

        res_exists = {
            "status": "exists",
            "name": "my-tool",
            "is_plugin": True,
            "destination": "/lib/my-tool",
            "skills_count": 2,
        }
        assert "already exists in library" in quartermaster.format_import_text(res_exists)

        res_error = {"status": "error", "error": "Git clone failed"}
        assert "Error: Git clone failed" in quartermaster.format_import_text(res_error)

    def test_format_core_helpers(self):
        list_data = {
            "library_path": "/path/to/lib",
            "project_path": "/path/to/proj",
            "total_core": 1,
            "core_capabilities": [
                {
                    "name": "spec",
                    "type": "skill",
                    "in_library": True,
                    "in_workspace": True,
                }
            ],
        }
        text_list = quartermaster.format_core_list(list_data)
        assert "QUARTERMASTER CORE CAPABILITIES REPORT" in text_list
        assert "spec" in text_list
        assert "Library + Project" in text_list

        add_data = {
            "message": "Designated 'spec' as Core",
            "marked_paths": ["/path/to/spec/.core"],
        }
        assert "Designated 'spec' as Core" in quartermaster.format_core_add(add_data)

        rm_data = {
            "message": "Removed Core designation from 'spec'",
            "unmarked_paths": ["/path/to/spec/.core"],
        }
        assert "Removed Core designation" in quartermaster.format_core_rm(rm_data)
