"""
Generate a GitHub Actions reusable workflow to wrap a Python script.
"""
import argparse
import ast
import os
import sys

from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import LiteralScalarString


def extract_add_argument_calls(module_path: str):
    """
    Extract calls to functions named add_argument in the given file
    """
    obj_names = set()
    with open(module_path, "r") as f:
        tree = ast.parse(f.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'add_argument':
            obj_str = ast.unparse(node.func.value)
            obj_names.add(obj_str)
            yield node
            data = {
              'args': [ast.unparse(j) for j in node.args],
              'kwargs': {j.arg:ast.unparse(j.value) for j in node.keywords}}

    num_obj = len(obj_names)
    if num_obj == 0:
        raise ValueError("Found 0 add_argument calls")
    elif num_obj > 1:
        raise ValueError(f"Found add_argument_calls on multiple objects: {', '.join(sorted(obj_names))}")


def extract_args(script_path):
    """
    Extract data about calls to add_argument in the given file

    :return: generator of tuple of (input_type, name, description, flag, required)
    """

    add_argument_calls = extract_add_argument_calls(script_path)

    for call in add_argument_calls:
        args = call.args
        keywords = call.keywords

        name = None
        description = None
        is_positional = None
        option_strings = []
        flag = None
        action_type = "store"

        for arg in args:
            value = arg.value
            if isinstance(arg, ast.Constant) and isinstance(value, str):
                if value[0] == "-":
                    # flag
                    option_strings.append(value)
                    is_positional = False
                else:
                    # positional args can only have one name
                    assert len(args) == 1
                    name = value
                    is_positional = True
            else:
                print([ast.unparse(a) for a in args])
                raise ValueError(f"Unable to parse non-string add_argument arg")

        if is_positional is None:
            print([ast.unparse(a) for a in args])
            raise ValueError("Unable to identify whether this add_argument call was positional or optional")

        # positional args are required by default
        required = is_positional

        for keyword in keywords:
            if keyword.arg == "dest":
                if isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
                    name = keyword.value.value
            elif keyword.arg == "help":
                if isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
                    description = keyword.value.value
            elif keyword.arg == "required":
                if isinstance(keyword.value, ast.Constant):
                    required = keyword.value.value
            elif keyword.arg == "action":
                if isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
                    action_type = keyword.value.value
            else:
                # TODO handle mapping type=int to input_type number
                print(f"Ignoring add_argument kwarg {keyword.arg}")

        if not is_positional:
            # conventionally positional flags are short then long, so use last
            flag = option_strings[-1]

            if not name:
                # derive name from flag
                name = flag.lstrip('-').replace('-', '_')

        if action_type == "store":
            input_type = 'string'
            if is_positional and not required:
                print([ast.unparse(a) for a in args])
                raise NotImplementedError("Optional positional arguments not supported, change it to a flag.")
        elif action_type == "store_true":
            input_type = 'boolean'
        else:
            if action_type != "help":
                print(f"Skipping unknown action {action_type}")
            continue

        yield input_type, name, description, flag, required


def generate_workflow(script_path):
    """
    Analyze the argument parser of the given Python script
    and generate a GitHub Actions reusable workflow to call it
    """

    cmd_parts = [".venv/bin/python3", script_path]
    optional_arg_lines = []
    workflow_inputs = {}
    for input_type, name, description, flag, required in extract_args(script_path):
        if input_type == 'string':
            if flag is None:
                # Positional
                if not required:
                    raise NotImplementedError("Optional positional arguments not supported, change it to a flag.")
                cmd_parts.append('${{ inputs.%s }}' % name)
            else:
                # Flag
                optional_arg_lines.extend([
                    'if [[ "${{ inputs.%s }}" ]]; then' % name,
                    '  cmd+=(%s)' % flag,
                    '  cmd+=("${{ inputs.%s }}")' % name,
                    'fi',
                ])
        elif input_type == 'boolean':
            optional_arg_lines.extend([
                'if [[ "${{ inputs.%s }}" ]]; then' % name,
                '  cmd+=(%s)' % flag,
                'fi',
            ])
        else:
            raise NotImplementedError(f"No handling for input_type {input_type}")
        workflow_inputs[name] = {
            'description': description,
            'required': required,
            'type': input_type,
        }

    run_cmd_lines = [
        f'cmd=({" ".join(cmd_parts)})',
        *optional_arg_lines,
        'echo "[DEBUG]" "${cmd[@]}"',
        '"${cmd[@]}"',
    ]
    run_cmd = LiteralScalarString('\n'.join(run_cmd_lines))
    workflow_name = f'Run {os.path.basename(script_path)}'
    run_name = workflow_name
    if "dry_run" in workflow_inputs:
        run_name += " ${{ inputs.dry_run && '(dry-run)' || '' }}"
    workflow = {
        'name': workflow_name,
        'run-name': run_name,
        # TODO could add optional workflow_dispatch and/or wrapper workflow_dispatch
        'on': {'workflow_call': {'inputs': workflow_inputs}},
        'jobs': {
            'run-script': {
                'runs-on': 'ubuntu-latest',
                'steps': [
                    {
                        'uses': 'actions/checkout@v4'
                    },
                    {
                        'name': 'Set up Python',
                        'uses': 'actions/setup-python@v5',
                        'with': {
                            'python-version': sys.version.split()[0],
                            'cache': 'pip'
                        }
                    },
                    {
                        'name': 'Install dependencies',
                        'run': LiteralScalarString('python3 -m venv .venv\n.venv/bin/python3 -m pip install -r requirements.txt')
                    },
                    {
                        'name': 'Run script',
                        'run': run_cmd
                    }
                ]
            }
        }
    }

    return workflow

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("script_path", help="Path to the python script.")
    args = parser.parse_args()

    workflow = generate_workflow(args.script_path)

    yaml = YAML(typ="rt")
    yaml.default_flow_style = False
    yaml.indent(mapping=2, sequence=4, offset=2)
    with open('generated_workflow.yml', 'w') as f:
        yaml.dump(workflow, f)
