## Amazon S3 manager
## Author: Michal Ludvig <michal@logix.cz>
##         http://www.logix.cz/michal
## License: GPL Version 2

import os
import time
import re
import string
import random
import rfc822
try:
	from hashlib import md5, sha1
except ImportError:
	from md5 import md5
	import sha as sha1
import hmac
import base64
import errno

from logging import debug, info, warning, error

import Config
import Exceptions

try:
	import xml.etree.ElementTree as ET
except ImportError:
	import elementtree.ElementTree as ET
from xml.parsers.expat import ExpatError

__all__ = []
def parseNodes(nodes):
	## WARNING: Ignores text nodes from mixed xml/text.
	## For instance <tag1>some text<tag2>other text</tag2></tag1>
	## will be ignore "some text" node
	retval = []
	for node in nodes:
		retval_item = {}
		for child in node.getchildren():
			name = child.tag
			if child.getchildren():
				retval_item[name] = parseNodes([child])
			else:
				retval_item[name] = node.findtext(".//%s" % child.tag)
		retval.append(retval_item)
	return retval
__all__.append("parseNodes")

def stripNameSpace(xml):
	"""
	removeNameSpace(xml) -- remove top-level AWS namespace
	"""
	r = re.compile('^(<?[^>]+?>\s?)(<\w+) xmlns=[\'"](http://[^\'"]+)[\'"](.*)', re.MULTILINE)
	if r.match(xml):
		xmlns = r.match(xml).groups()[2]
		xml = r.sub("\\1\\2\\4", xml)
	else:
		xmlns = None
	return xml, xmlns
__all__.append("stripNameSpace")

def getTreeFromXml(xml):
	xml, xmlns = stripNameSpace(xml)
	try:
		tree = ET.fromstring(xml)
		if xmlns:
			tree.attrib['xmlns'] = xmlns
		return tree
	except ExpatError, e:
		error(e)
		raise Exceptions.ParameterError("Bucket contains invalid filenames. Please run: s3cmd fixbucket s3://your-bucket/")
__all__.append("getTreeFromXml")
	
def getListFromXml(xml, node):
	tree = getTreeFromXml(xml)
	nodes = tree.findall('.//%s' % (node))
	return parseNodes(nodes)
__all__.append("getListFromXml")

def getDictFromTree(tree):
	ret_dict = {}
	for child in tree.getchildren():
		if child.getchildren():
			## Complex-type child. Recurse
			content = getDictFromTree(child)
		else:
			content = child.text
		if ret_dict.has_key(child.tag):
			if not type(ret_dict[child.tag]) == list:
				ret_dict[child.tag] = [ret_dict[child.tag]]
			ret_dict[child.tag].append(content or "")
		else:
			ret_dict[child.tag] = content or ""
	return ret_dict
__all__.append("getDictFromTree")

def getTextFromXml(xml, xpath):
	tree = getTreeFromXml(xml)
	if tree.tag.endswith(xpath):
		return tree.text
	else:
		return tree.findtext(xpath)
__all__.append("getTextFromXml")

def getRootTagName(xml):
	tree = getTreeFromXml(xml)
	return tree.tag
__all__.append("getRootTagName")

def xmlTextNode(tag_name, text):
	el = ET.Element(tag_name)
	el.text = unicode(text)
	return el
__all__.append("xmlTextNode")

def appendXmlTextNode(tag_name, text, parent):
	"""
	Creates a new <tag_name> Node and sets
	its content to 'text'. Then appends the
	created Node to 'parent' element if given.
	Returns the newly created Node.
	"""
	el = xmlTextNode(tag_name, text)
	parent.append(el)
	return el
__all__.append("appendXmlTextNode")

def dateS3toPython(date):
	date = re.compile("(\.\d*)?Z").sub(".000Z", date)
	return time.strptime(date, "%Y-%m-%dT%H:%M:%S.000Z")
__all__.append("dateS3toPython")

def dateS3toUnix(date):
	## FIXME: This should be timezone-aware.
	## Currently the argument to strptime() is GMT but mktime() 
	## treats it as "localtime". Anyway...
	return time.mktime(dateS3toPython(date))
__all__.append("dateS3toUnix")

def dateRFC822toPython(date):
	return rfc822.parsedate(date)
__all__.append("dateRFC822toPython")

def dateRFC822toUnix(date):
	return time.mktime(dateRFC822toPython(date))
__all__.append("dateRFC822toUnix")

def formatSize(size, human_readable = False, floating_point = False):
	size = floating_point and float(size) or int(size)
	if human_readable:
		coeffs = ['k', 'M', 'G', 'T']
		coeff = ""
		while size > 2048:
			size /= 1024
			coeff = coeffs.pop(0)
		return (size, coeff)
	else:
		return (size, "")
__all__.append("formatSize")

def formatDateTime(s3timestamp):
	return time.strftime("%Y-%m-%d %H:%M", dateS3toPython(s3timestamp))
__all__.append("formatDateTime")

def convertTupleListToDict(list):
	retval = {}
	for tuple in list:
		retval[tuple[0]] = tuple[1]
	return retval
__all__.append("convertTupleListToDict")

_rnd_chars = string.ascii_letters+string.digits
_rnd_chars_len = len(_rnd_chars)
def rndstr(len):
	retval = ""
	while len > 0:
		retval += _rnd_chars[random.randint(0, _rnd_chars_len-1)]
		len -= 1
	return retval
__all__.append("rndstr")

def mktmpsomething(prefix, randchars, createfunc):
	old_umask = os.umask(0077)
	tries = 5
	while tries > 0:
		dirname = prefix + rndstr(randchars)
		try:
			createfunc(dirname)
			break
		except OSError, e:
			if e.errno != errno.EEXIST:
				os.umask(old_umask)
				raise
		tries -= 1

	os.umask(old_umask)
	return dirname
__all__.append("mktmpsomething")

def mktmpdir(prefix = "/tmp/tmpdir-", randchars = 10):
	return mktmpsomething(prefix, randchars, os.mkdir)
__all__.append("mktmpdir")

def mktmpfile(prefix = "/tmp/tmpfile-", randchars = 20):
	createfunc = lambda filename : os.close(os.open(filename, os.O_CREAT | os.O_EXCL))
	return mktmpsomething(prefix, randchars, createfunc)
__all__.append("mktmpfile")

def hash_file_md5(filename):
	h = md5()
	f = open(filename, "rb")
	while True:
		# Hash 32kB chunks
		data = f.read(32*1024)
		if not data:
			break
		h.update(data)
	f.close()
	return h.hexdigest()
__all__.append("hash_file_md5")

def mkdir_with_parents(dir_name):
	"""
	mkdir_with_parents(dst_dir)
	
	Create directory 'dir_name' with all parent directories

	Returns True on success, False otherwise.
	"""
	pathmembers = dir_name.split(os.sep)
	tmp_stack = []
	while pathmembers and not os.path.isdir(os.sep.join(pathmembers)):
		tmp_stack.append(pathmembers.pop())
	while tmp_stack:
		pathmembers.append(tmp_stack.pop())
		cur_dir = os.sep.join(pathmembers)
		try:
			debug("mkdir(%s)" % cur_dir)
			os.mkdir(cur_dir)
		except (OSError, IOError), e:
			warning("%s: can not make directory: %s" % (cur_dir, e.strerror))
			return False
		except Exception, e:
			warning("%s: %s" % (cur_dir, e))
			return False
	return True
__all__.append("mkdir_with_parents")

def unicodise(string, encoding = None, errors = "replace"):
	"""
	Convert 'string' to Unicode or raise an exception.
	"""

	if not encoding:
		encoding = Config.Config().encoding

	if type(string) == unicode:
		return string
	debug("Unicodising %r using %s" % (string, encoding))
	try:
		return string.decode(encoding, errors)
	except UnicodeDecodeError:
		raise UnicodeDecodeError("Conversion to unicode failed: %r" % string)
__all__.append("unicodise")

def deunicodise(string, encoding = None, errors = "replace"):
	"""
	Convert unicode 'string' to <type str>, by default replacing
	all invalid characters with '?' or raise an exception.
	"""

	if not encoding:
		encoding = Config.Config().encoding

	if type(string) != unicode:
		return str(string)
	debug("DeUnicodising %r using %s" % (string, encoding))
	try:
		return string.encode(encoding, errors)
	except UnicodeEncodeError:
		raise UnicodeEncodeError("Conversion from unicode failed: %r" % string)
__all__.append("deunicodise")

def unicodise_safe(string, encoding = None):
	"""
	Convert 'string' to Unicode according to current encoding 
	and replace all invalid characters with '?'
	"""

	return unicodise(deunicodise(string, encoding), encoding).replace(u'\ufffd', '?')
__all__.append("unicodise_safe")

def replace_nonprintables(string):
	"""
	replace_nonprintables(string)

	Replaces all non-printable characters 'ch' in 'string'
	where ord(ch) <= 26 with ^@, ^A, ... ^Z
	"""
	new_string = ""
	modified = 0
	for c in string:
		o = ord(c)
		if (o <= 31):
			new_string += "^" + chr(ord('@') + o)
			modified += 1
		elif (o == 127):
			new_string += "^?"
			modified += 1
		else:
			new_string += c
	if modified and Config.Config().urlencoding_mode != "fixbucket":
		warning("%d non-printable characters replaced in: %s" % (modified, new_string))
	return new_string
__all__.append("replace_nonprintables")

def sign_string(string_to_sign):
	#debug("string_to_sign: %s" % string_to_sign)
	signature = base64.encodestring(hmac.new(Config.Config().secret_key, string_to_sign, sha1).digest()).strip()
	#debug("signature: %s" % signature)
	return signature
__all__.append("sign_string")

def check_bucket_name(bucket, dns_strict = True):
	if dns_strict:
		invalid = re.search("([^a-z0-9\.-])", bucket)
		if invalid:
			raise Exceptions.ParameterError("Bucket name '%s' contains disallowed character '%s'. The only supported ones are: lowercase us-ascii letters (a-z), digits (0-9), dot (.) and hyphen (-)." % (bucket, invalid.groups()[0]))
	else:
		invalid = re.search("([^A-Za-z0-9\._-])", bucket)
		if invalid:
			raise Exceptions.ParameterError("Bucket name '%s' contains disallowed character '%s'. The only supported ones are: us-ascii letters (a-z, A-Z), digits (0-9), dot (.), hyphen (-) and underscore (_)." % (bucket, invalid.groups()[0]))

	if len(bucket) < 3:
		raise Exceptions.ParameterError("Bucket name '%s' is too short (min 3 characters)" % bucket)
	if len(bucket) > 255:
		raise Exceptions.ParameterError("Bucket name '%s' is too long (max 255 characters)" % bucket)
	if dns_strict:
		if len(bucket) > 63:
			raise Exceptions.ParameterError("Bucket name '%s' is too long (max 63 characters)" % bucket)
		if re.search("-\.", bucket):
			raise Exceptions.ParameterError("Bucket name '%s' must not contain sequence '-.' for DNS compatibility" % bucket)
		if re.search("\.\.", bucket):
			raise Exceptions.ParameterError("Bucket name '%s' must not contain sequence '..' for DNS compatibility" % bucket)
		if not re.search("^[0-9a-z]", bucket):
			raise Exceptions.ParameterError("Bucket name '%s' must start with a letter or a digit" % bucket)
		if not re.search("[0-9a-z]$", bucket):
			raise Exceptions.ParameterError("Bucket name '%s' must end with a letter or a digit" % bucket)
	return True
__all__.append("check_bucket_name")

def check_bucket_name_dns_conformity(bucket):
	try:
		return check_bucket_name(bucket, dns_strict = True)
	except Exceptions.ParameterError:
		return False
__all__.append("check_bucket_name_dns_conformity")

def getBucketFromHostname(hostname):
	"""
	bucket, success = getBucketFromHostname(hostname)

	Only works for hostnames derived from bucket names
	using Config.host_bucket pattern.

	Returns bucket name and a boolean success flag.
	"""

	# Create RE pattern from Config.host_bucket
	pattern = Config.Config().host_bucket % { 'bucket' : '(?P<bucket>.*)' }
	m = re.match(pattern, hostname)
	if not m:
		return (hostname, False)
	return m.groups()[0], True
__all__.append("getBucketFromHostname")

def getHostnameFromBucket(bucket):
	return Config.Config().host_bucket % { 'bucket' : bucket }
__all__.append("getHostnameFromBucket")
