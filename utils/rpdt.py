import pathlib
import sys

if sys.version_info[0] < 3 or (sys.version_info[0] == 3 and sys.version_info[1] < 8):
    print('ERROR: This script requires Python 3.8 or higher')
    sys.exit(1)

import os
from pathlib import Path
import urllib.request
import urllib.error
import json
from argparse import ArgumentParser

os.chdir(Path(__file__).parents[1].absolute())
sys.path.insert(0, os.path.abspath("schema/six"))
sys.path.insert(0, os.path.abspath("schema/"))
import jsonschema

schema_json_path = "schema/workflow_schema_v2_5.schema.json"

# ################################ #
# RapidCompact.Cloud API endpoints #
# ################################ #

LOGIN_ENDPOINT = "login"
CONVERT_ENDPOINT = "preset/rpdx"


# ################################ #
#         Helper Functions         #
# ################################ #


def execute_server_request(request):
    try:
        response = urllib.request.urlopen(request)
    except urllib.error.URLError as e:
        print("******************************************************")
        if hasattr(e, "reason"):
            print("ERROR: Failed to fulfill the request.")
            print("Reason: ", e.reason)
        elif hasattr(e, "code"):
            print("ERROR: The server couldn't fulfill the request.")
            print("Error code: ", e.code)
        if hasattr(e, "readlines"):
            try:
                error_lines = e.readlines()
                try:
                    server_errors = json.loads(error_lines[0].decode("utf-8"))
                    print("Server message: \"" + server_errors["message"] + "\"")
                    print("Reported Errors:")
                    print(json.dumps(server_errors["errors"], indent=2))
                except json.JSONDecodeError:
                    # json parsing doesn't work - just try to print the string then
                    print("Server message: \"")
                    for errLine in error_lines:
                        print(errLine.decode("utf-8"))
            except:
                # we don't know how to parse the content
                print(e.readlines())
        print("******************************************************")

        return None, e.code if hasattr(e, "code") else None

    return response, response.getcode()


def validate_json_with_api_schema(variant_config, schema_file, silent):
    try:
        with open(schema_file) as file:
            schema = json.load(file)
    except (OSError, json.JSONDecodeError):
        if not silent:
            print(
                "Error: Unable to validate configuration against schema: schema couldn't be read from file \""
                + schema_file + "\".")
        return False

    try:
        jsonschema.validate(variant_config, schema)
        if not silent:
            print("Variant configuration passed validation.")
        return True
    except Exception as e:
        if not silent:
            print("Error: Variant configuration is not valid - see JSON validation report on how to fix this:")
            print("********************************************************************************")
            print(e)
            print("********************************************************************************")

    return False


def convert_json_schema_to_cli(auth_token, preset, download_path):
    headers = {'Authorization': 'Bearer ' + auth_token, 'Content-Type': 'application/json'}
    url = base_url + CONVERT_ENDPOINT
    data = json.dumps(preset).encode("utf8")

    req = urllib.request.Request(url, method='POST', headers=headers, data=data)
    response, code = execute_server_request(req)

    if response is None or code != 200:
        print("Could not convert to CLI preset.")
        return False
    else:
        try:
            with open(download_path, 'wb') as f:
                f.write(response.read())
            print('Success: CLI Preset written to "' + str(download_path) + '"')
            return True
        except OSError:
            print("Error: Cannot write to output file \"" + str(download_path) + "\".")
            return False


parser = ArgumentParser()
parser.add_argument("-b", "--base-url", dest="baseUrl", default="https://api.rapidcompact.com/api/",
                    help="api base url")
parser.add_argument("-c", "--credentials-file", dest="credentialsFile", default="credentials.json",
                    help="credentials JSON file")
parser.add_argument("-v", "--variants-file", dest="variantsFile", default="variants.json",
                    help="variant definitions JSON file")
parser.add_argument("-e", "--exit", dest="exitOnError", default=False,
                    help="exit script on optimize error. Set False or True")

parser.set_defaults(cleanup=True)

pArgs = parser.parse_args()
argsDict = vars(pArgs)

variants_file = argsDict["variantsFile"]
credentials_file = argsDict["credentialsFile"]
base_url = argsDict["baseUrl"]
cleanup = argsDict["cleanup"]
exit_on_error = argsDict["exitOnError"]

print("API Endpoint: " + base_url)

user_credentials = None
user_variants = None

try:
    with open(credentials_file) as f:
        user_credentials = json.load(f)
except (OSError, json.JSONDecodeError):
    print(
        "Unable to load and parse credentials JSON file \"" + credentials_file + "\". Make sure the file exists and is "
                                                                                 "valid JSON.")
    sys.exit(1)

try:
    with open(variants_file) as f:
        user_variants = json.load(f)
except(OSError, json.JSONDecodeError):
    print(
        "Unable to load and parse variant definitions JSON file \"" + variants_file + "\". Make sure the file exists "
                                                                                      "and is valid JSON.")
    sys.exit(1)

# obtain token from credentials file
access_token = user_credentials["token"]
if access_token == "":
    print("Couldn't log in. Are your credentials valid?")
    sys.exit(1)

# check if output folder exists
if not os.path.isdir("output"):
    os.mkdir("output")

# validate before uploading, to prevent unnecessary waiting and traffic
for variantName in user_variants["variants"]:
    variant = user_variants["variants"][variantName]

    print("Validating configuration for variant \"" + variantName + "\".")

    if validate_json_with_api_schema(variant["config"], schema_json_path, False):
        download_target = pathlib.Path('output/' + variantName + '.zip').absolute()
        if not convert_json_schema_to_cli(access_token, variant, download_target) and exit_on_error:
            print("Exiting with error because of failed variants conversion")
            sys.exit(1)
