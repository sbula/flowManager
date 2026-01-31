from pathlib import Path
from typing import Dict, Any, Union
import jinja2

def render_string(template_string: str, context: Dict[str, Any]) -> str:
    """Renders a Jinja2 template string."""
    env = jinja2.Environment(autoescape=False)
    tpl = env.from_string(template_string)
    return tpl.render(**context)

def render_file(template_path: Path, context: Dict[str, Any]) -> str:
    """Renders a Jinja2 template file."""
    # We use FileSystemLoader to support inheritance if needed, 
    # but for simple atom we can just read text if we want isolation.
    # To support Extends/Include, we need a Loader.
    
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(template_path.parent)),
        autoescape=False
    )
    tpl = env.get_template(template_path.name)
    return tpl.render(**context)
