#!/usr/bin/python -OO
# -*- coding: utf-8 -*-
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys
import os
import time, datetime
import re
import hashlib
import urllib2
import tempfile
import traceback
import random
import subprocess
import cStringIO as StringIO
import wikitools
import wikiUpload
import feedparser
import steam
from wikiUpload import wikiUploader

from botConfig import config
steam.set_api_key(config['steamAPI'])
config['runtime'] = {
	'rcid': -1,
	'onlinercid': -1,
	'wiki': None,
	'edits': 0,
	'regexes': {},
	'pages': {},
	'uploader': wikiUploader(config['username'], config['password'], config['api'])
}

def u(s):
	if type(s) is type(u''):
		return s
	if type(s) is type(''):
		try:
			return unicode(s)
		except:
			try:
				return unicode(s.decode('utf8'))
			except:
				try:
					return unicode(s.decode('windows-1252'))
				except:
					return unicode(s, errors='ignore')
	try:
		return unicode(s)
	except:
		try:
			return u(str(s))
		except:
			return s
class curry:
	def __init__(self, func, *args, **kwargs):
		self.func = func
		self.pending = args[:]
		self.kwargs = kwargs
	def __str__(self):
		if u(self.func) == u(regSub):
			return 'Regex' + u(self.pending)
		return u'<Curry of ' + u(self.func) + u'; args = ' + u(self.pending) + u'; kwargs = ' + u(self.kwargs) + u'>'
	def __repr__(self):
		return self.__str__()
	def __call__(self, *args, **kwargs):
		if kwargs and self.kwargs:
			kw = self.kwargs.copy()
			kw.update(kwargs)
		else:
			kw = kwargs or self.kwargs
		return self.func(*(self.pending + args), **kw)
def getTempFilename():
	global config
	f = tempfile.mkstemp(prefix=config['prefix'])
	os.close(f[0]) # Damn you Python I just want a filename
	return f[1]

def wiki():
	global config
	if config['runtime']['wiki'] is None:
		config['runtime']['wiki'] = wikitools.wiki.Wiki(config['api'])
		print 'Logging in as', config['username'], '...'
		config['runtime']['wiki'].login(config['username'], config['password'])
		try:
			config['runtime']['onlinercid'] = int(u(wikitools.page.Page(wiki(), config['pages']['rcid']).getWikiText()).strip())
			config['runtime']['rcid'] = config['runtime']['onlinercid']
		except:
			error('Couldn\'t read RCID.')
		print 'Logged in.'
	return config['runtime']['wiki']
def page(p):
	global config
	if type(p) in (type(''), type(u'')):
		p = u(p)
		if p not in config['runtime']['pages']:
			config['runtime']['pages'][p] = wikitools.page.Page(wiki(), p, followRedir=False)
		return config['runtime']['pages'][p]
	# Else, it is a page object
	title = u(p.title)
	if title not in config['runtime']['pages']:
		config['runtime']['pages'][title] = p
	return config['runtime']['pages'][title]
def getSummary(summary):
	summary = u(summary)
	while len(summary) > 250:
		if summary.find(u' ') == -1:
			summary = summary[:summary.rfind(u' ')] + u'...'
		else:
			summary = summary[:247] + u'...'
	return summary
def editPage(p, content, summary=u'', minor=True, bot=True, nocreate=True):
	global config
	summary = getSummary(summary)
	try:
		if nocreate:
			result = page(p).edit(u(content), summary=summary, minor=minor, bot=bot, nocreate=nocreate)
		else:
			result = page(p).edit(u(content), summary=summary, minor=minor, bot=bot)
	except:
		warning('Couldn\'t edit', p)
		return None
	try:
		if result['edit']['result']:
			config['runtime']['edits'] += 1
	except:
		warning('Couldn\'t edit', p)
	return result
def deletePage(p, summary=False):
	if summary:
		summary = getSummary(summary)
	return page(p).delete(summary)
def uploadFile(filename, destfile, pagecontent='', license='', overwrite=False, reupload=False):
	global config
	return config['runtime']['uploader'].upload(filename, destfile, pagecontent, license, overwrite=overwrite, reupload=reupload)
def updateRCID():
	if abs(config['runtime']['rcid'] - config['runtime']['onlinercid']) >= config['rcidrate']:
		print 'Updating last RCID...'
		try:
			editPage(config['pages']['rcid'], config['runtime']['rcid'], summary=u'Updated Recent Changes log position to ' + u(config['runtime']['rcid']))
			config['runtime']['onlinercid'] = config['runtime']['rcid']
		except:
			warning('Couldn\'t update RCID.')
def updateEditCount(force=False):
	global config
	if not config['runtime']['edits']:
		return
	if not force and random.randint(0, 40) != 7:
		return
	try:
		editPage(config['pages']['editcount'], int(wikitools.api.APIRequest(wiki(), {
			'action': 'query',
			'list': 'users',
			'usprop': 'editcount',
			'ususers': config['username']
		}).query(querycontinue=False)['query']['users'][0]['editcount']) + 1, summary=u'Updated edit count.')
		config['runtime']['edits'] = 0
	except:
		warning('Couldn\'t update edit count.')

def compileRegex(regex, flags=re.IGNORECASE):
	global config
	regex = u(regex)
	if regex in config['runtime']['regexes']:
		return config['runtime']['regexes'][regex]
	config['runtime']['regexes'][regex] = re.compile(regex, flags)
	return config['runtime']['regexes'][regex]

def warning(*info):
	s = []
	print info
	import traceback
	traceback.print_exc()
def error(*info):
	warning(*info)
	sys.exit(1)

def setFilterName(f, name):
	name = u(name)
	f.__unicode__ = lambda: name
	f.__str__ = lambda: name.encode('utf8')
	f.filterName = name
	return f
class link:
	def __init__(self, content):
		content = u(content)
		self.joined = False
		self.setBody(content)
		self.setType(u'unknown')
		self.setLabel(None)
		self.setLink(u'')
		self.joined = False
		if len(content) > 2:
			if content[:2] == u'[[' and content[-2:] == u']]':
				split = content[2:-2].split(u'|')
				if len(split) in (1, 2):
					self.setType(u'internal')
					lnk = split[0]
					if lnk.find(u':') == -1:
						lnk = lnk.replace(u'_', u' ')
					self.setLink(lnk)
					if len(split) == 2:
						self.setLabel(split[1])
					else:
						self.setLabel(split[0])
						self.joined = True
			elif content[0] == u'[' and content[-1] == u']':
				split = content[1:-1].split(u' ', 1)
				self.setType(u'external')
				self.setLink(split[0])
				if len(split) == 2:
					self.setLabel(split[1])
				else:
					self.setLabel(None)
	def getType(self):
		return u(self.kind)
	def getBody(self):
		return u(self.body)
	def getLink(self):
		return u(self.link)
	def getLabel(self):
		if self.label is None:
			return None
		if self.joined:
			return self.getLink()
		return u(self.label)
	def setType(self, kind):
		self.kind = u(kind)
	def setBody(self, body):
		self.body = u(body)
	def setLink(self, link):
		self.link = u(link)
		if self.joined:
			self.label = u(link)
	def setLabel(self, label):
		if label is None:
			self.label = None
		else:
			self.label = u(label)
		if self.joined:
			self.link = u(label)
	def __str__(self):
		return self.__unicode__()
	def __repr__(self):
		return u'<Link-' + self.getType() + u': ' + self.__unicode__() + u'>'
	def __unicode__(self):
		label = self.getLabel()
		tmpLink = self.getLink()
		if self.getType() == u'internal':
			tmpLink2 = tmpLink.replace(u'_', u' ')
			if label in (tmpLink2, tmpLink) or (label and tmpLink and (label[0].lower() == tmpLink[0].lower() and tmpLink[1:] == label[1:]) or (label[0].lower() == tmpLink2[0].lower() and tmpLink2[1:] == label[1:])):
				return u'[[' + label + u']]'
			elif tmpLink and label and len(label) > len(tmpLink) and (label.lower().find(tmpLink2.lower()) == 0 or label.lower().find(tmpLink.lower()) == 0):
				index = max(label.lower().find(tmpLink2.lower()), label.lower().find(tmpLink.lower()))
				badchars = (u' ', u'_')
				nobadchars = True
				for c in badchars:
					if label[:index].find(c) != -1 or label[index+len(tmpLink):].find(c) != -1:
						nobadchars = False
				if nobadchars:
					return label[:index] + u(link(u'[[' + tmpLink + u'|' + label[index:index+len(tmpLink)] + u']]')) + label[index+len(tmpLink):]
			return u'[[' + tmpLink + u'|' + label + u']]'
		if self.getType() == u'external':
			if label is None:
				return u'[' + tmpLink + u']'
			return u'[' + tmpLink + u' ' + label + u']'
		return self.getBody()
class template:
	maxInlineParams = 1
	def __init__(self, content):
		content = u(content)
		self.changed = False
		self.content = content
		self.name = None
		self.order = None
		self.links = []
		self.params = []
		self.paramNum = 0
		self.indentation = {}
		self.defaultIndent = 0
		if len(content) > 4 and content[:2] == '{{' and content[-2:] == '}}':
			innerRegex = compileRegex(r'\s*\|\s*')
			itemRegex = compileRegex(r'^(\S[^=]*?)\s*=\s*(.*?)$')
			content = content[2:-2]
			content, self.links = linkExtract(content)
			innerStuff = innerRegex.split(content)
			if innerStuff[0][:9].lower() == 'template:':
				innerStuff[0] = innerStuff[0][9:]
			self.name = u(innerStuff[0][0].upper() + innerStuff[0][1:]).replace(u'_', u' ').strip()
			innerStuff = innerStuff[1:]
			for i in innerStuff:
				i = linkRestore(i.strip(), self.links, restore=True)
				itemRes = itemRegex.search(i)
				if itemRes:
					self.params.append((u(itemRes.group(1)).lower(), u(itemRes.group(2))))
				else:
					self.paramNum += 1
					self.params.append((u(self.paramNum), i))
		self.originalContent = self.content
		self.originalParams = self.params[:]
		self.originalName = self.name
		self.forceindent = False
	def indentationMatters(self, doesitmatter=True):
		self.forceindent = doesitmatter
	def getName(self):
		return self.name
	def setName(self, name):
		self.name = u(name).replace(u'_', u' ')
		self.changed = self.changed or self.name != self.originalName
	def getParam(self, key):
		key = u(key).lower()
		for k, v in self.params:
			if k == key:
				return v
		return None
	def delParam(self, *indexes):
		for index in indexes:
			index = u(index)
			isNumber = self.isInt(index)
			for p in range(len(self.params)):
				k, v = self.params[p]
				if k == index:
					self.changed = True
					self.params = self.params[:p] + self.params[p+1:]
					if isNumber:
						if int(index) == self.paramNum:
							self.paramNum -= 1
					break
	def setParam(self, index=None, value=u''):
		if value is None:
			return self.delParam(index)
		if index is None:
			index = u(self.paramNum)
		else:
			index = u(index).lower()
		isNumber = self.isInt(index)
		value = u(value)
		hasChanged = False
		for p in range(len(self.params)):
			k, v = self.params[p]
			if k == index:
				self.changed = self.changed or v != value
				self.params[p] = (k, value)
				hasChanged = True
				break
		if not hasChanged:
			if isNumber:
				while self.numParam < int(index) - 1:
					self.appendParam(u'')
			self.params.append((index, value))
			self.changed = True
	def appendParam(self, value=u''):
		self.paramNum += 1
		self.params.append((u(self.paramNum), value))
	def setPreferedIndentation(self, index, indent=0):
		self.indentation[u(index)] = indent
		self.changed = self.changed or self.forceindent
	def setDefaultIndentation(self, indent=0):
		self.defaultIndent = indent
		self.changed = self.changed or self.forceindent
	def setPreferedOrder(self, order=None):
		order2 = []
		for o in order:
			order2.append(u(o))
		self.order = order2
		oldParams = self.params[:]
		self.changed = self.changed or self.fixOrder() == oldParams
	def renameParam(self, oldkey, newkey):
		oldkey, newkey = u(oldkey).lower(), u(newkey).lower()
		if oldkey == newkey:
			return
		for p in range(len(self.params)):
			k, v = self.params[p]
			if k == oldkey:
				self.params[p] = (newkey, v)
				self.changed = True
				break
	def fixOrder(self):
		if self.order is None:
			return self.params
		newParams = []
		doneParams = []
		for k in self.order:
			k = u(k)
			if self.getParam(k) is not None:
				newParams.append((k, self.getParam(k)))
				doneParams.append(k)
		for k, v in self.params:
			if k not in doneParams:
				doneParams.append(k)
				newParams.append((k, v))
		self.params = newParams
		return self.params
	def defined(self):
		return self.name is not None
	def isInt(self, i):
		try:
			return u(int(i)) == u(i) and int(i) > 0
		except:
			return False
	def __str__(self):
		return self.__unicode__()
	def __repr__(self):
		return u'<Template-' + self.getName() + u': ' + self.__unicode__() + u'>'
	def __unicode__(self):
		if not self.defined():
			return u''
		if not self.changed:
			return self.originalContent
		self.fixOrder()
		params = [self.name]
		indentMode = len(self.params) > template.maxInlineParams or self.forceindent
		maxIndent = 0
		if indentMode:
			for k, v in self.params:
				l = len(k) + self.defaultIndent
				if k in self.indentation:
					l = len(k) + self.indentation[k]
				if not self.isInt(k) and l > maxIndent:
					maxIndent = l
		numParam = 1
		for k, v in self.params:
			indent = self.defaultIndent
			if k in self.indentation and indentMode:
				indent = self.indentation[k]
			try:
				isNumber = u(int(index)) == u(index) and int(index) > 0
			except:
				isNumber = False
			if indentMode:
				key = u' ' * indent + u'| '
				addKey = True
				if self.isInt(k):
					if int(k) == numParam:
						addKey = False
					numParam += 1
				if addKey:
					key += k + (u' ' * max(0, maxIndent - len(k) - indent)) + u' = '
			else:
				key = u''
				addKey = True
				if self.isInt(k):
					if int(k) == numParam:
						addKey = False
					numParam += 1
				if addKey:
					key += k + u' = '
			params.append(key + v)
		if indentMode:
			params = u'\n'.join(params) + u'\n'
		else:
			params = u' | '.join(params)
		return u'{{' + params + u'}}'
def linkExtract(content):
	content = u(content)
	links1 = compileRegex(r'\[\[([^\[\]]+)\]\]')
	links2 = compileRegex(r'\[([^\[\]]+)\](?!\])')
	linkcount = 0
	linklist = []
	res = links1.search(content)
	while res:
		linklist.append(link(res.group()))
		content = content[:res.start()] + u'~!~!~!~OMGLINK-' + u(linkcount) + u'~!~!~!~' + content[res.end():]
		linkcount += 1
		res = links1.search(content)
	res = links2.search(content)
	while res:
		linklist.append(link(res.group()))
		content = content[:res.start()] + u'~!~!~!~OMGLINK-' + u(linkcount) + u'~!~!~!~' + content[res.end():]
		linkcount += 1
		res = links2.search(content)
	return content, linklist
def templateExtract(content):
	content = u(content)
	templatesR = compileRegex(r'\{\{([^\{\}]+)\}\}')
	templatecount = 0
	templatelist = []
	res = templatesR.search(content)
	while res:
		templatelist.append(template(res.group()))
		content = content[:res.start()] + u'~!~!~!~OMGTEMPLATE-' + u(templatecount) + u'~!~!~!~' + content[res.end():]
		templatecount += 1
		res = templatesR.search(content)
	return content, templatelist
def blankAround(content, search, repl=u''):
	content = u(content)
	search = u(search)
	repl = u(repl)
	blank = compileRegex(u'(\\s*)' + u(re.escape(search)) + u'(\\s*)')
	res = blank.search(content)
	if not res:
		return content.replace(search, repl)
	if u(res.group(0)) == content:
		return repl
	if len(res.group(1)) < len(res.group(2)):
		return content[:res.end(1)] + content[res.end(2):]
	else:
		return content[:res.start()] + content[res.start(2):]
def linkRestore(content, links=[], restore=False):
	linklist=links[:]
	linkcount = len(linklist)
	i = 0
	linklist.reverse()
	for l in linklist:
		i += 1
		if l is None:
			content = blankAround(content, u'~!~!~!~OMGLINK-' + u(linkcount - i) + u'~!~!~!~', u'')
		else:
			if restore:
				l = l.getBody()
			content = content.replace(u'~!~!~!~OMGLINK-' + u(linkcount - i) + u'~!~!~!~', u(l))
	return content
def templateRestore(content, templatelist=[]):
	templatecount = len(templatelist)
	i = 0
	templatelist.reverse()
	for t in templatelist:
		i += 1
		if t is None:
			content = blankAround(content, u'~!~!~!~OMGTEMPLATE-' + u(templatecount - i) + u'~!~!~!~', u'')
		else:
			content = content.replace(u'~!~!~!~OMGTEMPLATE-' + u(templatecount - i) + u'~!~!~!~', u(t))
	return content
def safeContent(content):
	safelist = []
	tags = compileRegex(r'<(?:ref|gallery|pre|code)[^<>]*>[\S\s]*?</(?:ref|gallery|pre|code)>', re.IGNORECASE | re.MULTILINE)
	comments = compileRegex(r'<!--[\S\s]*?-->')
	tagcount = 0
	res = tags.search(content)
	if not res:
		res = comments.search(content)
	while res:
		safelist.append(('~!~!~!~OMGTAG-' + u(tagcount) + u'~!~!~!~', u(res.group())))
		content = content[:res.start()] + u'~!~!~!~OMGTAG-' + u(tagcount) + u'~!~!~!~' + content[res.end():]
		tagcount += 1
		res = tags.search(content)
		if not res:
			res = comments.search(content)
	return content, safelist
def safeContentRestore(content, safelist=[]):
	safelist.reverse()
	for s in safelist:
		content = content.replace(s[0], s[1])
	return content

def regReplaceCallBack(sub, match):
	groupcount = 1
	for g in match.groups():
		if g is not None:
			sub = sub.replace(u'$' + u(groupcount), g)
		else:
			sub = sub.replace(u'$' + u(groupcount), u'')
		groupcount += 1
	return sub
def regSub(regexes, content, **kwargs):
	content = u(content)
	for regex in regexes.keys():
		compiled = compileRegex(u(regex), re.IGNORECASE | re.DOTALL | re.MULTILINE)
		callback = curry(regReplaceCallBack, u(regexes[regex]))
		oldcontent = u''
		while content != oldcontent:
			oldcontent = content
			content = compiled.sub(callback, content)
	return u(content)
def dumbReplacement(strings, content, **kwargs):
	content = u(content)
	for s in strings.keys():
		content = content.replace(u(s), u(strings[s]))
	return content
def filterEnabled(f, **kwargs):
	if type(f) is not type(()):
		return True
	if len(f) < 2:
		return True
	if type(f[1]) is not type({}):
		return True
	article = None
	if 'article' in kwargs.keys():
		article = kwargs['article']
		if article is None:
			return True
		if type(article) not in (type(u''), type('')):
			article = article.title
	if article is None:
		return True
	if 'languageBlacklist' in f[1].keys():
		for i in f[1]['languageBlacklist']:
			if compileRegex(u'/' + u(i) + u'$').search(u(article)):
				return False
		return True
	if 'languageWhitelist' in f[1].keys():
		for i in f[1]['languageWhitelist']:
			if compileRegex(u'/' + u(i) + u'$').search(u(article)):
				return True
		return False
	if 'language' in f[1].keys():
		return compileRegex(u'/' + u(f[1]['language']) + u'$').search(u(article))
	return True
def scheduleTask(task, oneinevery):
	result = random.randint(0, oneinevery-1)
	print 'Task:', task, '; result:', result
	if not result:
		task()
def sFilter(filters, content, returnActive=False, **kwargs):
	content = u(content)
	lenfilters = len(filters)
	if not lenfilters:
		if returnActive:
			return content, []
		return content
	filtercount = 0
	activeFilters = []
	for f in filters:
		if not filterEnabled(f, **kwargs):
			continue
		if type(f) is type(()):
			f, params = f
		filtercount += 1
		#print 'Filter', f, '(', filtercount, '/', lenfilters, ')'
		loopTimes = 0
		beforeFilter = u''
		while not loopTimes or beforeFilter != content:
			loopTimes += 1
			if loopTimes >= config['filterPasses']:
				print 'Warning: More than', config['filterPasses'], 'loops with filter', u(f)
				break
			beforeFilter = content
			content = u(f(content, **kwargs))
			if content != beforeFilter and f not in activeFilters:
				activeFilters.append(f)
	if returnActive:
		return content, activeFilters
	return content
def linkFilter(filters, linklist, returnActive=False, **kwargs):
	activeFilters = []
	for f in filters:
		if not filterEnabled(f, **kwargs):
			continue
		if type(f) is type(()):
			f, params = f
		for i in range(len(linklist)):
			if linklist[i] is not None:
				oldLink = u(linklist[i])
				linklist[i] = f(linklist[i], **kwargs)
				if oldLink != u(linklist[i]) and f not in activeFilters:
					activeFilters.append(f)
	if returnActive:
		return linklist, activeFilters
	return linklist
def templateFilter(filters, templatelist, returnActive=False, **kwargs):
	activeFilters = []
	for f in filters:
		if not filterEnabled(f, **kwargs):
			continue
		if type(f) is type(()):
			f, params = f
		for i in range(len(templatelist)):
			if templatelist[i] is not None:
				oldTemplate = u(templatelist[i])
				templatelist[i] = f(templatelist[i], **kwargs)
				if oldTemplate != u(templatelist[i]) and f not in activeFilters:
					activeFilters.append(f)
	if returnActive:
		return templatelist, activeFilters
	return templatelist
def linkTextFilter(subfilters, l, linksafe=False, **kwargs):
	if l.getType() == u'internal' and l.getLink().find(u':') == -1 and pageFilter(l.getLink()):
		if linksafe:
			l.setLink(sFilter(subfilters, l.getLink(), **kwargs))
		if l.getLabel().find(u':') == -1:
			l.setLabel(sFilter(subfilters, l.getLabel(), **kwargs))
	return l
def linkDomainSub(fromDomain, toDomain, link, **kwargs):
	domainR = compileRegex(r'^(https?://(?:[-\w]+\.)*)' + u(re.escape(fromDomain)) + r'(\S+)$')
	toDomain = u(toDomain)
	if link.getType() == 'external':
		linkInfo = domainR.search(link.getLink())
		if linkInfo:
			link.setLink(u(linkInfo.group(1)) + toDomain + u(linkInfo.group(2)))
	return link
def linkDomainFilter(fromDomain, toDomain):
	return curry(linkDomainSub, fromDomain, toDomain)
def regexes(rs):
	return curry(regSub, rs)
def regex(reg, replace):
	return regexes({reg: replace})
def dumbReplaces(rs):
	return setFilterName(curry(dumbReplacement, rs), u'DumbReplacements(' + u(rs) + u')')
def dumbReplace(subject, replacement):
	return setFilterName(dumbReplaces({subject: replacement}), u'DumbReplacement(' + u(subject) + u' -> ' + u(replacement) + u')')
def wordRegex(word):
	word = u(re.sub(r'[-_ ]+', r'[-_ ]', u(word)))
	return u(r"(?<![\u00E8-\u00F8\xe8-\xf8\w])(?<!'')(?<!" + r'"' + r")(?:\b|^)" + word + r"(?:\b(?![\u00E8-\u00F8\xe8-\xf8\w])(?!''|" + r'"' + r")|$)")
def wordFilter(correct, *badwords, **kwargs):
	correct = u(correct)
	rs = {}
	badwords2 = []
	for i in badwords:
		badwords2.append(u(i))
	if not len(badwords2):
		badwords2.append(correct)
	for w in badwords2:
		rs[wordRegex(w)] = correct
	return setFilterName(regexes(rs), u'WordFilter(' + u'/'.join(badwords2) + u' -> ' + correct + u')')
def enforceCapitalization(*words, **kwargs):
	for w in words:
		addSafeFilter(setFilterName(wordFilter(u(w)), u'EnforceCapitalization(' + u(w) + u')'), **kwargs)

pageFilters = []
pageWhitelist = []
categoryFilters = []
def pageFilter(page):
	global pageFilters, pageWhitelist
	if type(page) in (type(()), type([])):
		pages = []
		for p in page:
			if pageFilter(p):
				pages.append(p)
		return pages
	if type(page) not in (type(u''), type('')):
		page = page.title
	page = u(page)
	if page in pageWhitelist:
		return True
	for f in pageFilters:
		if f.search(page):
			return False
	return True
def categoryFilter(page):
	global categoryFilters
	pageCategories = page.getCategories()
	for c in pageCategories:
		if u(c).replace(u'_', ' ') in categoryFilters:
			return False
	return True
def addPageFilter(*filters):
	global pageFilters
	for f in filters:
		pageFilters.append(compileRegex(f))
def addBlacklistPage(*pages):
	for p in pages:
		addPageFilter(re.escape(u(p)))
def addWhitelistPage(*pages):
	global pageWhitelist
	for p in pages:
		if type(p) in (type([]), type(())):
			addWhitelistPage(*p)
		elif u(p) not in pageWhitelist:
			pageWhitelist.append(u(p))
def addBlacklistCategory(*categories):
	global categoryFilters
	for c in categories:
		categoryFilters.append(u(c).replace(u'_', ' '))
def loadBlacklist():
	global config
	for l in page(config['pages']['blacklist']).getLinks():
		l = u(l)
		if l.find(u':') != -1:
			if l[:l.find(u':')].lower() == 'category':
				addBlacklistCategory(l)
				continue
		addBlacklistPage(l)

filters = {
	'regular': [],
	'safe': [],
	'link': [],
	'template': [],
	'file': []
}
def addFilterType(filterType, *fs, **kwargs):
	global filters
	for f in fs:
		f = (f, kwargs)
		if f not in filters[filterType]:
			filters[filterType].append(f)
def delFilterType(filterType, *fs, **kwargs):
	global filters
	for f in fs:
		f = (f, kwargs)
		if f in filters[filterType]:
			filters[filterType].remove(f)
def addFilter(*fs, **kwargs):
	addFilterType('regular', *fs, **kwargs)
def delFilter(*fs, **kwargs):
	delFilterType('regular', *fs, **kwargs)
def addSafeFilter(*fs, **kwargs):
	addFilterType('safe', *fs, **kwargs)
def delSafeFilter(*fs, **kwargs):
	delFilterType('safe', *fs, **kwargs)
def addLinkFilter(*fs, **kwargs):
	addFilterType('link', *fs, **kwargs)
def delLinkFilter(*fs, **kwargs):
	delFilterType('link', *fs, **kwargs)
def addTemplateFilter(*fs, **kwargs):
	addFilterType('template', *fs, **kwargs)
def delTemplateFilter(*fs, **kwargs):
	delFilterType('template', *fs, **kwargs)
def addFileFilter(*fs, **kwargs):
	addFilterType('file', *fs, **kwargs)
def delFileFilter(*fs, **kwargs):
	delFilterType('file', *fs, **kwargs)
def filterRepr(filters):
	s = []
	reprRegex = compileRegex(r'^<function (\S+)')
	for f in filters:
		if type(f) in (type([]), type(())) and not len(f[1]):
			f = f[0] # Omit parameters if there are none
		try:
			name = f.filterName
			s.append(name)
		except:
			res = reprRegex.search(u(f))
			if res:
				filterR = u(res.group(1))
				if filterR not in s:
					s.append(filterR)
			elif u(f) not in s:
				s.append(u(f))
	if not len(s):
		return u'Built-in filters' # Link simplification, template formatting, etc
	return u', '.join(s)
def fixContent(content, article=None, returnActive=False, **kwargs):
	global filters
	content = u(content)
	oldcontent = u''
	loopTimes = 0
	redirect = False
	activeFilters = []
	if len(content) > 9:
		redirect = content[:9] == u'#REDIRECT'
	if article is not None:
		article = page(article)
	while not loopTimes or content != oldcontent:
		loopTimes += 1
		if loopTimes > 2:
			print 'Pass', loopTimes, 'on', article
		if loopTimes >= config['pagePasses']:
			print 'Warning: More than', config['pagePasses'], 'fix passes on article', u(article.title)
			break
		oldcontent = content
		# Apply unsafe filters
		content, activeF = sFilter(filters['regular'], content, returnActive=True, article=article, redirect=redirect)
		activeFilters.extend(activeF)
		# Apply safe filters
		content, safelist = safeContent(content)
		content, templatelist = templateExtract(content)
		content, linklist = linkExtract(content)
		content, activeF = sFilter(filters['safe'], content, returnActive=True, article=article, redirect=redirect)
		activeFilters.extend(activeF)
		extraLinks = setFilterName(curry(linkTextFilter, filters['safe']), u'(Content filters applied to links)')
		addLinkFilter(extraLinks)
		if not redirect:
			linklist, activeF = linkFilter(filters['link'], linklist, returnActive=True, article=article, redirect=redirect)
			activeFilters.extend(activeF)
		content = linkRestore(content, linklist)
		templatelist, activeF = templateFilter(filters['template'], templatelist, returnActive=True, article=article, redirect=redirect)
		activeFilters.extend(activeF)
		content = templateRestore(content, templatelist)
		content = safeContentRestore(content, safelist)
		delLinkFilter(extraLinks)
	if u(article.title)[:5] == 'File:':
		# Apply file filters
		content, activeF = sFilter(filters['file'], content, returnActive=True, article=article, redirect=redirect)
		activeFilters.extend(activeF)
	if returnActive:
		return content, activeFilters
	return content
def fixPage(article, **kwargs):
	article = page(article)
	force = False
	if 'force' in kwargs and kwargs['force']:
		force = True
	try:
		catFilter = categoryFilter(article)
	except wikitools.page.NoPage:
		print 'No such page:', article
		return False
	except:
		catFilter = True
	if not force and (not pageFilter(article) or not catFilter):
		print 'Skipping:', article
		return
	originalContent = u(article.getWikiText())
	content, activeFilters = fixContent(originalContent, returnActive=True, article=article)
	if content != originalContent:
		print article, 'needs to be updated.'
		summary = u'Auto: ' + filterRepr(activeFilters)
		if 'reason' in kwargs:
			summary += u' (' + u(kwargs['reason']) + u')'
		if 'fake' in kwargs:
			print '-------- New content is: --------'
			print content
			print '---------------------------------'
		else:
			editPage(article, content, summary=summary)
		return True
	print article, 'is up-to-date.'
	return False
def patrol(change):
	global config
	secondsElapsed = (datetime.datetime.utcnow() - datetime.datetime.fromtimestamp(time.mktime(time.strptime(change['timestamp'], r'%Y-%m-%dT%H:%M:%SZ'))))
	totalTime = secondsElapsed.seconds + secondsElapsed.days * 86400
	if int(change['rcid']) <= config['runtime']['rcid'] or not pageFilter(change['title']) or totalTime <= config['freshnessThreshold']:
		print 'Skipping', change['rcid'], change['title']
		if int(change['rcid']) > config['runtime']['rcid']:
			config['runtime']['rcid'] = int(change['rcid'])
		return
	print 'Patrolling', change['title']
	config['runtime']['rcid'] = int(change['rcid'])
	result = fixPage(change['title'], reason=u'Review RC#' + u(change['rcid']))
	updateRCID()
def loadPage(p):
	p = page(p)
	try:
		code = u(p.getWikiText())
	except:
		error('Couldn\'t grab page', p)
	coderegex = compileRegex(r'^(?:  [^\r\n]*(?:[\r\n]+|$))+', re.MULTILINE)
	trimcode = compileRegex(r'^  |</?nowiki>', re.MULTILINE)
	for m in coderegex.finditer(code):
		try:
			exec(trimcode.sub(u'', u(m.group())))
		except:
			error('Error while parsing code: ', m.group())
def patrolChanges():
	try:
		recentChanges = wikitools.api.APIRequest(wiki(), {
			'action':'query',
			'list':'recentchanges',
			'rctoken':'patrol',
			'rclimit':'500'
		}).query(querycontinue=False)[u'query'][u'recentchanges']
		recentChanges.reverse()
	except:
		error('Error while trying to grab recent changes.')
	uniquePages = []
	uniqueChanges = {}
	for change in recentChanges:
		if change['title'] not in uniquePages:
			uniquePages.append(change['title'])
		if change['title'] not in uniqueChanges or uniqueChanges[change['title']]['rcid'] < change['rcid']:
			uniqueChanges[change['title']] = change
			# Move page to end of queue
			uniquePages.remove(change['title'])
			uniquePages.append(change['title'])
	for title in uniquePages:
		change = uniqueChanges[title]
		try:
			patrol(change)
		except KeyboardInterrupt:
			error('Interrupted:', change)
		except:
			warning('Failed to patrol change:', change)
	print 'Done patrolling.'
def parsePageRequest(l, links=[]):
	l = u(l)
	content = []
	selfContent = u'* [[:' + l + u']]'
	if l.find(u':'):
		if l[:l.find(u':')].lower() == 'category':
			subpages = wikitools.category.Category(wiki(), l[l.find(u':')+1:]).getAllMembers(titleonly=True)
			for s in subpages:
				if s not in links:
					links.append(s)
					newLink, links = parsePageRequest(s, links=links)
					content.append(newLink)
	if len(content):
		selfContent += u'\r\n' + u'\r\n'.join(content)
	return selfContent, links
def doPageRequests(force=False):
	global config
	print 'Executing page requests. Force =', force
	if force:
		requestPageTitle = config['pages']['pagerequestsforce']
	else:
		requestPageTitle = config['pages']['pagerequests']
	requestPage = page(requestPageTitle)
	reqre = compileRegex(r'^\*[\t ]*\[\[:?([^][]+)\]\]', re.MULTILINE)
	originalRequests = u(requestPage.getWikiText())
	requests = originalRequests
	matches = []
	links = []
	for m in reqre.finditer(requests):
		matches.append(m)
		l = u(m.group(1))
		if l not in links:
			links.append(l)
	matches.reverse()
	for m in matches:
		pagelink, links = parsePageRequest(u(m.group(1)), links=links)
		requests = requests[:m.start()] + pagelink + requests[m.end():]
	requests = regSub({r'^[ \t]*(\*[^\r\n]+)[\r\n]+(?=^[ \t]*\*)':'$1\r\n'}, requests)
	reqre2 = compileRegex(r'^\*[\t ]*\[\[:?([^][]+)\]\]\s*', re.MULTILINE)
	matches2 = []
	requestsDone = 0
	tooMany = False
	for m in reqre2.finditer(requests):
		requestsDone += 1
		if requestsDone > config['maxrequests']:
			tooMany = True
			break
		matches2.append(m)
	matches2.reverse()
	tofix = []
	for m in matches2:
		tofix.append(u(m.group(1)))
		requests = requests[:m.start()] + requests[m.end():]
	tofix.reverse()
	for p in tofix:
		fixPage(p, reason=u'Requested on [[:' + u(requestPageTitle) + u']]', force=force)
	requests = regSub({r'^[ \t]*(\*[^\r\n]+)[\r\n]+(?=^[ \t]*\*)':'$1\r\n'}, requests)
	if len(tofix) and originalRequests != requests:
		if tooMany:
			editPage(requestPage, requests, summary=u'Processed: [[:' + u']], [[:'.join(tofix) + u']]')
		else:
			editPage(requestPage, requests, summary=u'Finished all requests. Processed: [[:' + u']], [[:'.join(tofix) + u']]')
def parseLocaleFile(content, language='english', languages={}):
	content = u(content)
	language = u(language)
	if content.find('Tokens') != -1:
		content = content[content.find('Tokens')+6:]
	regexSplit = compileRegex('\n(?=\s*")', re.IGNORECASE | re.MULTILINE)
	content = regexSplit.split(content)
	regexLang = compileRegex(r'^"\[([-\w]+)\]([^"\s]+)"\s+"([^"]*)"', re.IGNORECASE | re.MULTILINE)
	regexNoLang = compileRegex(r'^"([^[][^"\s]+)"\s+"([^"]*)"', re.IGNORECASE | re.MULTILINE)
	for l in content:
		l = u(l.strip())
		curlang = None
		key, value = None, None
		langRes = regexLang.search(l)
		if langRes:
			curlang = u(langRes.group(1))
			key, value = langRes.group(2), langRes.group(3)
		else:
			langRes = regexNoLang.search(l)
			if langRes:
				curlang = language
				key, value = langRes.group(1), langRes.group(2)
		if curlang is not None:
			if u(key) not in languages:
				languages[u(key)] = {}
			languages[u(key)][curlang] = u(value)
		else:
			pass #print 'Invalid line:', l.__repr__()
	return languages
def languagesFilter(languages, commonto=None, prefix=None, suffix=None, exceptions=[]):
	filtered = {}
	for k in languages:
		if k in exceptions:
			continue
		if commonto is not None:
			doit = True
			for i in commonto:
				if i not in languages[k]:
					doit = False
					break
			if not doit:
				continue
		if prefix is not None:
			doit = False
			for i in prefix:
				if k.lower()[:len(i)] == i.lower():
					doit = True
					break
			if not doit:
				continue
		if suffix is not None:
			doit = False
			for i in suffix:
				if k.lower()[-len(i):] == i.lower():
					doit = True
					break
			if not doit:
				continue
		filtered[u(k)] = languages[k]
	return filtered
def readLocaleFile(f):
	return u(f.decode('utf16'))
def associateLocaleWordFilters(languages, fromLang, toLang, targetPageLang=None):
	for a in languages:
		f = wordFilter(languages[a][toLang], languages[a][fromLang])
		if targetPageLang is None:
			addSafeFilter(f)
		else:
			addSafeFilter(f, language=targetPageLang)
def run():
	global config
	print 'Bot started.'
	loadPage(config['pages']['filters'])
	for p in sys.argv[1:]:
		print 'Forced update to', p, '...'
		fixPage(p)
	loadBlacklist()
	patrolChanges()
	updateRCID()
	doPageRequests(force=True)
	doPageRequests(force=False)
	updateEditCount()
	import rcNotify
	rcNotify.main(once=True)
	try:
		subprocess.Popen(['killall', 'cpulimit']).communicate()
	except:
		pass
	print 'All done.'
if __name__ == '__main__':
	run()