


def unclassify(soup):
	validattrs = [
		'href',
		'src',
		'cellspacing',
		'cellpadding',
		'border',
		'colspan',
		'onclick',
		'type',
		'value',
	]
	print("RemoveClasses call!")

	for item in [item for item in soup.find_all(True) if item]:
		tmp_valid = validattrs[:]
		if item.attrs:
			for attr, value in list(item.attrs.items()):
				if attr == 'style' and 'float' in value:
					del item[attr]
				elif attr not in tmp_valid:
					del item[attr]

		# Set the class of tables set to have no borders to the no-border css class for later rendering.
		if item.name == "table" and item.has_attr("border") and item['border'] == "0":
			if not item.has_attr("class"):
				item['class'] = ""
			item['class'] += " noborder"


	return soup
