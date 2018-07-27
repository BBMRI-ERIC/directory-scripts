from typing import List
import re
import urllib
import pprint
import ssl
import logging as log

# this is ugly and only for assertive programming
import __main__ 

from yapsy.IPlugin import IPlugin
from customwarnings import DataCheckWarningLevel,DataCheckWarning

pp = pprint.PrettyPrinter(indent=4)

def testURL (URL : str, URLErrorWarning : DataCheckWarning) -> List[DataCheckWarning]:
	warnings = []
	print("Testing URL " + URL, end=' ')
	URL_connection_reset = False
	try: 
		URL_ret_code = urllib.request.urlopen(URL).getcode()
		URL_well_formatted = True
	except urllib.error.HTTPError as e:
		URL_ret_code = e.code
		URL_well_formatted = True
	except urllib.error.URLError as e:
		URLErrorWarning.message += " access was not successful (accessing " + URL + " returns " + str(e) + ")"
		warnings.append(URLErrorWarning)
		URL_well_formatted = False
		print(" -> URL not reachable (urllib.error.URLError)")
	except ValueError as e:
		URLErrorWarning.message += " is misformatted (" + URL + ")"
		warnings.append(URLErrorWarning)
		URL_well_formatted = False
		print(" -> malformatted URL (ValueError)")
	except ConnectionResetError as e:
		URLErrorWarning.message += " connection reset by peer (" + URL + ")"
		warnings.append(URLErrorWarning)
		URL_well_formatted = True
		URL_connection_reset = True
		print(" -> connection reset by peer")
	except Exception as e:
		print(" -> unknown exception")
		raise

	if URL_well_formatted and not URL_connection_reset and not (URL_ret_code >= 200 and URL_ret_code < 300):
		URLErrorWarning.message += " returns non-success code (" + URL + " returns HTTP error code " + str(URL_ret_code) + ")"
		warnings.append(URLErrorWarning)
		print(" -> HTTP error code " + str(URL_ret_code))
	else:
		if URL_well_formatted and not URL_connection_reset:
			print(" -> OK")

	return warnings


class CheckURLs(IPlugin):
	def check(self, dir, args):
		warnings = []
		log.info("Running URL checks (CheckURLs)")
		assert 'URLs' in __main__.remoteCheckList
		if 'URLs' in args.disableChecksRemote:
			return warnings
		print("Testing biobank URLs")
		for biobank in dir.getBiobanks():
			if not 'url' in biobank or re.search('^\s*$', biobank['url']):
				warning = DataCheckWarning(self.__class__.__name__, "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.WARNING, biobank['id'], "Missing URL for")
				warnings.append(warning)
			else:
				URLwarnings = testURL(biobank['url'], 
						DataCheckWarning(self.__class__.__name__, "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.ERROR, biobank['id'], "Biobank URL for biobank")
						)
				warnings += URLwarnings

		print("Testing collection URLs")
		for collection in dir.getBiobanks():
			# non-existence of access URIs is tested in the access policy checks - here we only check validity of the URL if it exists
			if 'data_access_uri' in collection and not re.search('^\s*$', collection['data_access_uri']):
				URLwarnings = testURL(collection['data_access_uri'],
						DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], "Data access URL for collection")
						)
				warnings += URLwarnings

			if 'sample_access_uri' in collection and not re.search('^\s*$', collection['sample_access_uri']):
				URLwarnings = testURL(collection['sample_access_uri'],
						DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], "Sample access URL for collection")
						)
				warnings += URLwarnings
			if 'image_access_uri' in collection and not re.search('^\s*$', collection['image_access_uri']):
				URLwarnings = testURL(collection['image_access_uri'],
						DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], "Image access URL for collection")
						)
				warnings += URLwarnings

		return warnings
