# -*- coding: utf-8 -*-
{
    'name': "Cloud Manager",

    'summary': """ The Cloud Manager helps you create and manage a hybrid set of virtual machines.""",

    'description': """
		Create and manage Google Compute Engine VM and Digital Ocean Droplet (and similar vendor)
		 instances for any purpose including running a SaaS company.
		Provide for "High Availability (HA)" and "Disaster recovery (DR)" via remote datacenter warm backup systems.
		Provide modular script template facilities for managing your virtual servers alone or in groups using action buttons.
    """,

    'author': "AdHoc S.A. Gary Wallis for Unixservice, LLC.",
    'website': "http://www.adhoc.com.ar",

    'category': 'Uncategorized',
    'version': '8.0.1.0.0',

    # any module necessary for this one to work correctly
    'depends': ['base','board'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/cloudmanager.xml',
        'views/provider.xml',
        'views/server.xml',
        'views/serverstatus.xml',
        'views/zone.xml',
        'views/machinetype.xml',
        'views/image.xml',
        'views/deployvm.xml',
	'data/provider.xml',
	'data/serverstatus.xml',
	'data/machinetype.xml',
	'data/image.xml',
	'data/zone.xml',
	'data/server.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo.xml',
    ],
}