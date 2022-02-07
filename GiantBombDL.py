#! /usr/bin/python
# python3
# GiantBombDL by falcorr
# Giant Bomb API: https://www.giantbomb.com/api/
# requires wget
# benefits from ffmpeg, ffprobe, AtomicParsley

import os
import sys
import time
import subprocess
import shutil
import re
import argparse
import urllib.request as urllib2
import json

COLOURS = { "red": "\033[31m",
       "lightRed": "\033[91m",
          "green": "\033[32m",
     "lightGreen": "\033[92m",
         "yellow": "\033[33m",
    "lightYellow": "\033[93m",
           "blue": "\033[34m",
      "lightBlue": "\033[94m",
        "magenta": "\033[35m",
   "lightMagenta": "\033[95m",
           "cyan": "\033[36m",
      "lightCyan": "\033[96m",
           "grey": "\033[90m",
      "lightGrey": "\033[37m",
          "white": "\033[97m",
          "black": "\033[30m",
          "reset": "\033[0m" }

colourEnabled = True
           
STATUS_CODES = { 1: "OK",
               100: "Invalid API key",
               101: "Object not found",
               102: "Invalid URL format",
               103: "jsonp' format requires a 'json_callback' argument",
               104: "Filter error",
               105: "Premium-only video" }
                
# Which ffmpeg errors indicate a rejected video, don't need to escape strings
VIDEO_ERRORS = { "Update your FFmpeg version": False,
                 "Not yet implemented in FFmpeg": False,
                 "moov atom not found": False,
                 "Assuming an incorrectly encoded channel layout": False,
                 "Format detected only misdetection possible": False,
                 "Reserved bit set": False,
                 "ms_present = is reserved": False,
                 "Packet corrupt": False,
                 "Sample rate index in program config element does not match the sample rate index configured by the container": False,
                 "Remapped id too large": False,
                 "Too large remapped id is not implemented": False,
                 "More than one AAC RDB per ADTS frame is not implemented": False,
                 "partial file": True,
                 "Invalid argument": True,
                 "Invalid data found when processing input": True,
                 "Invalid NAL unit size": True,
                 "Error splitting the input into NAL units": True,
                 "Error while decoding stream": True,
                 "get_buffer() failed": True,
                 "Number of bands exceeds limit": True,
                 "channel element is not allocated": True,
                 "Prediction is not allowed": True,
                 "Number of scalefactor bands in group exceeds limit": True,
                 "Pulse tool not allowed in eight short sequence": True,
                 "Inconsistent channel configuration": True, 
                 "Dependent coupling is not supported together": True,
                 "was found before the first channel element": True,
                 "invalid band type": True,
                 "Input buffer exhausted before END element found": True,
                 "Invalid Predictor Reset Group": True }

capabilities = { "ffmpeg" : False,
                 "ffprobe": False,
           "AtomicParsley": False }


rootDir = None
args = None
truncateThreshold = None
CONFIG_FILE = "GiantBombDL.cfg"
apiKey = "put yo api key here"
RATE_LIMIT_VIDEO_LENGTH = 41.749
           
def log(text, append = True):
    try:
        if append:
            log = open(rootDir + '/' + logFilename + '.log', 'a')
        else:
            log = open(rootDir + '/' + logFilename + '.log', 'wt')
    except:
        print("[Error] problem writing log file")
    finally:
        log.write("[%s] %s\n" % (datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S'), text))
        log.close

def onScreenLog(text, colour):
    if colourEnabled:
        print(colour + text + COLOURS["reset"])
    else:
        print(text)
        
def truncate(content, length=truncateThreshold, suffix='...'):  
    if length:
        if len(content) > length:
            content = ' '.join(content[:length+1].split(' ')[0:-1]) + suffix
        
        if len(content) > 3:
            if content[-4:] == "....":
                content = content[:-1]

        if content == "...":
            content = ""
    else:
        content = ""
        
    return content

def verify(filename, isVideo=True):
    """ returns False on failure """
    
    if isVideo == False:
        if os.name == "nt":
            if os.path.exists(filename):
                if os.stat(filename).st_size == 0:
                    os.system('del "{0}"'.format(filename.replace('/', '\\')))
                else:
                    onScreenLog("Info: thumbnail downloaded", COLOURS["white"])
                    return True
            
            onScreenLog("Error: thumbnail download failed", COLOURS["lightRed"])
            return False
        else:
            try:
                process = subprocess.Popen(["/usr/bin/file", "-i", filename], stdout=subprocess.PIPE)
                mimeType = process.communicate(timeout=5)[0].split()[1]
                process.wait(5)
            except:
                process.kill()
                onScreenLog("Error: thumbnail download failed", COLOURS["lightRed"])
                return False
                
            mimeType = mimeType.decode("utf-8")[:-1]
            thumbnailMimes = { "image/jpeg", "image/png", "image/bmp", "image/gif" }
            for i in thumbnailMimes:
                if re.search(re.escape(mimeType), i, re.IGNORECASE):
                    process.kill()
                    onScreenLog("Info: thumbnail downloaded", COLOURS["white"])
                    return True
                    
            process.kill()
            onScreenLog("Error: thumbnail download failed", COLOURS["lightRed"])
            return False
    
    if not os.path.exists(filename):
        onScreenLog("Error: something went wrong", COLOURS["lightRed"])
        return False
    if os.stat(filename).st_size == 0:
        # wget failed, empty destination file
        if os.name == "nt":
            os.system('del "{0}"'.format(filename.replace('/', '\\')))
            pass
        else:
            os.system('rm -f "{0}"'.format(filename.replace('\\', '/')))
        onScreenLog("Error: source file unavailable", COLOURS["lightRed"])
        return False
    
    if args.verifyBasic is False:
        return True
    
    onScreenLog("Info: verifying ..", COLOURS["white"])
    
    # Quick checks for obvious problems
    checks = { 1: "ffmpeg -v warning -sseof -10 -threads {0} -i \"{1}\" -f null -".format(args.verifyThreads, filename), 
               2: "ffmpeg -v warning -t 10 -threads {0} -i \"{1}\" -f null -".format(args.verifyThreads, filename),
               3: "ffmpeg -v warning -ss 300 -t 10 -threads {0} -i \"{1}\" -f null -".format(args.verifyThreads, filename),
               4: "ffmpeg -v warning -ss 600 -t 10 -threads {0} -i \"{1}\" -f null -".format(args.verifyThreads, filename),
               5: "ffmpeg -v warning -ss 1800 -t 10 -threads {0} -i \"{1}\" -f null -".format(args.verifyThreads, filename),
               6: "ffmpeg -v warning -ss 3600 -t 10 -threads {0} -i \"{1}\" -f null -".format(args.verifyThreads, filename), }
    # Check whole file
    if args.verifyComplete is True:
        checks[7] = "ffmpeg -v warning -threads {0} -i \"{1}\" -f null -".format(args.verifyThreads, filename)
    
    for key, value in checks.items():
        process = subprocess.Popen(value, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        
        output = ""
        # Check -ss, -t, -sseof parameter validity
        sseofInvalid = False
        while True:
            returnCode = process.poll() 
            line = process.stdout.readline()
            cleanLine = line.decode('utf-8')
            if not cleanLine == "":
                output += cleanLine
                if re.search(re.escape("-sseof value seeks to before start of file"), cleanLine, re.IGNORECASE) or re.search(re.escape("Invalid duration"), cleanLine, re.IGNORECASE):
                    sseofInvalid = True
                    break   
            if returnCode is not None:
                wait = False
                break
        
        # If -sseof parameter was invalid, skip to next command
        if sseofInvalid is False:
            if "-ss " in value or "-sseof " in value:
                try:
                    process.wait(15)
                except:
                    process.kill()
                    pass
            else:
                try:
                    process.wait(os.stat(filename).st_size / 2000000 + 5) 
                except:
                    # Timeout hit, assume there was a problem
                    process.kill()
                    onScreenLog("Error: video verification timed out", COLOURS["lightRed"])
                    return False
                
            for i in range(len(output)):
                for key, value in VIDEO_ERRORS.items():
                    if re.search(re.escape(key), output, re.IGNORECASE):
                        if value is True:
                            process.kill()
                            onScreenLog("Error: video verification failed", COLOURS["lightRed"])
                            return False
                            
    process.kill()
    onScreenLog("Info: video verified", COLOURS["white"])
    return True

def loadConfig():

    config = json.loads("{}")
    addKeyToConfig = False
    if os.path.exists(rootDir + '/' + CONFIG_FILE):
        if os.path.isfile(rootDir + '/' + CONFIG_FILE) and os.access(rootDir + '/' + CONFIG_FILE, os.X_OK):
            with open(rootDir + '/' + CONFIG_FILE, 'r') as file:
                config = json.load(file)
            if "API_KEY" not in config:
                addKeyToConfig = True
            elif config["API_KEY"] == "":
                addKeyToConfig = True
    else:
        addKeyToConfig = True
        
    if addKeyToConfig:
        print("Enter API key (found at www.giantbomb.com/api)")
        apiKey = input('> ')
        config["API_KEY"] = apiKey.strip()
        json.dump(config, open(CONFIG_FILE, "w"))
    
    apiKey = config["API_KEY"]

def checkLength(video):
    if args.filterMinimumLength:
        if video["length_seconds"] < args.filterMinimumLength:
            return False
    if args.filterMaximumLength:
        if video["length_seconds"] > args.filterMaximumLength:
            return False
            
    return True

def retrieveJSON(url, JSON):
    response = None
    try:
        response = urllib2.urlopen(url).read()
    except (urllib2.HTTPError, exception):
        onScreenLog("Error: HTTPError = " + str(exception.code), COLOURS["lightRed"])
    except (urllib2.URLError, exception):
        onScreenLog("Error: URLError = " + str(exception.reason), COLOURS["lightRed"])
    
    if response != None:
        responseJSON = json.loads(response)

        if "status_code" in responseJSON:
            statusCode = int(responseJSON["status_code"])
            if statusCode in STATUS_CODES:
                error =  STATUS_CODES[statusCode]
            else:
                error =  "unknown"
            if error == "OK":
                JSON.update(responseJSON)
                return True
        else:
            onScreenLog("Error: " + error, COLOURS["lightRed"])

    return False

def listShows():
    onScreenLog("List of shows", COLOURS["lightMagenta"])
    showsURL = "http://www.giantbomb.com/api/video_shows/?api_key={0}&format=json".format(apiKey)
    JSON = json.loads("{}")
    
    
    if retrieveJSON(showsURL, JSON) is False:
        onScreenLog("Error: failed to retrieve from API", COLOURS["lightRed"])
    else:
        if True:
            for show in JSON["results"]:
                description = truncate(show["deck"])
                if len(description) < 1:
                    onScreenLog("[{0}] {1}".format(show["id"], show["title"]), COLOURS["blue"])
                else:
                    onScreenLog("[{0}] {1}\n{2}\n".format(show["id"], show["title"], description), COLOURS["blue"])

def getVideo(JSON, filteredJSON=None):
    if filteredJSON:
        for key, value in filteredJSON.items():
            yield value
    
    for video in JSON["results"]:
        yield video

def download():
    
    global args
    
    APIURL = "http://www.giantbomb.com/api/videos/?api_key={0}&format=json&limit={1}&offset={2}&sort=id:{3}".format(apiKey, str(args.limit), str(args.offset), args.sortOrder)
    
    if args.filterPhrase or args.filterShowID or args.filterVideoID:
        APIURL += "&filter="
    if args.filterPhrase:
        APIURL += "name:{0}".format(args.filterPhrase.replace(" ", "%20"))
    if args.filterVideoID:
        if args.filterPhrase:
            APIURL += ","
        APIURL += "id:{0}".format(args.filterVideoID)
    if args.filterShowID:
        if args.filterPhrase or args.filterVideoID:
            APIURL += ","
        APIURL += "video_show:{0}".format(args.filterShowID)
    
    # default
    JSON = json.loads("{}")
    
    # default
    downloadRecord = {}
    if args.downloadRecordFile:
        if os.path.isfile(rootDir + '/' + args.downloadRecordFile):
            with open(rootDir + '/' + args.downloadRecordFile, 'r') as file:
                downloadRecord = json.load(file)
    
    if retrieveJSON(APIURL, JSON) is False:
        onScreenLog("Error: failed to retrieve from API", COLOURS["lightRed"])
    
    rateLimitCandidateCount = 0
    rateLimitCandidateFilenames = []
    rateLimitCandidateIDs = []
    
    # Filter out videos
    if args.filterPhraseExclude or args.filterMinimumLength or args.filterMaximumLength:
        filteredJSON = json.loads("{}")
        
        for index in range(len(JSON["results"])):
            filteredOut = False
            
            # exclude word or phrase
            if args.filterPhraseExclude:
                if re.search(re.escape(args.filterPhraseExclude), JSON["results"][index]["name"], re.IGNORECASE) or re.search(re.escape(args.filterPhraseExclude), JSON["results"][index]["video_show"]["title"], re.IGNORECASE):
                    filteredOut = True
            # length
            if args.filterMinimumLength or args.filterMaximumLength:
                if checkLength(JSON["results"][index]) is False:
                    filteredOut = True
                    
            if filteredOut is False:
                filteredJSON[index] = JSON["results"][index]
            else:
                try:
                    del filteredJSON[index]
                except:
                    pass
    else:
        filteredJSON = None
    
    # Display number of results
    if not args.filterVideoID:
        if filteredJSON is not None:
            results = len(filteredJSON)
        else:
            results = JSON["number_of_total_results"]
        if results == 0:
            onScreenLog("Results: 0", COLOURS["white"])
            sys.exit()
        elif results == 100:
            onScreenLog("Results: 100 (hit request limit, there may be more results, use offset)", COLOURS["white"])
        elif results < 100 and JSON["number_of_total_results"] == 100:
            onScreenLog("Results: {0} (hit request limit, there may be more results, use offset)".format(results), COLOURS["white"])
        else:
            onScreenLog("Results: {0}".format(results), COLOURS["white"])
    
    for video in getVideo(JSON, filteredJSON):
        # Format filename
        filename = video["name"]
        if args.codifiedFilename is True:
            filename = filename.replace("%", "%25")
            filename = filename.replace(" ", "%20")
            filename = filename.replace("-", "%2D")
            filename = filename.replace("/", "%2F")
            filename = filename.replace("\\", "%5C")
            filename = filename.replace("\"", "%22")     
            filename = filename.replace("|", "%7C")  
            filename = filename.replace(":", "%3A")
            filename = filename.replace(";", "%3B")
            filename = filename.replace("?", "%3F")
            filename = filename.replace("!", "%21")
            filename = filename.replace("&", "%26")
            filename = filename.replace("(", "%28")
            filename = filename.replace(")", "%29")
            filename = filename.replace("[", "%5B")
            filename = filename.replace("]", "%5D")
            filename = filename.replace("*", "%2A")
            filename = filename.replace(",", "%2C")
            filename = filename.replace("'", "%27")            
            filename = filename.replace("`", "%60")
            filename = filename.replace("<", "%3C")
            filename = filename.replace(">", "%3E")
        else:
            filename = filename.replace(":", " ")
            filename = filename.replace("?", " ")
            filename = filename.replace("/", "_")
            filename = filename.replace("\\", "_")
            filename = filename.replace("<", "_")
            filename = filename.replace(">", "_")
            filename = filename.replace("\"", "'")
            filename = filename.replace("*", " ")
        
        minutes, seconds = divmod(video["length_seconds"], 60)
        hours, minutes = divmod(minutes, 60)
        filename += "___" + "{0}h{1}m{2}s".format(hours, minutes, seconds)
        filename += "_" + str(video["id"])
        
        # Ensure output directory exists
        if args.outputDirectory != None:
            if not os.path.exists(args.outputDirectory):
                os.makedirs(args.outputDirectory)
            filename = args.outputDirectory + "/" + filename
        else:
            filename = rootDir + '/' + filename
        
        if args.downloadRecordFile and str(video["id"]) in downloadRecord:
            # Video has been previously downloaded, as indicated by the record
            onScreenLog("Skipping download, video ID exists in download record", COLOURS["grey"])
        else:
            # Download video    
            title = "[id:" + str(video["id"]) + "] "
            if video["video_show"] is not None:
                if not re.search(re.escape(video["video_show"]["title"]), video["name"], re.IGNORECASE) or not re.search(re.escape(video["video_show"]["title"].replace(':', '')), video["name"], re.IGNORECASE):
                    title += video["video_show"]["title"] + ": "
            else:
                title += "(no show): "
            if minutes == 0:
                strSeconds = str(seconds) + "s"
            else:
                strSeconds = ""
            title += video["name"]
            onScreenLog("Downloading {0} ({1}h{2}m{3})".format(title, str(hours), str(minutes), strSeconds), COLOURS["cyan"])
            
            # Quality fallback
            currentQuality = args.quality
            qualityChecked = { "low" : False,
                               "high": False,
                               "hd"  : False }
            qualityFound = False
            URLNotFound = False  
            while not qualityFound and not URLNotFound:
                if currentQuality == "low":
                    videoURL = video["low_url"]
                elif currentQuality == "high":
                    videoURL = video["high_url"]
                elif currentQuality == "hd":
                    videoURL = video["hd_url"]
                
                if videoURL is None:
                    onScreenLog("Warning: {0} quality unavailable".format(currentQuality), COLOURS["yellow"])
                    qualityChecked[currentQuality] = True
                    
                    if currentQuality == "low":
                        if args.fallback == "lower":
                            if args.fallbackExhaustive:
                                for index, key in enumerate(qualityChecked):
                                    if qualityChecked[key] is False:
                                        currentQuality = key
                                        break
                                
                                if not False in qualityChecked.values():
                                    URLNotFound = True
                            else:
                                URLNotFound = True
                        else:
                            currentQuality = "high"
                    elif currentQuality == "high":
                        if args.fallback == "lower":
                            currentQuality = "low"
                        else:
                            currentQuality = "hd"
                    elif currentQuality == "hd":
                        if args.fallback == "lower":
                            currentQuality = "high"
                        else:
                            if args.fallbackExhaustive:
                                for index, key in reversed(enumerate(qualityChecked)):
                                    if qualityChecked[key] is False:
                                        currentQuality = key
                                        break
                                        
                                if not False in qualityChecked.values():
                                    URLNotFound = True
                            else:
                                URLNotFound = True
                else:
                    qualityFound = True
            
            if URLNotFound:
                # No qualities available
                onScreenLog("Error: all qualities unavailable", COLOURS["lightRed"])        
            else:
                # An accepted quality was found
                args.verifyRetry = 0
                while args.verifyRetry >= 0:
                    onScreenLog("Info: {0} quality will be downloaded".format(currentQuality), COLOURS["white"])
                    
                    # Downloading video
                    process = subprocess.Popen(["wget", "--user-agent", "GiantBombDL", videoURL + "?api_key=" + apiKey, "-c", "-q", "--show-progress", "-O", filename + ".mp4"], stdout=subprocess.PIPE)
                    while True:
                        returnCode = process.poll() 
                        line = process.stdout.readline()
                        if not line.decode('utf-8') == "":
                            print(line.decode('utf-8'))
                        if returnCode is not None:
                            wait = False
                            break
                    
                    if verify(filename + ".mp4") is True:
                        downloadRecord[video["id"]] = video["name"]
                        if args.downloadRecordFile:
                            with open(rootDir + '/' + args.downloadRecordFile, 'w') as file:
                                json.dump(downloadRecord, file, indent=4, sort_keys=True)
                        
                        try:
                            if args.thumbnail:   
                                if not video["image"]["small_url"] is None:
                                    thumbnailExtension = os.path.splitext(video["image"]["small_url"])[1]
                                    thumbnailURL = video["image"]["small_url"]  
                                elif not video["image"]["screen_url"] is None:
                                    thumbnailExtension = os.path.splitext(video["image"]["screen_url"])[1]
                                    thumbnailURL = video["image"]["screen_url"]
                                elif not video["image"]["original_url"] is None:
                                    thumbnailExtension = os.path.splitext(video["image"]["original_url"])[1]
                                    thumbnailURL = video["image"]["original_url"]
                                    
                                process = subprocess.Popen(["wget", "--user-agent", "GiantBombDL", thumbnailURL, "-c", "-q", "--show-progress", "-O", filename + thumbnailExtension], stdout=subprocess.PIPE)
                                while True:
                                    returnCode = process.poll() 
                                    line = process.stdout.readline()
                                    if returnCode is not None:
                                        break
                                verify(filename + thumbnailExtension, False)
                        except:
                            onScreenLog("Error: unable to retrieve thumbnail", COLOURS["lightRed"])
                        
                        # Check for rate-limiting
                        if shutil.which("ffprobe"):
                            if os.path.exists(filename + ".mp4"):
                                process = subprocess.Popen(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", filename + ".mp4"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                                process.stdout.flush()
                                duration = list(map(float, process.stdout))[0]
                                
                                print("Video duration (s): " + str(duration))
                                if duration == RATE_LIMIT_VIDEO_LENGTH:
                                    rateLimitCandidateCount += 1
                                    rateLimitCandidateFilenames.append(filename)
                                    rateLimitCandidateIDs.append(video["id"])
                                    
                                    # Certain of rate-limiting
                                    if rateLimitCandidateCount > 2:
                                        onScreenLog("Error: rate-limited", COLOURS["lightRed"])
                                        for i in rateLimitCandidateFilenames:
                                            try:
                                                os.remove(rateLimitCandidateFilenames[i])
                                            except:
                                                pass
                                        rateLimitCandidateFilenames[:] = []
                                        for i in rateLimitCandidateIDs:
                                            downloadRecord.remove(rateLimitCandidateIDs[i])
                                        rateLimitCandidateIDs[:] = []
                                        if args.downloadRecordFile:
                                            with open(rootDir + '/' + args.downloadRecordFile, 'w') as file:
                                                json.dump(downloadRecord, file, sort_keys=True, indent=4)
                                else:
                                    rateLimitCandidateCount = 0
                                    rateLimitCandidateFilenames[:] = []
                                    rateLimitCandidateIDs[:] = []   
                                
                        else:
                            onScreenLog("Warning: unable to check for rate-limiting, ffprobe unavailable", COLOURS["yellow"])
                        
                        if shutil.which("AtomicParsley"):
                            pass
                        else:
                            onScreenLog("Warning: unable to edit metadata, AtomicParsley unavailable", COLOURS["yellow"])
                    
                    args.verifyRetry -= 1

def checkCapability():

    global capabilities
    
    if not shutil.which("wget"):
        onScreenLog("Error: wget missing", COLOURS["lightRed"])
        sys.exit()
    if shutil.which("ffmpeg"):
        onScreenLog("Info: ffmpeg found, verification available", COLOURS["white"])
        capabilities["ffmpeg"] = True
    else:
        onScreenLog("Warning: ffmpeg missing, verification unavailable", COLOURS["yellow"])
    if shutil.which("ffprobe"):
        onScreenLog("Info: ffprobe found, rate-limiting detection available", COLOURS["white"])
        capabilities["ffprobe"] = True
    else:
        onScreenLog("Warning: ffprobe missing, rate-limiting detection unavailable", COLOURS["yellow"])
    if shutil.which("AtomicParsley"):
        onScreenLog("Info: AtomicParsley found, metadata modification available", COLOURS["white"])
        capabilities["AtomicParsley"] = True
    else:
        onScreenLog("Warning: AtomicParsley missing, metadata modification unavailable", COLOURS["yellow"])
  
def validateArgs():
    
    global args
    
    if args.quality != None:
        args.quality = args.quality.lower()
        if args.quality not in ['low', 'high', 'hd']:
            onScreenLog("Error: invalid quality, options are \"low\", \"high\", \"hd\"", COLOURS["lightRed"])
            return False
    
    if args.fallback != None:
        args.fallback = args.fallback.lower()
        if args.quality not in ['lower', 'higher', 'low', 'high', 'downgrade', 'upgrade', 'down', 'up']:
            onScreenLog("Error: invalid fallback, options are \"lower\", \"higher\"", COLOURS["lightRed"])
            return False
    
    # Limit of 100 set by Giant Bomb
    # A limit of zero amounts to a dry run
    if args.limit < 0 or args.limit > 100:
        onScreenLog("Error: limit must be in the range 0-100", COLOURS["lightRed"])
        return False
        
    if args.offset < 0:
        onScreenLog("Error: limit must be in the range 0-100", COLOURS["lightRed"])
        return False
    
    args.sortOrder = args.sortOrder.lower()
    if args.sortOrder == "ascending":
        args.sortOrder = "asc"
    if args.sortOrder == "descending":
        args.sortOrder = "desc"
    if args.sortOrder == "asce":
        args.sortOrder = "asc"
    if args.sortOrder == "des":
        args.sortOrder = "desc"
    if args.sortOrder == "up":
        args.sortOrder = "asc"
    if args.sortOrder == "down":
        args.sortOrder = "desc"
    if args.sortOrder not in ['asc', 'desc']:
        onScreenLog("Error: invalid sort, options are \"ascending\" or \"descending\"", COLOURS["lightRed"])
        return False
    
    if args.verifyThreads < 0:
        onScreenLog("Error: invalid threads number", COLOURS["lightRed"])
        return False
    
    if args.verifyRetry < 0:
        onScreenLog("Error: invalid failed verification retries", COLOURS["lightRed"])
        return False
    elif args.verifyRetry > 2:
        onScreenLog("Error: too many failed verification retries, setting to the maximum of two", COLOURS["lightRed"])
        args.verifyRetry = 2
    
    if args.downloadRecordFile and not args.downloadRecordFile.endswith(".json"):
        args.downloadRecordFile = args.downloadRecordFile.split('.')[0] + ".json"
        onScreenLog("Info: download record file will use .json extension", COLOURS["lightRed"])
    
    if args.filter is False:
        if args.filterPhrase != None or args.filterVideoID != None or args.filterShowID != None:
            onScreenLog("Error: add --filter to process filter arguments", COLOURS["lightRed"])
            return False
            
    return True

def init():
    parser = argparse.ArgumentParser()
    parser.add_argument('--list-shows', '-L', dest="showIDs", action="store_true", help="show list", default=False)
    parser.add_argument('--quality', '-q', metavar="low/high/hd",dest="quality", action="store", default="high", help="video quality (low, high, hd) [default: %(default)s]")
    parser.add_argument('--fallback', '-f', metavar="lower/higher",dest="fallback", action="store", default="lower", help="fallback video quality to lower or higher [default: %(default)s]")
    parser.add_argument('--fallback-exhaustive', '-e', dest="fallbackExhaustive", action="store_true", default=False, help="whether --fallback should try all remaining options if still unsuccessful [default: %(default)s]")
    parser.add_argument('--limit', '-l', dest="limit", metavar="number", action="store", type=int, default=100, help="item limit for the request, maximum is one hundred [default: %(default)s]")
    parser.add_argument('--offset', '-o', dest="offset", metavar="number", action="store", type=int, default=0, help="results offset [default: %(default)s]")
    parser.add_argument('--sort', '-s', dest="sortOrder", metavar="ascending/descending", action="store", default="descending", help="download videos in order of ID (ascending, descending) [default: %(default)s]")
    parser.add_argument('--thumbnail', '-t', dest="thumbnail", action="store_true", default=False, help="download thumbnail file [default: %(default)s]")
    parser.add_argument('--verify-basic', '-b', dest="verifyBasic", action="store_true", default=False, help="quick, basic download verification [default: %(default)s]")
    parser.add_argument('--verify-complete', '-c', dest="verifyComplete", action="store_true", default=False, help="full download verification [default: %(default)s]")
    parser.add_argument('--verify-threads', '-T', dest="verifyThreads", metavar="integer", action="store", type=int, default=0, help="threads allocated for verification, zero for maximum [default: %(default)s]")
    parser.add_argument('--verify-retry', '-R', dest="verifyRetry", metavar="integer", action="store", type=int, default=0, help="how many times to retry on failed verification, maximum two [default: %(default)s]")
    parser.add_argument('--output', '-O', dest="outputDirectory", metavar="directory", action="store", help="output directory [default: working directory]")
    parser.add_argument('--codify-filename', '-C', dest="codifiedFilename", action="store_true", default=False, help="codify filename to make manipulation potentially easier [default: working directory]") 
    parser.add_argument('--download-record', '-r', metavar="filename", dest="downloadRecordFile", action="store", help="maintain a record of downloaded videos and skip repeat downloads, provide filename")
    parser.add_argument('--log', '-g', dest="log", action="store_true", default=False, help="write to log file [default: %(default)s]")
    parser.add_argument('--truncate', '-k', dest="truncateThreshold", metavar="integer", action="store", type=int, default=70, help="truncate show descriptions [default: %(default)s]")
    #parser.add_argument('--duder', '-d', dest="duderMode", action="store_true", default=False, help="activate duder mode [default: %(default)s]")
    parser.add_argument('--filter', '-F', dest="filter", action="store_true", default=False, help="provide with filter options")
    filterArgs = parser.add_argument_group("Filter options", "Used in conjunction with --filter")
    filterArgs.add_argument('--phrase', dest="filterPhrase", metavar="phrase", action="store", help="search video titles with a word or phrase")
    filterArgs.add_argument('--phrase-exclude', dest="filterPhraseExclude", metavar="phrase", action="store", help="search video titles with a word or phrase excluded")
    filterArgs.add_argument('--show-id', dest="filterShowID", metavar="ID", action="store", type=int, help="show ID (see --list-shows)")
    filterArgs.add_argument('--video-id', dest="filterVideoID", metavar="ID", action="store", type=int, help="video ID")
    filterArgs.add_argument('--minimum-length', dest="filterMinimumLength", metavar="seconds", action="store", type=int, help="minimum video length")
    filterArgs.add_argument('--maximum-length', dest="filterMaximumLength", metavar="seconds", action="store", type=int, help="maximum video length")
    
    onScreenLog("GiantBombDL v1 (6-1-2021)", COLOURS["white"])
    
    # Check availability of external programs
    checkCapability()
    
    global args
    args = parser.parse_args()
    if validateArgs() is False:
        return
    
    global rootDir   
    global truncateThreshold
    truncateThreshold = args.truncateThreshold
    
    # No arguments
    if len(sys.argv) < 2:
        onScreenLog("Error: no arguments provided", COLOURS["lightRed"])
        onScreenLog("See --help", COLOURS["lightRed"])
        sys.exit()
    
    loadConfig()
    
    if args.showIDs:
        listShows()
        sys.exit()
    
    if args.filterPhrase or args.filterPhraseExclude:
        args.filterVideoID = None
    else:
        if args.filterShowID:
            args.filterVideoID = None
        if args.filterVideoID:
            args.filterShowID = None
    
    download()
    
rootDir = os.getcwd()

# Disable colour in Windows command prompt
if os.name == "nt":
    colourEnabled = False

init()
