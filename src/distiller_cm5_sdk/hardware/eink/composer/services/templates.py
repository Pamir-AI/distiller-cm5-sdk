"""Template management service for saving and loading compositions."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional


class TemplateService:
    """Service for managing composition templates."""

    def __init__(self, template_dir: str = "templates"):
        """Initialize template service."""
        self.template_dir = Path(template_dir)
        self.template_dir.mkdir(exist_ok=True)

    def save_template(
        self,
        name: str,
        composition: dict,
        description: str | None = None,
    ) -> bool:
        """Save a composition as a template."""
        try:
            # Create template directory
            template_path = self.template_dir / name
            template_path.mkdir(exist_ok=True)

            # Add metadata
            template_data = {
                "template_version": "1.0",
                "name": name,
                "description": description or "",
                "created": datetime.now().isoformat(),
                "width": composition.get("width", 250),
                "height": composition.get("height", 128),
                "layers": composition.get("layers", []),
            }

            # Save template JSON
            template_file = template_path / "template.json"
            with open(template_file, "w") as f:
                json.dump(template_data, f, indent=2)

            return True

        except Exception as e:
            print(f"Error saving template: {e}")
            return False

    def load_template(self, name: str) -> dict | None:
        """Load a template by name."""
        try:
            template_file = self.template_dir / name / "template.json"
            if not template_file.exists():
                return None

            with open(template_file) as f:
                return json.load(f)

        except Exception as e:
            print(f"Error loading template: {e}")
            return None

    def list_templates(self) -> list[dict[str, any]]:
        """List all available templates."""
        templates = []

        for template_dir in self.template_dir.iterdir():
            if template_dir.is_dir():
                template_file = template_dir / "template.json"
                if template_file.exists():
                    try:
                        with open(template_file) as f:
                            data = json.load(f)
                            templates.append(
                                {
                                    "name": data.get("name", template_dir.name),
                                    "description": data.get("description", ""),
                                    "created": data.get("created", ""),
                                    "layers_count": len(data.get("layers", [])),
                                    "width": data.get("width", 250),
                                    "height": data.get("height", 128),
                                }
                            )
                    except Exception:
                        pass

        return sorted(templates, key=lambda x: x.get("created", ""), reverse=True)

    def delete_template(self, name: str) -> bool:
        """Delete a template."""
        try:
            template_path = self.template_dir / name
            if template_path.exists() and template_path.is_dir():
                # Remove all files in template directory
                for file in template_path.iterdir():
                    file.unlink()
                template_path.rmdir()
                return True
            return False

        except Exception as e:
            print(f"Error deleting template: {e}")
            return False

    def export_template(self, name: str) -> str | None:
        """Export template as JSON string."""
        template = self.load_template(name)
        if template:
            return json.dumps(template, indent=2)
        return None

    def import_template(self, json_str: str, name: str | None = None) -> bool:
        """Import template from JSON string."""
        try:
            data = json.loads(json_str)
            template_name = name or data.get("name", f"imported_{datetime.now().timestamp()}")

            # Save as new template
            return self.save_template(
                template_name,
                {
                    "width": data.get("width", 250),
                    "height": data.get("height", 128),
                    "layers": data.get("layers", []),
                },
                description=data.get("description", "Imported template"),
            )

        except Exception as e:
            print(f"Error importing template: {e}")
            return False
