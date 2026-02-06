# Copyright 2026 Steve Bula @ pitBula
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from pathlib import Path
from typing import Any, Dict, Union

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
        loader=jinja2.FileSystemLoader(str(template_path.parent)), autoescape=False
    )
    tpl = env.get_template(template_path.name)
    return tpl.render(**context)
