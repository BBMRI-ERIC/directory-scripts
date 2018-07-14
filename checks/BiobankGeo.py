import re

from yapsy.IPlugin import IPlugin
from customwarnings import DataCheckWarningLevel,DataCheckWarning

from geopy.geocoders import Nominatim

class CheckBiobankGeo(IPlugin):
	def check(self, dir):
		geolocator = Nominatim()
		warnings = []
		# This is to be enabled for real runs.
		geoCodingEnabled = True
		for biobank in dir.getBiobanks():
			if 'latitude' in biobank and not re.search('^\s*$', biobank['latitude']) and 'longitude' in biobank and not re.search('^\s*$', biobank['longitude']):
				if re.search ('^-?\d+\.\d*$', biobank['latitude']) and re.search ('^-?\d+\.\d*$', biobank['longitude']):
					if geoCodingEnabled:
						print("Checking reverse geocoding for " + biobank['latitude'] + ", " + biobank['longitude'], end=' ')
						try:
							location = geolocator.reverse(biobank['latitude'] + ", " + biobank['longitude'])
							country_code = location.raw['address']['country_code']
							print(" -> OK")
							if (biobank['country']['id'] != "IARC" and country_code.upper() != biobank['country']['id']):
								warning = DataCheckWarning("", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.WARNING, biobank['id'], "Geolocation of the biobank is likely outside of its country; biobank seems to be in " + country_code.upper())
								warnings.append(warning)
						except Exception as e:
							print(" -> failed")
							warning = DataCheckWarning("", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.WARNING, biobank['id'], "Reverse geocoding of the biobank  location failed (" + str(e) + ")")
							warnings.append(warning)

				else:
					if not re.search ('^-?\d+\.\d*$', biobank['latitude']):
						warning = DataCheckWarning("", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.ERROR, biobank['id'], "Invalid biobank latitude: " + biobank['latitude'])
						warnings.append(warning)
					if not re.search ('^-?\d+\.\d*$', biobank['longitude']):
						warning = DataCheckWarning("", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.ERROR, biobank['id'], "Invalid biobank longitude: " + biobank['longitude'])
						warnings.append(warning)
			else:
				warning = DataCheckWarning("", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.INFO, biobank['id'], "Missing geographical coordinates")
				warnings.append(warning)


		return warnings
