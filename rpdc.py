# check python version, this script requires python3
import sys
if sys.version_info[0] < 3 or (sys.version_info[0] == 3 and sys.version_info[1] < 8):
    print('ERROR: This script requires Python 3.8 or higher')
    sys.exit(1)

import urllib.request
import urllib.error

import os
import json
import time
from argparse import ArgumentParser


# add the six and jsonschema packages (locally, so users don't have to know pip etc.)
sys.path.insert(0, os.path.abspath("schema/six"))
sys.path.insert(0, os.path.abspath("schema/"))
import jsonschema


SchemaJSONPath = "schema/workflow_schema_v2_5.schema.json"


# ################################ #
# RapidCompact.Cloud API endpoints #
# ################################ #


LOGIN_ENDPOINT             = "login"
PRESIGNED_FETCH_ENDPOINT   = "rawmodel/api-upload/start"
FINALIZE_RAWMODEL_ENDPOINT = "rawmodel/{id}/api-upload/complete"
OPTIMIZE_MODEL_ENDPOINT    = "rawmodel/optimize/{id}"
BASE_ASSET_ENDPOINT        = "rawmodel/{id}"
RAPID_MODEL_ENDPOINT       = "rapidmodel/{id}"


# ################################ #
#         Helper Functions         #
# ################################ #

def executeServerRequest(request):
    try:
        response = urllib.request.urlopen(request)
    except urllib.error.URLError as e:
        print("******************************************************")
        if hasattr(e, "reason"):
            print("ERROR: Failed to fulfill the request.")
            print("Error code: ", e.code)
            print("Reason: ", e.reason)
        elif hasattr(e, "code"):
            print("ERROR: The server couldn't fulfill the request.")
            print("Error code: ", e.code)
        try:
            errorLines = e.readlines()
            try:
                serverErrors = json.loads(errorLines[0].decode("utf-8"))
                print("Server message: \"" + serverErrors["message"] + "\"")
                print("Reported Errors:")
                print(json.dumps(serverErrors["errors"], indent=2))
            except:
                # json parsing doesn't work - just try to print the string then
                print("Server message: \"")
                for errLine in errorLines:
                    print(errLine.decode("utf-8"))
        except:
            # we don't know how to parse the content
            print(e.readlines())
        print("******************************************************")

        return None, e.code

    return response, response.getcode()

# #############################################################################

def getServerRequestJSON(request):
    response, code = executeServerRequest(request)

    if not response:
        return None, code

    res = response.read().decode("utf8")
    try:
        rJSON = json.loads(res)
    except:
        print("ERROR: Could not parse the result from server.")

    return rJSON, response.getcode()

# #############################################################################

def downloadFile(fileURL, outputFilePath):
    req = urllib.request.Request(fileURL)
    response, code = executeServerRequest(req)
    if not response:
        print("Error: No data received to write output file \"" + outputFilePath + "\".")
        return False
    try:
        with open(outputFilePath, 'wb') as f:
            f.write(response.read())
    except:
       print("Error: Cannot write to output file \"" + outputFilePath + "\".")
       return False

    return True

# #############################################################################

def getUploadURLs(fileExt, accessToken, modelLabel, baseUrl):
    reqHeaders = {'Authorization' : 'Bearer ' + accessToken,
                  'content-type' : 'application/json'}

    payload = {"filenames": ["rapid" + fileExt],"model_name": modelLabel}
    data = json.dumps(payload).encode("utf8")
    print("Obtaining Signed Upload URLs ...")
    req = urllib.request.Request(baseUrl+PRESIGNED_FETCH_ENDPOINT, data, headers=reqHeaders)
    responseJSON, code = getServerRequestJSON(req)
    return responseJSON

# #############################################################################

def uploadRawModel(modelFile, fileExt, uploadURLs, accessToken, baseUrl):
    dataModel = None

    try:
       dataModel = open(modelFile, 'rb')
    except IOError:
       print("Error: cannot open model file \"" + modelFile + "\"")
       return False

    url_model = uploadURLs['links']['s3_upload_urls']['rapid' + fileExt]
    id        = uploadURLs['id']

    # upload binary data via PUT
    print("Uploading model file ...")
    req = urllib.request.Request(url_model, data=dataModel.read(), method='PUT')
    response, code = executeServerRequest(req)

    if response == None:
        print("Could not upload model file.")
        return False

    # finalize model upload
    reqHeaders = {'Authorization' : 'Bearer ' + accessToken,
                  'Content-Type' : 'application/json'}

    print("Inserting into base assets section ...")
    finalizeUploadURL= baseUrl+FINALIZE_RAWMODEL_ENDPOINT.replace("{id}", str(id))
    req = urllib.request.Request(finalizeUploadURL, headers=reqHeaders)
    response, code = executeServerRequest(req)

    if response == None:
        print("Could not upload model file.")
        return False

    upload_status = ""
    checkOptStatusURL = baseUrl+BASE_ASSET_ENDPOINT.replace("{id}", str(id))
    # if this is a zip file, make sure that the server processed the file (unzipped)
    if fileExt == ".zip":
        print("Waiting for the server to unzip the model.")
        upload_status = "unzipping"

        while upload_status == "unzipping":
            req = urllib.request.Request(checkOptStatusURL, headers=reqHeaders)
            rJSON, code = getServerRequestJSON(req)

            if rJSON == None:
                print("Could not get the base asset status.")
                return False

            upload_status = rJSON["data"]["upload_status"]
            time.sleep(1)

    # wait for the model to be ready
    print("Waiting for the server to analyse the model.")
    while upload_status != "complete":

        req = urllib.request.Request(checkOptStatusURL, headers=reqHeaders)
        rJSON, code = getServerRequestJSON(req)

        if rJSON == None:
            print("Could not get the base asset status.")
            return False

        upload_status = rJSON["data"]["upload_status"]
        time.sleep(1)

    return True

# #############################################################################

def deleteBaseAsset(id, accessToken):
    reqHeaders = {'Authorization' : 'Bearer ' + accessToken,
                  'Content-Type'  : 'application/json'}

    # delete base asset via DELETE
    print("Deleting base asset from cloud storage ...")

    deleteURL = baseUrl+BASE_ASSET_ENDPOINT.replace("{id}", str(id))

    req = urllib.request.Request(deleteURL, headers=reqHeaders, method='DELETE')
    response, code = executeServerRequest(req)

    if response == None or code != 200:
        print("Could not delete base asset from cloud storage.")
        return False
    else:
        print("Success.")
        return True

# #############################################################################

def deleteRapidModel(id, accessToken):
    reqHeaders = {'Authorization' : 'Bearer ' + accessToken,
                  'Content-Type'  : 'application/json'}

    # delete base asset via DELETE
    print("Deleting optimized model from cloud storage ...")

    deleteURL = baseUrl+RAPID_MODEL_ENDPOINT.replace("{id}", str(id))

    req = urllib.request.Request(deleteURL, headers=reqHeaders, method='DELETE')
    response, code = executeServerRequest(req)

    if response == None or code != 200:
        print("Could not delete optimized model from cloud storage.")
        return False
    else:
        print("Success.")
        return True

# #############################################################################

def makeProgessBarStr(progress):
    barStr    = "["
    percSteps = 20
    for i in range(1,percSteps+1):
        if  progress >= i * 5:
            barStr += "#"
        else:
            barStr += "_"
    barStr += "]"
    return barStr

# #############################################################################

def generateOptimizedVariant(modelID, outputModelFilePrefix, variant, accessToken, baseUrl):
    rawModelIDStr = str(modelID)

    reqHeaders = {'Authorization' : 'Bearer ' + accessToken,
                  'Content-Type' : 'application/json'}

    # submit optimization job
    payload = variant

    data = json.dumps(payload).encode("utf8")

    print("Submitting optimization job ...")
    optimizedModelURL= baseUrl+OPTIMIZE_MODEL_ENDPOINT.replace("{id}", rawModelIDStr)
    req         = urllib.request.Request(optimizedModelURL, data=data, headers=reqHeaders)
    rJSON, code = getServerRequestJSON(req)

    if rJSON == None:
        print("Could not submit optimization job.")
        return -1

    rapidModelID    = rJSON["id"]
    rapidModelIDStr = str(rapidModelID)

    # check model status
    print("Waiting for optimization to complete for rapid model " + rapidModelIDStr)

    opt_status = "sent_to_queue"

    checkOptStatusURL = baseUrl+RAPID_MODEL_ENDPOINT.replace("{id}", rapidModelIDStr)
    while (opt_status != "done"):
        req         = urllib.request.Request(checkOptStatusURL, headers=reqHeaders)
        rJSON, code = getServerRequestJSON(req)

        # too many requests?
        if code == 429:
            print("Retrying in 30 seconds...")
            time.sleep(30)
            continue

        if rJSON == None:
            print("Could not get the optimization status.")
            return -1

        if "data" in rJSON and "progress" in rJSON["data"]:
            progress   = rJSON["data"]["progress"]
            barDisplay = makeProgessBarStr(progress)
            for i in range(3-len(str(progress))):
                barDisplay += " "
            pStep      = ""
            if rJSON["data"]["processing_step"]:
                pStep = "  |  " + rJSON["data"]["processing_step"]
                for i in range(45-len(pStep)):
                    pStep += " "
            print(f"\rProgress: {barDisplay} {progress}%{pStep}", end = '')

        opt_status = rJSON["data"]["optimization_status"]
        # if (opt_status != "sent_to_queue" and opt_status != "done"):
        if (opt_status == "sent_to_queue"):
            print("Debug only - Explicitly trigger error")
            print("Error: Unexpected status code from optimization run (" + opt_status + ").")
            return -1

        time.sleep(2)

    # optimization successful

    barDisplayFinal = makeProgessBarStr(100)
    print(f"\rProgress: {barDisplayFinal} 100%  |  Finished.                               \n", end = '')

    exports      = variant["config"]["compressionAndExport"]["fileExports"]
    downloadURLs = rJSON["data"]["downloads"]["all"]

    # name and download results
    # using "downloads"->"all" is the most straightforward way,
    # since each entry there corresponds to one entry in "fileExports"
    # if you need to rename and differentiate between file formats,
    # there are also individual lists / values for each file extension
    i = 0
    for key in downloadURLs:
        dlURL    = downloadURLs[key]
        fileType = exports[i]["fileType"]

        fileExt  = fileType
        if (fileType == "obj" or fileType == "gltf"):
            fileExt = ".zip"

        filenameSuffix = "_e" + str(i) + "." + fileExt
        downloadFile(dlURL, outputModelFilePrefix + filenameSuffix)

        i += 1

    return rapidModelID

# #############################################################################

def validateJSONWithAPISchema(variantConfig, schemaFile, silent):
    schema = None
    try:
        with open(schemaFile) as f:
            schema = json.load(f)
    except:
        if (silent == False):
            print("Error: Unable to validate configuration against schema: schema couldn't be read from file \"" + schemaFile + "\".")
        return False

    try:
        jsonschema.validate(variantConfig, schema)
        if (silent == False):
            print("Variant configuration passed validation.")
        return True
    except Exception as e:
        if (silent == False):
            print("Error: Variant configuration is not valid - see JSON validation report on how to fix this:")
            print("********************************************************************************")
            print(e)
            print("********************************************************************************")

    return False

# #############################################################################

def validateJSONConfigContent(variantConfig):
    exports = variantConfig["compressionAndExport"]["fileExports"]

    exportType0 = exports[0]["fileType"]

    # the V1 currently expects the first export to always be in glb format
    if (exportType0 != "glb"):
        print("Error when checking additional constraint: With API V1, first export must be \"glb\" (given: \"" + exportType0 + "\").")
        return False

    return True


# ################################ #
#           Main Program           #
# ################################ #

# argument parsing

parser = ArgumentParser()

parser.add_argument("model",                    help="input directory or 3D model (must be a .glb file OR .zip file OR base asset ID in the form <number>.id)")
parser.add_argument("-b", "--base-url", dest="baseUrl", default="https://api.rapidcompact.com/api/", help="api base url")
parser.add_argument("-c", "--credentials-file", dest="credentialsFile", default="credentials.json", help="credentials JSON file")
parser.add_argument("-v", "--variants-file", dest="variantsFile", default="variants.json", help="variant definitions JSON file")
parser.add_argument("-l", "--label",  dest="modelLabel", default="", help="label for the model")
parser.add_argument("-o", "--origin", dest="originDesc", default="Gallery Uploader Script", help="origin label for the model")
parser.add_argument('--cleanup',    dest='cleanup', action='store_true')
parser.add_argument('--no-cleanup', dest='cleanup', action='store_false')
parser.add_argument("-e", "--exit", dest="exitOnError", default=False, help="exit script on optimize error. Set False or True")

parser.set_defaults(cleanup=True)

pArgs     = parser.parse_args()
argsDict = vars(pArgs)

modelFile       = argsDict["model"]
variantsFile    = argsDict["variantsFile"]
credentialsFile = argsDict["credentialsFile"]
modelLabel      = argsDict["modelLabel"]
originDesc      = argsDict["originDesc"]
baseUrl         = argsDict["baseUrl"]
cleanup         = argsDict["cleanup"]
exitOnError         = argsDict["exitOnError"]


print("API Endpoint: "+baseUrl)

userCredentials = None
userVariants    = None

try:
    with open(credentialsFile) as f:
        userCredentials = json.load(f)
except:
    print("Unable to load and parse credentials JSON file \"" + credentialsFile + "\". Make sure the file exists and is valid JSON.")
    sys.exit(1)

try:
    with open(variantsFile) as f:
        userVariants = json.load(f)
except:
    print("Unable to load and parse variant definitions JSON file \"" + variantsFile + "\". Make sure the file exists and is valid JSON.")
    sys.exit(1)

# For ExitOnError Flag
failedOptimizations = 0

# 1) obtain token from credentials file

accessToken = userCredentials["token"]

# iterate over input directory OR use input file
directoryMode = os.path.isdir(modelFile)
filesToProcess =[]

if directoryMode:
    print("Running in directory mode.")
    filesToProcess = os.listdir(modelFile)
    # to streamline code below, add the path prefix, just like in single-file mode
    for i in range(0, len(filesToProcess)):
        filesToProcess[i] = os.path.join(modelFile, filesToProcess[i])
else:
    print("Running in single-file mode.")
    filesToProcess = [modelFile]

for nextModelFile in filesToProcess:

    nextModelFileWithoutExt        = nextModelFile[0:nextModelFile.rfind('.')]
    nextModelFileWithoutExtAndPath = os.path.basename(nextModelFileWithoutExt)

    if (accessToken == ""):
        print("Couldn't log in. Are your credentials valid?")
        sys.exit(1)

    if (nextModelFile.endswith(".id")):
        modelID = nextModelFile[:-3]
    else:
        fileExt = nextModelFile[-4:]

        allVariantsInvalid = True

        # validate before uploading, to prevent unnecessary waiting and traffic
        for variantName in userVariants["variants"]:
            variant = userVariants["variants"][variantName]

            print("Validating configuration for variant \"" + variantName + "\".")

            if (validateJSONWithAPISchema(variant["config"], SchemaJSONPath, False)):
                allVariantsInvalid = False

        if (allVariantsInvalid):
            print("No valid variant configuration found. Terminating.")
            sys.exit(1)


        # 2) obtain signed URLs for upload
        if (modelLabel != ""):
            uploadURLs = getUploadURLs(fileExt, accessToken, modelLabel,baseUrl)
        else:
            uploadURLs = getUploadURLs(fileExt, accessToken, nextModelFileWithoutExt,baseUrl)

        if (uploadURLs is None):
            print("Couldn't obtain signed upload URLs from server.")
            sys.exit(1)


        # 3) upload model into the "Base Assets" section, or take existing ID
        success = uploadRawModel(nextModelFile, fileExt, uploadURLs, accessToken, baseUrl)

        if (success == False):
            print("Couldn't upload base asset.")
            sys.exit(1)

        modelID = uploadURLs['id']


    # 4) create optimized variants

    variantIdx = 0

    newRapidModelIDs = []

    for variantName in userVariants["variants"]:

        variant = userVariants["variants"][variantName]

        # check if output folder exists
        if not os.path.isdir("output"):
            os.mkdir("output")

        outputModelFilePrefix = "output/" + nextModelFileWithoutExtAndPath + "_" + variantName

        print("Producing asset variant \"" + variantName + "\".")

        if (validateJSONWithAPISchema(variant["config"], SchemaJSONPath, True)):
            if (validateJSONConfigContent(variant["config"])):
                resultRapidModelID = generateOptimizedVariant(modelID, outputModelFilePrefix, variant, accessToken, baseUrl)
                if (resultRapidModelID != -1):
                    newRapidModelIDs.append(resultRapidModelID)
                else:
                    failedOptimizations += 1

        variantIdx += 1


    # 5) where desired, delete the base asset from the cloud storage after optimization

    if (not nextModelFile.endswith(".id")):
        fileExt = nextModelFile[-4:]
        if (cleanup):
            print("Cleaning up: deleting uploaded base asset and optimized results. If you want to skip this step, run again with option --no-cleanup.")
            deleteBaseAsset(uploadURLs['id'], accessToken)
            for rapidModelID in newRapidModelIDs:
                deleteRapidModel(rapidModelID, accessToken)

# Exit with error
if(exitOnError and failedOptimizations > 0):
    print("Exiting with error because of failed optimizations")
    sys.exit(42)