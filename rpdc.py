# check python version, this script requires python3
import sys
if sys.version_info[0] < 3:
    print('ERROR: This script requires Python 3')
    sys.exit(1)

import urllib.request
import urllib.error

import os
import json
import time
import datetime
from argparse import ArgumentParser
        
        
# ################################ #  
# RapidCompact.Cloud API endpoints #
# ################################ #


LOGIN_ENDPOINT              = "login"
PRESIGNED_FETCH_ENDPOINT    = "rawmodel/api-upload/start"
FINALIZE_RAWMODEL_ENDPOINT  = "rawmodel/{id}/api-upload/complete"
OPTIMIZE_MODEL_ENDPOINT     = "rawmodel/process/{id}"
CHECK_UPLOADSTATUS_ENDPOINT = "rawmodel/{id}"
CHECK_OPTSTATUS_ENDPOINT    = "rapidmodel/{id}"

AUTH_FILE = "auth.cache"

# ################################ #  
#         Helper Functions         #
# ################################ #

def executeServerRequest(request):
    try:
        response = urllib.request.urlopen(request)
    except urllib.error.URLError as e:
        if hasattr(e, "reason"):
            print("ERROR: Failed to fulfill the request.")
            print("Error code: ", e.code)
            print("Reason: ", e.reason)
            return None, e.code
        elif hasattr(e, "code"):
            print("ERROR: The server couldn't fulfill the request.")
            print("Error code: ", e.code)
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
    except e:
        print("ERROR: Could not parse the result from server.")

    return rJSON, response.getcode()

# #############################################################################       

def downloadFile(fileURL, outputFilePath):
    req = urllib.request.Request(fileURL)
    response, code = executeServerRequest(req)
    if not response:
        return False


    try:
        with open(outputFilePath, 'wb') as f:
            f.write(response.read())
    except: 
       print("Error: Cannot write to output file \"" + outputFilePath + "\".")
       return False

    return True

# #############################################################################       

def loadTokenFromFile(baseUrl):
    auth = {}
    try:
        with open(AUTH_FILE) as f:
            auth = json.load(f)
    except:
        return None

    if "access_token" not in auth or "expiration" not in auth or "base_url" not in auth:
        return None

    if auth["base_url"] != baseUrl:
        return None

    tokenExpiration = datetime.datetime.fromisoformat(auth["expiration"])
    currentTimedate = datetime.datetime.now()
    if tokenExpiration > currentTimedate:
        return auth["access_token"]
    else:
        return None

# #############################################################################       

def login(credentials, baseUrl):
    print("Logging in...")

    cachedToken = loadTokenFromFile(baseUrl)
    if cachedToken:
        print("Using cached token")
        return cachedToken

    currentTimedate = datetime.datetime.now()

    data = json.dumps(credentials).encode("utf8")
    req = urllib.request.Request(baseUrl+LOGIN_ENDPOINT, data, headers={'content-type': 'application/json'})
    responseJSON, code = getServerRequestJSON(req)
    if not responseJSON or not 'access_token' in responseJSON:
        return ""

    print("Logged in.\n")

    accessToken = responseJSON['access_token']
    tokenExpiration = currentTimedate + datetime.timedelta(seconds=responseJSON["expires_in"])
    authData = {"base_url":baseUrl,"access_token": accessToken, "expiration": tokenExpiration.isoformat()}

    try:
        with open(AUTH_FILE, 'w') as f:
            json.dump(authData, f)
    except e:
       print(e)
       print("Could not cache auth token")

    return accessToken

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
    
    print("Inserting into raw models section ...")
    finalizeUploadURL= baseUrl+FINALIZE_RAWMODEL_ENDPOINT.replace("{id}", str(id))
    req = urllib.request.Request(finalizeUploadURL, headers=reqHeaders)
    response, code = executeServerRequest(req)

    if response == None:
        print("Could not upload model file.")
        return False

    

    upload_status = ""
    checkOptStatusURL = baseUrl+CHECK_UPLOADSTATUS_ENDPOINT.replace("{id}", str(id))
    # if this is a zip file, make sure that the server processed the file (unzipped)
    if fileExt == ".zip":
        print("Waiting for the server to unzip the model.")
        upload_status = "unzipping"

        while upload_status == "unzipping":
            req = urllib.request.Request(checkOptStatusURL, headers=reqHeaders)
            rJSON, code = getServerRequestJSON(req)

            if rJSON == None:
                print("Could not get the raw model status.")
                return False

            upload_status = rJSON["data"]["upload_status"]
            time.sleep(1)

    # wait for the model to be ready
    print("Waiting for the server to analyse the model.")
    while upload_status != "complete":
        
        req = urllib.request.Request(checkOptStatusURL, headers=reqHeaders)
        rJSON, code = getServerRequestJSON(req)

        if rJSON == None:
            print("Could not get the raw model status.")
            return False

        upload_status = rJSON["data"]["upload_status"]
        time.sleep(1)

    return True

# #############################################################################    

def generateOptimizedVariant(modelID, outputFile, mbCountStr, configDict, accessToken, extension, baseUrl):
    rawModelIDStr = str(modelID)

    reqHeaders = {'Authorization' : 'Bearer ' + accessToken,
                  'Content-Type' : 'application/json'}

    configStr = json.dumps(configDict)
    
    # submit optimization job    
    payload = ""
    
    if (mbCountStr != ""):
        # payload = {"max_size_mb" : str(mbCountStr), "config" : configStr}
        payload = {"max_size_mb" : float(mbCountStr), "config" : configStr}
    else:
        payload = {"config" : configStr}

    data = json.dumps(payload).encode("utf8")

    print("Submitting optimization job ...")
    optimizedModelURL= baseUrl+OPTIMIZE_MODEL_ENDPOINT.replace("{id}", rawModelIDStr)
    req = urllib.request.Request(optimizedModelURL, data=data, headers=reqHeaders)
    rJSON, code = getServerRequestJSON(req)

    if rJSON == None:
        print("Could not submit optimization job.")
        return False
    
    rapidModelIDStr = str(rJSON["id"])
    
    # check model status
    print("Waiting for optimization to complete for rapid model " + rapidModelIDStr)

    opt_status = "sent_to_queue"

    checkOptStatusURL = baseUrl+CHECK_OPTSTATUS_ENDPOINT.replace("{id}", rapidModelIDStr)
    while (opt_status != "done"):
        req = urllib.request.Request(checkOptStatusURL, headers=reqHeaders)
        rJSON, code = getServerRequestJSON(req)
       
        # too many requests?
        if code == 429:
            print("Retrying in 30 seconds...")
            time.sleep(30)
            continue

        if rJSON == None:
            print("Could not get the optimization status.")
            return False

        if "data" in rJSON and "progress" in rJSON["data"]:
            progress = rJSON["data"]["progress"]
            print(f"\rProgress: {progress}%", end = '')

        opt_status = rJSON["data"]["optimization_status"]
        if (opt_status != "sent_to_queue" and opt_status != "done"):
            print("Error: Unexpected status code from optimization run (" + opt_status + ").")
            return False
        time.sleep(5)
    
    print("\nCompleted.")

    downloadURL = rJSON["data"]["downloads"][extension]

    # download result
    return downloadFile(downloadURL, outputFile)


# ################################ #  
#           Main Program           #
# ################################ #

# argument parsing

parser = ArgumentParser()

parser.add_argument("model",                    help="input directory or 3D model (must be a .glb file OR .zip file OR raw model ID in the form <number>.id)")
parser.add_argument("-b", "--base-url", dest="baseUrl", default="https://api.rapidcompact.com/api/", help="api base url")
parser.add_argument("-c", "--credentials-file", dest="credentialsFile", default="credentials.json", help="credentials JSON file")
parser.add_argument("-v", "--variants-file", dest="variantsFile", default="variants.json", help="variant definitions JSON file")
parser.add_argument("-l", "--label",  dest="modelLabel", default="", help="label for the model")
parser.add_argument("-o", "--origin", dest="originDesc", default="Gallery Uploader Script", help="origin label for the model")

pArgs     = parser.parse_args()
argsDict = vars(pArgs)

modelFile       = argsDict["model"]
variantsFile    = argsDict["variantsFile"]
credentialsFile = argsDict["credentialsFile"]
modelLabel      = argsDict["modelLabel"]
originDesc      = argsDict["originDesc"]
baseUrl         = argsDict["baseUrl"]


print("API Endpoint: "+baseUrl)

userCredentials = None
userVariants    = None

try:
    with open(credentialsFile) as f:
        userCredentials = json.load(f)
except:
    print("Unable to load and parse credentials JSON file \"" + credentialsFile + "\". Make sure the file exists and is valid JSON.")
    quit()
        
try:
    with open(variantsFile) as f:
        userVariants = json.load(f)
except:
    print("Unable to load and parse variant definitions JSON file \"" + variantsFile + "\". Make sure the file exists and is valid JSON.")
    quit()
  

# 1) perform login with user credentials via HTTPS

accessToken = login(userCredentials, baseUrl)
    
# iterate over input directory OR use input file
directoryMode = (modelFile.rfind(".") == -1)
filesToProcess =[]

if directoryMode:
    filesToProcess = os.listdir(modelFile)
else:
    filesToProcess = [modelFile]

for nextModelFile in filesToProcess:

    nextModelFileWithoutExt = nextModelFile[0:nextModelFile.rfind('.')]

    if (accessToken == ""):
        print("Couldn't log in. Are your credentials valid?")
        quit()

    if (nextModelFile.endswith(".id")):
        modelID = nextModelFile[:-3]
    else:
        fileExt = nextModelFile[-4:]
        
        # 2) obtain signed URLs for upload        
        if (modelLabel != ""):
            uploadURLs = getUploadURLs(fileExt, accessToken, modelLabel,baseUrl)
        else:
            uploadURLs = getUploadURLs(fileExt, accessToken, nextModelFileWithoutExt,baseUrl)

        if (uploadURLs is None):
            print("Couldn't obtain signed upload URLs from server.")
            quit()
            

        # 3) upload model into the "RawModels" section, or take existing ID
        if directoryMode:        
            success = uploadRawModel(modelFile + "/" + nextModelFile, fileExt, uploadURLs, accessToken, baseUrl)
        else:
            success = uploadRawModel(nextModelFile, fileExt, uploadURLs, accessToken, baseUrl)

        if (success == False):
            print("Couldn't upload raw model.")
            quit()
            
        modelID = uploadURLs['id']


    # 4) create optimized variants

    for variant in userVariants["variants"]:
        mbCount  = str(variant["maxMBCount"])
        mbCountF = 0.0
        
        if (mbCount != ""):
            mbCountF = float(mbCount)
        
        # check if output folder exists
        if not os.path.isdir("output"):
            os.mkdir("output")

        configDict = variant["rpd_config"]
        extension  = variant["outputFileExtension"]

        if (extension == "obj"):
            outputModelFile = "output/" + nextModelFileWithoutExt + variant["outputFileSuffix"] + ".zip"
        else:
            outputModelFile = "output/" + nextModelFileWithoutExt + variant["outputFileSuffix"] + "." + extension
            
        if (mbCount != "" and (mbCountF > 25.0 or mbCountF < 0.1)):
            print("Warning: MB count must be a value between 0.1 and 25. Skipping Variant.")
        else:
            if (mbCount != ""):
                print("Optimizing to " + mbCount + "MB.")
            else:
                print("Optimizing to given configuration.")
            generateOptimizedVariant(modelID, outputModelFile, mbCount, configDict, accessToken, extension, baseUrl)            
