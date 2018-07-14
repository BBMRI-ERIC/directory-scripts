import re

from yapsy.IPlugin import IPlugin
from customwarnings import DataCheckWarningLevel,DataCheckWarning

from geopy.geocoders import Nominatim

class CheckBiobankGeo(IPlugin):
	def check(self, dir):
		geolocator = Nominatim()
		warnings = []
		# This is to be enabled for real runs.
		geoCodingEnabled = False
		for biobank in dir.getBiobanks():
			if 'latitude' in biobank and not re.search('^\s*$', biobank['latitude']) and 'longitude' in biobank and not re.search('^\s*$', biobank['longitude']):
				if re.search ('^-?\d+\.\d*$', biobank['latitude']) and re.search ('^-?\d+\.\d*$', biobank['longitude']):
					if geoCodingEnabled:
						print("Checking reverse geocoding for " + biobank['latitude'] + ", " + biobank['longitude'])
						location = geolocator.reverse(biobank['latitude'] + ", " + biobank['longitude'])
						country_code = location.raw['address']['country_code']
						if (biobank['country']['id'] != "IARC" and country_code.upper() != biobank['country']['id']):
							warning = DataCheckWarning("", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.WARNING, "Geolocation of the biobank is likely outside of its country " + biobank['id'] + " seems to be in " + country_code.upper())
							warnings.append(warning)
				else:
					if not re.search ('^-?\d+\.\d*$', biobank['latitude']):
						warning = DataCheckWarning("", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.ERROR, "Invalid biobank latitude for " + biobank['id'] + ": " + biobank['latitude'])
						warnings.append(warning)
					if not re.search ('^-?\d+\.\d*$', biobank['longitude']):
						warning = DataCheckWarning("", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.ERROR, "Invalid biobank longitude for " + biobank['id'] + ": " + biobank['longitude'])
						warnings.append(warning)
			else:
				warning = DataCheckWarning("", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.INFO, "Missing geographical coordinates for " + biobank['id'])
				warnings.append(warning)


		return warnings
