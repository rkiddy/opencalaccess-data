
import datetime as dt
import sys

from dateutil.relativedelta import relativedelta
from dotenv import dotenv_values
from sqlalchemy import create_engine, inspect

cfg = dotenv_values(".env")

sys.path.append(f"{cfg['APP_HOME']}")
import common

engine = create_engine(f"mysql+pymysql://ray:{cfg['PWD']}@{cfg['HOST']}/{cfg['DB']}")
conn = engine.connect()
inspector = inspect(engine)


def tables_with_column(col_name):

    file = open(f"{cfg['APP_HOME']}/tableCols.txt")

    table_name = None
    found_tables = list()

    for line in file:
        parts = line.strip().split(' ')
        if len(parts) == 1:
            table_name = parts[0]
        if len(parts) > 1 and parts[0] == col_name:
            found_tables.append(table_name)

    return sorted(found_tables)


def full_name(naml, namf, namt, nams):
    if namt is not None:
        buf = f"{namt} "
    else:
        buf = ""
    if naml is not None and namf is not None:
        buf = f"{buf} {namf} {naml}"
    if naml is not None and namf is None:
        buf = f"{buf} {naml}"
    if naml is None and namf is not None:
        buf = f"{buf} {namf}"
    if nams is not None:
        buf = f"{buf} {nams}"
    return buf


def calacess_front(lowest_date=None, highest_date=None):
    context = dict()

    if lowest_date is not None and highest_date is None:
        lowest = dt.strptime(lowest_date, '%Y-%m-%d')
        highest = lowest + relativedelta(days=20)
        highest_date = highest.strftime('%Y-%m-%d')

    if lowest_date is None and highest_date is not None:
        highest = dt.strptime(highest_date, '%Y-%m-%d')
        lowest = highest - relativedelta(days=20)
        lowest_date = lowest.strftime('%Y-%m-%d')

    if lowest_date is not None and highest_date is not None:
        sql = f"""
        select date(filing_date) as filing_date, count(0) as count from filer_filings
        where filing_date >= '{lowest_date}' and filing_date <= '{highest_date}'
        group by filing_date order by filing_date desc
        """

    if lowest_date is None and highest_date is None:
        sql = """
        select date(filing_date) as filing_date, count(0) as count from filer_filings
        where filing_date < '2030-01-01'
        group by filing_date order by filing_date desc limit 20
        """

    rows = conn.execute(sql).fetchall()
    next_rows = list()
    for row in rows:
        next_rows.append(
            {
                'filing_date': row['filing_date'].strftime('%Y-%m-%d'),
                'count': row['count']
            }
        )

    if len(next_rows) > 0:
        lowest_date = min([r['filing_date'] for r in next_rows])
        highest_date = max([r['filing_date'] for r in next_rows])

    sql = f"""
    select filing_date, filing_id, form_id
    from filer_filings
    where filing_date >= '{lowest_date}' and filing_date < '{highest_date}'
    """

    cols = {
        'filing_date': 0,
        'filing_id': 1,
        'form_id': 2
    }

    rows = conn.execute(sql).fetchall()
    data = common.fill_in_table(rows, cols)

    # filings -> [filing_date] -> [form_id] -> # for the filing_date
    # totals -> [filing_date] -> # for the all forms for the filing_date

    filings = dict()
    all_form_ids = list()
    totals = dict()

    for datum in data:

        all_form_ids.append(datum['form_id'])
        filing_date = datum['filing_date'].strftime('%Y-%m-%d')

        if filing_date not in filings:
            filings[filing_date] = dict()
        if filing_date not in totals:
            totals[filing_date] = 0

        totals[filing_date] += 1
        if datum['form_id'] not in filings[filing_date]:
            filings[filing_date][datum['form_id']] = 1
        else:
            filings[filing_date][datum['form_id']] += 1

    all_form_ids = sorted(list(set(all_form_ids)))

    for filing_date in filings:
        for form_id in all_form_ids:
            if form_id not in filings[filing_date]:
                filings[filing_date][form_id] = 0

    form_ids = dict()
    form_ids['campaign'] = list()
    form_ids['lobbyist'] = list()
    form_ids['others'] = list()

    for form_id in all_form_ids:
        if form_id.startswith('F4'):
            form_ids['campaign'].append(form_id)
        elif form_id.startswith('F6'):
            form_ids['lobbyist'].append(form_id)
        else:
            form_ids['others'].append(form_id)

    filing_dates = sorted(list(filings.keys()))
    filing_dates.reverse()

    context['nexts'] = {
        'next_start': highest_date,
        'next_end': (dt.datetime.strptime(highest_date, '%Y-%m-%d') + relativedelta(days=20)).strftime('%Y-%m-%d'),
        'prev_start': (dt.datetime.strptime(lowest_date, '%Y-%m-%d') - relativedelta(days=20)).strftime('%Y-%m-%d'),
        'prev_end': lowest_date
    }

    sql = """
    select n1.form_type, n1.form_name,
        count_2015, count_2016, count_2017, count_2018,
        count_2019, count_2020, count_2021, count_2022, count_all
    from _form_type_names n1
    order by n1.form_type
    """
    cols = {
        'form_type': 0,
        'form_name': 1,
        'count_2015': 2,
        'count_2016': 3,
        'count_2017': 4,
        'count_2018': 5,
        'count_2019': 6,
        'count_2020': 7,
        'count_2021': 8,
        'count_2022': 9,
        'count_all': 10,
        'count': 11
    }
    form_types = [dict(row) for row in conn.execute(sql).fetchall()]

    context['form_types'] = form_types
    context['form_ids'] = form_ids
    context['totals'] = totals
    context['filing_dates'] = filing_dates
    context['filings'] = filings

    return context


def quarter_abbrev(period_start, period_desc):
    if period_start is not None and period_desc is not None:
        start_date = period_start.strftime("%Y")
        period = f"{start_date} Q{period_desc[-1]}"
    if period_start is not None and period_desc is None:
        start_date = period_start.strftime("%Y")
        period = f"{start_date} Q?"
    if period_start is None and period_desc is not None:
        period = f"???? Q{period_desc[-1]}"
    if period_start is None and period_desc is None:
        period = None
    return period


def calaccess_filing_date(filing_date_1, filing_date_2=None, form_id=None):

    context = dict()

    # select * from filer_filings outer left join filername;
    #
    if form_id is None:
        sql = f"""
        select f1.filing_id, f1.filer_id, f1.period_id, f1.form_id,
            f1.filing_sequence as filing_seq, date(f1.rpt_start) as rpt_start,
            date(f1.rpt_end) as rpt_end, f2.filer_type, f2.naml, f2.namf, f2.namt,
            f2.nams, f2.city, f2.st, f2.zip4, f2.effect_dt, f3.start_date, f3.period_desc,
            f4.form_name
        from filer_filings f1 left join filername f2 on f1.filer_id = f2.filer_id
            left join filing_period f3 on f1.period_id = f3.period_id
            left join _form_type_names f4 on f1.form_id = f4.form_type
        """

        if filing_date_2 is None:
            sql = f"{sql} where f1.filing_date = '{filing_date_1}'"
        else:
            sql = f"""
                {sql} where f1.filing_date >= '{filing_date_1}'
                and f1.filing_date <= '{filing_date_2}'
            """
    else:
        sql = f"""
        select f1.filing_id, f1.filer_id, f1.period_id, f1.form_id,
            f1.filing_sequence as filing_seq, date(f1.rpt_start) as rpt_start,
            date(f1.rpt_end) as rpt_end, f2.filer_type, f2.naml, f2.namf, f2.namt,
            f2.nams, f2.city, f2.st, f2.zip4, f2.effect_dt, f3.start_date, f3.period_desc,
            f4.form_name
        from filer_filings f1 left join filername f2 on f1.filer_id = f2.filer_id
            left join filing_period f3 on f1.period_id = f3.period_id
            left join _form_type_names f4 on f1.form_id = f4.form_type
                where f1.form_id = '{form_id}' and
                f1.form_id = f4.form_type
        """

        if filing_date_2 is None:
            sql = f"{sql} and f1.filing_date = '{filing_date_1}'"
        else:
            sql = f"""
                {sql}
                and f1.filing_date >= '{filing_date_1}'
                and f1.filing_date <= '{filing_date_2}'
            """

    rows = conn.execute(sql).fetchall()

    cols = {
        'filing_id': 0,
        'filer_id': 1,
        'period_id': 2,
        'form_id': 3,
        'filing_seq': 4,
        'rpt_start': 5,
        'rpt_end': 6,
        'filer_type': 7,
        'naml': 8,
        'namf': 9,
        'namt': 10,
        'nams': 11,
        'city': 12,
        'st': 13,
        'zip4': 14,
        'effect_dt': 15,
        'period_start': 16,
        'period_desc': 17,
        'form_name': 18
    }

    data = common.fill_in_table(rows, cols)

    next_data = dict()

    form_name = None

    for datum in data:

        filer_id = datum['filer_id']

        if form_id is not None:
            form_name = datum['form_name']

        if filer_id not in next_data:
            next_data[filer_id] = datum
        else:
            effect_dt = datum['effect_dt']
            if effect_dt is not None and effect_dt > next_data[filer_id]['effect_dt']:
                next_data[filer_id] = datum

    amt_tables = ['expn', 'latt', 'lccm', 'lexp', 'loth', 'rcpt', 's401', 's496', 's497']

    for filer_id in next_data:

        entry = next_data[filer_id]

        entry['full_name'] = full_name(entry['naml'], entry['namf'], entry['namt'], entry['nams'])

        entry['period'] = quarter_abbrev(entry['period_start'], entry['period_desc'])

        amounts = dict()

        for amt_table in amt_tables:
            sql = f"select max(amend_id) amend_id from {amt_table} where filing_id = '{entry['filing_id']}'"
            row = conn.execute(sql).fetchone()
            if row['amend_id'] is not None:
                amend_id = row['amend_id']
                sql = f"""
                    select sum(amount) sum from {amt_table}
                    where filing_id = '{entry['filing_id']}' and
                          amend_id = '{amend_id}'"""
                row = conn.execute(sql).fetchone()
                if row['sum'] is not None and str(row['sum']) != '0':
                    amounts[amt_table] = "${:,.2f}".format(row['sum'])

        entry['amounts'] = amounts

    context['filing_date'] = filing_date_1
    context['filing_date_hi'] = filing_date_2

    context['form_id'] = form_id
    context['form_name'] = form_name

    context['calaccess_filing_date'] = common.order_dicts_by_key(list(next_data.values()), 'filing_id')

    return context


def filing_raw(filing_id):

    context = dict()

    amend_id = 0

    context['filing_id'] = filing_id

    url_start = "https://cal-access.sos.ca.gov/PDFGen/pdfgen.prg"

    tables = list()

    for table in tables_with_column('filing_id'):

        sql = f"desc {table}"

        rows = conn.execute(sql).fetchall()
        column_names = list()
        sideways = dict()
        cols = dict()
        idx = 0

        for row in rows:
            column_names.append(row[0])
            cols[row[0]] = idx
            sideways[row[0]] = list()
            idx += 1

        sql = f"select * from {table} where filing_id = {filing_id}"

        rows = conn.execute(sql).fetchall()
        data = common.fill_in_table(rows, cols)

        if len(data) > 0:
            for datum in data:
                for col_name in column_names:
                    sideways[col_name].append(datum[col_name])

            if 'amend_id' in sideways and len(sideways['amend_id']) > 0:
                amend_id = max(sideways['amend_id'])

            buf = f"<table border=\"1\">\n    <caption>Table: {table}</caption>\n"

            for col_name in column_names:
                buf = f"{buf}    <tr>\n        <th>{col_name}</th>\n"

                for value in sideways[col_name]:
                    buf = f"{buf}        <td>&nbsp;&nbsp;</td><td>{value}</td>\n"

                buf = f"{buf}    </tr>"

            buf = f"{buf}</table>\n"

            tables.append(buf)

    context['pdf'] = f"{url_start}?filingid={filing_id}&amendid={amend_id}"

    context['tables'] = tables

    return context


def filer_raw(filer_id):

    context = dict()

    context['filer_id'] = filer_id

    tables = list()

    for table in tables_with_column('filer_id'):

        sql = f"desc {table}"

        rows = conn.execute(sql).fetchall()
        column_names = list()
        sideways = dict()
        cols = dict()
        idx = 0

        for row in rows:
            column_names.append(row[0])
            cols[row[0]] = idx
            sideways[row[0]] = list()
            idx += 1

        sql = f"select * from {table} where filer_id = {filer_id}"

        rows = conn.execute(sql).fetchall()
        data = common.fill_in_table(rows, cols)

        if len(data) > 0:
            for datum in data:
                for col_name in column_names:
                    sideways[col_name].append(datum[col_name])

            buf = f"<table border=\"1\">\n    <caption>Table: {table}</caption>\n"

            for col_name in column_names:
                buf = f"{buf}    <tr>\n        <th>{col_name}</th>\n"

                for value in sideways[col_name]:
                    buf = f"{buf}        <td>&nbsp;&nbsp;</td><td>{value}</td>\n"

                buf = f"{buf}    </tr>"

            buf = f"{buf}</table>\n"

            tables.append(buf)

    context['tables'] = tables

    return context
