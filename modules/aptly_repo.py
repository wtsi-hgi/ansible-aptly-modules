#!/usr/bin/env python3

from ansible.module_utils.basic import AnsibleModule
import subprocess

REPO_NAME_PARAMETER_NAME = "name"
OPTIONS_PARAMETER_NAME = "options"
APTLY_BINARY_PARAMETER_NAME = "aptly_binary"

BYTE_STRING_ENCODING = "utf-8"
DEFAULT_APTLY_BINARY_LOCATION = "/usr/bin/aptly"

REPO_OPTIONS = {
    "comment": ("Comment", ""),
    "component": ("Default Distribution", "main"),
    "distribution": ("Default Component", "")
}


class RepositoryDoesNotExistError(RuntimeError):
    def __init__(self, repo_name):
        super().__init__("Repository \"%s\" does not exist" % (repo_name, ))


class InvalidRepositoryOptionsError(RuntimeError):
    def __init__(self, invalid_options):
        super().__init__("Invalid repository options: %s" % (invalid_options, ))
        self.invalid_options = invalid_options


def create_aptly_repo(repo_name, options, aptly_binary_location):
    option_pairs = _prepare_options(options)
    subprocess.run([aptly_binary_location, "repo", "create"] + option_pairs + [repo_name], check=True)
    assert does_aptly_repo_exist(repo_name, aptly_binary_location)


def edit_aptly_repo(repo_name, options, aptly_binary_location):
    if not does_aptly_repo_exist(repo_name, aptly_binary_location):
        raise RepositoryDoesNotExistError(repo_name)
    option_pairs = _prepare_options(options)
    subprocess.run([aptly_binary_location, "repo", "edit"] + option_pairs + [repo_name], check=True)


def _prepare_options(options):
    options = {"-%s" % key: value for key, value in options.items() if not key.startswith("-")}
    return ["%s=%s" % (key, value) for key, value in options.items()]


def does_aptly_repo_exist(repo_name, aptly_binary_location):
    list_process = subprocess.run([aptly_binary_location, "repo", "list"], check=True, stdout=subprocess.PIPE)
    return "[%s]" % repo_name in list_process.stdout.decode(BYTE_STRING_ENCODING)


def get_aptly_repo_option_values(repo_name, aptly_binary_location):
    if not does_aptly_repo_exist(repo_name, aptly_binary_location):
        raise RepositoryDoesNotExistError(repo_name)
    show_process = subprocess.run([aptly_binary_location, "repo", "show", repo_name], check=True,
                                  stdout=subprocess.PIPE)

    options = {}
    key_lookup = {value[0]: key for value, key in REPO_OPTIONS.items()}
    for line in show_process.stdout.decode(BYTE_STRING_ENCODING).split("\n"):
        if line.strip() == "":
            break
        key, value = line.split(":")
        if key in key_lookup:
            options[key_lookup[key]] = value.strip()
    assert validate_options(options) is None
    return options


def validate_options(options):
    invalid_keys = {key for key in options.keys() if key not in REPO_OPTIONS}
    if len(invalid_keys) > 0:
        raise InvalidRepositoryOptionsError(invalid_keys)


def main():
    module = AnsibleModule(
        argument_spec={
            REPO_NAME_PARAMETER_NAME: dict(type="str", required=True),
            OPTIONS_PARAMETER_NAME: dict(type="dict", default={}),
            APTLY_BINARY_PARAMETER_NAME: dict(type="str", default=DEFAULT_APTLY_BINARY_LOCATION)
        },
        supports_check_mode=True
    )

    repo_name = module.params[REPO_NAME_PARAMETER_NAME]
    options = {**{key: value[1] for key, value in REPO_OPTIONS.items()}, **module.params[OPTIONS_PARAMETER_NAME]}
    aptly_binary_location = module.params[APTLY_BINARY_PARAMETER_NAME]

    validate_options(options)

    changed = False
    if not does_aptly_repo_exist(repo_name, aptly_binary_location):
        create_aptly_repo(repo_name, options, aptly_binary_location)
        changed = True
    else:
        existing_options = get_aptly_repo_option_values(repo_name, aptly_binary_location)
        if existing_options != options:
            edit_aptly_repo(repo_name, options, aptly_binary_location)
            changed = True

    module.exit_json(changed=changed, options=options)


if __name__ == "__main__":
    main()
