
import re
import sys

from flask import Flask
from jinja2 import Environment, PackageLoader

import data

calaccess = Flask(__name__)
application = calaccess
env = Environment(loader=PackageLoader('calaccess', 'pages'))


@calaccess.route('/calaccess')
@calaccess.route('/calaccess/')
def contracts_front():
    main = env.get_template('calaccess.html')
    context = data.build('calaccess_front')
    return main.render(**context)


@calaccess.route('/calaccess/filingdate/<param>')
def contracts_filingdate(param):
    main = env.get_template('calaccess_filingdate.html')
    context = data.build('calaccess_filingdate', param)
    return main.render(**context)


@calaccess.route('/calaccess/filing_raw/<param>')
def contracts_filing_raw(param):
    main = env.get_template('calaccess_filing_raw.html')
    context = data.build('calaccess_filing_raw', param)
    return main.render(**context)


@calaccess.route('/calaccess/filer_raw/<param>')
def contracts_filer_raw(param):
    main = env.get_template('calaccess_filer_raw.html')
    context = data.build('calaccess_filer_raw', param)
    return main.render(**context)


if __name__ == '__main__':
    calaccess.run()