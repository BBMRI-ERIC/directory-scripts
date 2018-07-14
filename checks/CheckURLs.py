from typing import List
import re
import urllib
import pprint
import ssl

from yapsy.IPlugin import IPlugin
from customwarnings import DataCheckWarningLevel,DataCheckWarning

pp = pprint.PrettyPrinter(indent=4)

def testURL (URL : str, URLErrorWarning : DataCheckWarning) -> List[DataCheckWarning]:
	warnings = []
	test_URL = False
	if test_URL:
		print("Testing URL " + URL, end=' ')
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
		except Exception as e:
			print(" -> unknown exception")
			raise
		if URL_well_formatted and not (URL_ret_code >= 200 and URL_ret_code < 300):
			URLErrorWarning.message += " returns non-success code (" + URL + " returns HTTP error code " + str(URL_ret_code) + ")"
			warnings.append(URLErrorWarning)
			print(" -> HTTP error code " + str(URL_ret_code))
		else:
			if URL_well_formatted:
				print(" -> OK")

	return warnings


class CheckURLs(IPlugin):
	def check(self, dir):
		warnings = []
		test_URL = True
		print("Testing biobank URLs")
		for biobank in dir.getBiobanks():
			if not 'url' in biobank or re.search('^\s*$', biobank['url']):
				warning = DataCheckWarning("", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.WARNING, biobank['id'], "Missing URL for")
				warnings.append(warning)
			else:
				URLwarnings = testURL(biobank['url'], 
						DataCheckWarning("", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.ERROR, biobank['id'], "Biobank URL for biobank")
						)
				warnings += URLwarnings

		print("Testing collection URLs")
		for collection in dir.getBiobanks():
			if not 'data_access_uri' in collection or re.search('^\s*$', collection['data_access_uri']):
				warning = DataCheckWarning("", dir.getBiobankNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], "Missing data access URL for collection")
				warnings.append(warning)
			else:
				URLwarnings = testURL(collection['data_access_uri'],
						DataCheckWarning("", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], "Data access URL for collection")
						)
				warnings += URLwarnings

			if not 'sample_access_uri' in collection or re.search('^\s*$', collection['sample_access_uri']):
				warning = DataCheckWarning("", dir.getBiobankNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], "Missing sample access URL for collection")
				warnings.append(warning)
			else:
				URLwarnings = testURL(collection['sample_access_uri'],
						DataCheckWarning("", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], "Sample access URL for collection")
						)
				warnings += URLwarnings

		return warnings
