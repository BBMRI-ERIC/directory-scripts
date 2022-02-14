#!/usr/bin/python3
# vim:ts=4:sw=4:tw=0:et

from builtins import *

import logging as log
import re

import roman

cancer_diag_ranges = ['C00-D49', 'C00-C97', 'C00-C75', 'C00-C14', 'C15-C26', 'C30-C39', 'C40-C41', 'C43-C44', 'C45-C49',
                      'C51-C58', 'C60-C63', 'C64-C68', 'C69-C72', 'C73-C75', 'C76-C80', 'C81-C96', 'D00-D09', 
                      'D37-D48', 'C50-C50', 'C97-C97']

cancer_chapters_roman = list(map(roman.toRoman, range(1, 23)))  # chapter 22 added in 2020

obesity_diag_ranges = ['E65-E68']


class ICD10CodesHelper:

   def isCancerCode(code : str) -> bool:
      if code in ['C7A', 'C7B', 'D3A']:
         return True
      m = re.search(r'^(?P<block>[A-Z])(?P<code>\d{1,2})(\.(?P<subcode>\d+))?$', code)
      if m:
         log.debug("ICD-10 block detected: %s, code: %s, subcode %s" % (m.group('block'), m.group('code'), m.group('subcode')))
         if m.group('block') == 'C' or (m.group('block') == 'D' and (0 <= int(m.group('code')) <= 9 or 37 <= int(m.group('code')) <= 48)):
            return True
         else:
            return False

      # now we deal with ranges
      m = re.search(r'^(?P<blockA>[A-Z]\d{1,2}(\.\d+)?)-(?P<blockB>[A-Z]\d{1,2}(\.\d+)?)$', code)
      if m:
         log.debug("ICD-10 range of blocks detected: from %s to %s" % (m.group('blockA'), m.group('blockB')))
         if ICD10CodesHelper.isCancerCode(m.group('blockA')) or ICD10CodesHelper.isCancerCode(m.group('blockB')):
             return True
         else:
             return False

      # this is unparsable
      return None

   def isCancerChapter(code : str) -> bool:
      if code not in cancer_chapters_roman:
         return None
      log.debug("ICD10 chapter detected: %s" % (code))
      if code == "II":
         return True
      else:
         return False

   def isObesityCode(code : str) -> bool:
      m = re.search(r'^(?P<block>[A-Z])(?P<code>\d{1,2})(\.(?P<subcode>\d+))?$', code)
      if m:
         log.debug("ICD-10 block detected: %s, code: %s, subcode %s" % (m.group('block'), m.group('code'), m.group('subcode')))
         if m.group('block') == 'E' and (int(m.group('code')) == 66):
            return True
         else:
            return False

      # now we deal with ranges
      if code in obesity_diag_ranges:
             return True
      else:
             return False

      # this is unparsable
      return None

   def isIBDLynchCode(code : str) -> bool: # Inflammatory Bowel Disease
      m = re.search(r'^(?P<block>[A-Z])(?P<code>\d{1,2})(\.(?P<subcode>\d+))?$', code)
      IBDLynchCode = False
      if m:
         log.debug("ICD-10 block detected: %s, code: %s, subcode %s" % (m.group('block'), m.group('code'), m.group('subcode')))
         if m.group('block') == 'K' and (int(m.group('code')) == 50 or int(m.group('code')) == 51 or int(m.group('code')) == 52):
                  IBDLynchCode = True
         return IBDLynchCode

   def isChronicPancreatitisDuctalCancerCode(code : str) -> bool:
      m = re.search(r'^(?P<block>[A-Z])(?P<code>\d{1,2})(\.(?P<subcode>\d+))?$', code)
      ChronicPancreatitisDuctalCancer = False
      if m:
         log.debug("ICD-10 block detected: %s, code: %s, subcode %s" % (m.group('block'), m.group('code'), m.group('subcode')))
         if m.group('block') == 'C' and (int(m.group('code')) == 25):
            if m.group('subcode') and (int(m.group('subcode')) == 3):
               ChronicPancreatitisDuctalCancer = True
            else: # NOTE: Do we accept code level entries?
               ChronicPancreatitisDuctalCancer = True
         if m.group('block') == 'D' and (m.group('code') == '01'):
            if m.group('subcode') and (int(m.group('subcode')) == 7):
               ChronicPancreatitisDuctalCancer = True
         elif m.group('block') == 'K' and (int(m.group('code')) == 86):
            if m.group('subcode') and ((int(m.group('subcode')) == 0 or int(m.group('subcode')) == 1)):
               ChronicPancreatitisDuctalCancer = True
            else: # NOTE: Do we accept code level entries?
               ChronicPancreatitisDuctalCancer = True

         return ChronicPancreatitisDuctalCancer


   def isCholangiocarcinomaCode(code : str) -> bool:
      m = re.search(r'^(?P<block>[A-Z])(?P<code>\d{1,2})(\.(?P<subcode>\d+))?$', code)
      if m:
         log.debug("ICD-10 block detected: %s, code: %s, subcode %s" % (m.group('block'), m.group('code'), m.group('subcode')))
         if m.group('block') == 'C' and (int(m.group('code')) == 22):
            if m.group('subcode') and (int(m.group('subcode')) == 0 or int(m.group('subcode')) == 1):
               return True
            #else: # NOTE: Do we accept code level entries?
               #return True
         else:
            return False