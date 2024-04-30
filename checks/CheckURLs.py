# vim:ts=8:sw=8:tw=0:noet

from typing import List
import re
import urllib
import pprint
import ssl
import certifi
import logging as log
import os

# this is ugly and only for assertive programming
import __main__ 

from yapsy.IPlugin import IPlugin
from customwarnings import DataCheckWarningLevel,DataCheckWarning,DataCheckEntityType

from diskcache import Cache

pp = pprint.PrettyPrinter(indent=4)

cache = None

def testURL (URL : str, URLErrorWarning : DataCheckWarning) -> List[DataCheckWarning]:
	warnings = []
	logString = "Testing URL " + URL
	URL_connection_reset = False
	global cache

	if(URL in cache):
		(warnings, logString) = cache[URL]
	else:
		if(not re.search('^(http|https):', URL, re.IGNORECASE)):
			URLErrorWarning.message += ' (' + URL + ') does not start with http or https'
			warnings.append(URLErrorWarning)
			logString += " -> URL does not start with http or https"
		else:
			try: 
				URL_ret_code = urllib.request.urlopen(URL).getcode()
				URL_well_formatted = True
			except urllib.error.HTTPError as e:
				URL_ret_code = e.code
				URL_well_formatted = True
			except urllib.error.URLError as e:
				URLErrorWarning.message += " was not accessed successfully (accessing " + URL + " returns " + str(e) + ")"
				warnings.append(URLErrorWarning)
				URL_well_formatted = False
				logString += " -> URL not reachable (urllib.error.URLError)"
			except ValueError as e:
				URLErrorWarning.message += " is misformatted (" + URL + ")"
				warnings.append(URLErrorWarning)
				URL_well_formatted = False
				logString += " -> malformatted URL (ValueError)"
			except ConnectionError as e:
				cause = "failed"
				if isinstance(e, ConnectionAbortedError):
					cause = "aborted by peer"
				elif isinstance(e, ConnectionRefusedError):
					cause = "refused by peer"
				elif isinstance(e, ConnectionResetError):
					cause = "reset by peer"
				URLErrorWarning.message += " produced connection %s (%s)" % (cause, URL)
				warnings.append(URLErrorWarning)
				URL_well_formatted = True
				URL_connection_reset = True
				logString += " -> connection " + cause
			except Exception as e:
				logString += " -> unknown exception"
				log.info(logString)
				raise
			
			if URL_well_formatted and not URL_connection_reset and not (URL_ret_code >= 200 and URL_ret_code < 300):
				URLErrorWarning.message += " returns non-success code (" + URL + " returns HTTP error code " + str(URL_ret_code) + ")"
				warnings.append(URLErrorWarning)
				logString += " -> HTTP error code " + str(URL_ret_code)
			else:
				if URL_well_formatted and not URL_connection_reset:
					logString += " -> OK"
		cache[URL] = (warnings, logString)

	log.info(logString)
	return warnings

class CheckURLs(IPlugin):
	def check(self, dir, args):
		warnings = []
		log.info("Running URL checks (CheckURLs)")
		assert 'URLs' in __main__.remoteCheckList
		if 'URLs' in args.disableChecksRemote:
			return warnings

		cache_dir = 'data-check-cache/URLs'
		if not os.path.exists(cache_dir):
			os.makedirs(cache_dir)
		global cache
		cache = Cache(cache_dir)
		if 'URLs' in args.purgeCaches:
			cache.clear()
                
		log.info("Testing biobank URLs")
		for biobank in dir.getBiobanks():
			if not 'url' in biobank or re.search('^\s*$', biobank['url']):
				warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.WARNING, biobank['id'], DataCheckEntityType.BIOBANK, "Missing URL"))
			else:
				URLwarnings = testURL(biobank['url'], 
						DataCheckWarning(self.__class__.__name__, "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.ERROR, biobank['id'], DataCheckEntityType.BIOBANK, "Biobank URL")
						)
				warnings += URLwarnings

		log.info("Testing collection URLs")
		for collection in dir.getBiobanks():
			# non-existence of access URIs is tested in the access policy checks - here we only check validity of the URL if it exists
			if 'data_access_uri' in collection and not re.search('^\s*$', collection['data_access_uri']):
				URLwarnings = testURL(collection['data_access_uri'],
						DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "Data access URL for collection")
						)
				warnings += URLwarnings

			if 'sample_access_uri' in collection and not re.search('^\s*$', collection['sample_access_uri']):
				URLwarnings = testURL(collection['sample_access_uri'],
						DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "Sample access URL for collection")
						)
				warnings += URLwarnings
			if 'image_access_uri' in collection and not re.search('^\s*$', collection['image_access_uri']):
				URLwarnings = testURL(collection['image_access_uri'],
						DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "Image access URL for collection")
						)
				warnings += URLwarnings

		cache.close()
		return warnings
