__author__ = 'ilya'

class VersioningConfiguration:
	template = \
"""<VersioningConfiguration xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
  <Status>%(state)s</Status>
</VersioningConfiguration>"""
	def __init__(self, *args, **kwargs):
		self.state = kwargs['state']


	def __str__(self):
		return VersioningConfiguration.template % {'state':self.state}

if __name__ == '__main__':
	print VersioningConfiguration(state = 'Suspended')