from typing import List
import re
import urllib

from yapsy.IPlugin import IPlugin
from customwarnings import WarningLevel,Warning

def testURL (URL : str, URLErrorWarning : Warning, HTTPErrorWarning : Warning) -> List[Warning]:
	warnings = []
	test_URL = True
	if test_URL:
		print("Testing URL " + URL)
		try: 
			URL_ret_code = urllib.request.urlopen(URL).getcode()
			URL_well_formatted = True
		except urllib.error.HTTPError as e:
			URL_ret_code = e.code
			URL_well_formatted = True
		except urllib.error.URLError as e:
			warnings.append(URLErrorWarning)
			URL_well_formatted = False
		except ValueError as e:
			warnings.append(URLErrorWarning)
			URL_well_formatted = False
		if URL_well_formatted and not (URL_ret_code >= 200 and URL_ret_code < 300):
			warnings.append(HTTPErrorWarning)
	return warnings


class CheckURLs(IPlugin):
	def check(self, dir):
		warnings = []
		test_URL = True
		for biobank in dir.getBiobanks():
			if not 'url' in biobank or re.search('^\s*$', biobank['url']):
				warning = Warning("", dir.getBiobankNN(biobank['id']), WarningLevel.WARNING, "Missing URL for " + biobank['id'])
				warnings.append(warning)
			else:
				URLwarnings = testURL(biobank['url'], 
						Warning("", dir.getBiobankNN(biobank['id']), WarningLevel.ERROR, "Biobank URL for biobank " + biobank['id'] + " is misformatted"), 
						Warning("", dir.getBiobankNN(biobank['id']), WarningLevel.ERROR, "Biobank URL for biobank " + biobank['id'] + " returns non-success return code")
						)
				if len(URLwarnings) > 0:
					warnings.append(URLwarnings)

		for collection in dir.getBiobanks():
			if not 'data_access_uri' in collection or re.search('^\s*$', collection['data_access_uri']):
				warning = Warning("", dir.getBiobankNN(collection['id']), WarningLevel.WARNING, "Missing URL for " + collection['id'])
				warnings.append(warning)
			else:
				URLwarnings = testURL(collection['data_access_uri'],
						Warning("", dir.getCollectionNN(collection['id']), WarningLevel.ERROR, "Data access URL for collection " + collection['id'] + " is misformatted"),
						Warning("", dir.getCollectionNN(collection['id']), WarningLevel.ERROR, "Data access URL for collection " + collection['id'] + " returns non-success return code")
						)
				if len(URLwarnings) > 0:
					warnings.append(URLwarnings)

			if not 'sample_access_uri' in collection or re.search('^\s*$', collection['sample_access_uri']):
				warning = Warning("", dir.getBiobankNN(collection['id']), WarningLevel.WARNING, "Missing URL for " + collection['id'])
				warnings.append(warning)
			else:
				URLwarnings = testURL(collection['sample_access_uri'],
						Warning("", dir.getCollectionNN(collection['id']), WarningLevel.ERROR, "Sample access URL for collection " + collection['id'] + " is misformatted"),
						Warning("", dir.getCollectionNN(collection['id']), WarningLevel.ERROR, "Sample access URL for collection " + collection['id'] + " returns non-success return code")
						)

		return warnings
