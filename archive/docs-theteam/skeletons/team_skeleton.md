# Team Codebase Skeletons
> Use this for low-token code understanding. Prefer over reading full files.

### File: /Users/bparlan/devcode/team/__init__.py
import os
import sys
import json
import yaml
from pathlib import Path
from bin.theteam_config import validate_config, cmd_init, cmd_validate, cmd_roster
def load_config(project_root):
def main(project_root=None):
def run_discussion(project_root, topic):

### File: /Users/bparlan/devcode/team/README.md
from the template — the default 3-persona roster in

### File: /Users/bparlan/devcode/team/SKILL.md
from the template — the default 3-persona roster in

### File: /Users/bparlan/devcode/team/Scientific and Theoretical Foundation.md
import json, glob, os

### File: /Users/bparlan/devcode/team/bin/theteam_config.py
import sys
import os
import json
import yaml
class ConfigError(Exception):
def _require(condition, message):
def _fatal(code, message):
def _load_yaml(path):
def load_raw(path):
def validate_config(data):
def cmd_validate(args):
def cmd_roster(args):
def cmd_init(args):
def main():

### File: /Users/bparlan/devcode/team/bin/theteam_report.py
import sys
import os
import json
import glob
from datetime import datetime, timezone
def _fatal(code, message):
def load_notes(notes_dir):
def load_synthesis(path):
def render(topic, project, notes, synthesis):
def cmd_build(args):
def main():

### File: /Users/bparlan/devcode/team/theteam/__init__.py
import os
import sys
import json
import yaml
from pathlib import Path
from bin.theteam_config import validate_config, cmd_init, cmd_validate, cmd_roster
def load_config(project_root):
def main(project_root=None):
def run_discussion(project_root, topic):

### File: /Users/bparlan/devcode/team/theteam/README.md
from the template — the default 3-persona roster in

### File: /Users/bparlan/devcode/team/theteam/SKILL.md
from the template — the default 3-persona roster in

### File: /Users/bparlan/devcode/team/theteam/bin/theteam_config.py
import sys
import os
import json
import yaml
class ConfigError(Exception):
def _require(condition, message):
def _fatal(code, message):
def _load_yaml(path):
def load_raw(path):
def validate_config(data):
def cmd_validate(args):
def cmd_roster(args):
def cmd_init(args):
def main():

### File: /Users/bparlan/devcode/team/theteam/bin/theteam_report.py
import sys
import os
import json
import glob
from datetime import datetime, timezone
def _fatal(code, message):
def load_notes(notes_dir):
def load_synthesis(path):
def render(topic, project, notes, synthesis):
def cmd_build(args):
def main():

