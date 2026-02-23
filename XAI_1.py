import pandas as pd
import numpy
# import geopandas
from bokeh import models, plotting, layouts, io


from currency_converter import CurrencyConverter
from pathlib import Path
from datetime import datetime

c = CurrencyConverter(fallback_on_missing_rate=True)
io.output_file('Dashboard.html')

# --------------- SALES --------------------------------------------------

path_name = Path('assignment1_data').glob(r'sales*10*')
sales = []
for csv in path_name:
    df = pd.read_csv(csv, encoding='utf-8', sep=',')
    sales.append(df)

# for csv in lst:
#     print(csv.to_string())

# The formats of sales files 6 and 7 are different than those in 1-5
# CHANGE 67 NAMES TO 1-5 NAMES
for csv in ['assignment1_data/sales_202111.csv', 'assignment1_data/sales_202112.csv']:
    df = pd.read_csv(csv, encoding='utf-8', sep=',')
    df = df.rename(columns={
            'Order Charged Date': 'Transaction Date',
            'Product ID': 'Product id',
            'Sku ID': 'Sku Id',
            'Country of Buyer': 'Buyer Country',
            'Postal Code of Buyer': 'Buyer Postal Code',
    })

    # Note: November and December only have Charged Amount, which is in the original currency and not in EUR,
    # (as opposed to the previous months that have Amount (Merchant Currency) In EUR. Converting every Charged Amount
    # to EUR seems infeasible, but we should ask

    # for cell in df['Transaction Date']:
    #     cell = datetime.strptime(f"{cell}", "%Y-%m-%d")
    #     cell = cell.strftime("%b %d, %Y")

    df['Transaction Date'] = df['Transaction Date'].apply(lambda x: datetime.strptime(f"{x}", "%Y-%m-%d"))
    df['Transaction Date'] = df['Transaction Date'].apply(lambda x: x.strftime("%b %d, %Y"))

    df['Charged Amount'] = df['Charged Amount'].apply(lambda x: float(x.replace(',', '')) if isinstance(x, str) else float(x))

    # Change currency to EUR
    # df['Amount (Merchant Currency)'] = c.convert(df['Amount (Merchant Currency)'], 'EUR', df['Currency of Sale'], date=df['Transaction Date'])
    converted_amounts = []
    for i, row in df.iterrows():
        dt = datetime.strptime(row['Transaction Date'], "%b %d, %Y")
        try:
            amount = c.convert(row['Charged Amount'], row['Currency of Sale'], 'EUR', date=dt)
            converted_amounts.append(amount)
        except:
            # No data for: GHS and GBP; we took the average conversion rates of November/December
            if row['Currency of Sale'] == 'GHS':
                amount = row['Charged Amount'] * 0.1432
            elif row['Currency of Sale'] == 'COP':
                amount = row['Charged Amount'] * 0.0002249
            elif row['Currency of Sale'] == 'CRC':
                amount = row['Charged Amount'] * 0.0014
            else:
                amount = 'NaN'

            converted_amounts.append(amount)

    df['Amount (Merchant Currency)'] = converted_amounts

    # df['Transaction Date'] = datetime.strptime(f"{df['Transaction Date']}", "%Y-%m-%d")
    # df['Transaction Date'] = df['Transaction Date'].strftime("%b %d, %Y")
    # print(df[:5].to_string())

    # print(df.to_string())

    sales.append(df)

    # Note: the 67 dates say Nov 01 now while the 1-5 say Nov 1, so maybe need to fix this later

# for i, row in sales[-2].iterrows():
#     print(type(row['Amount (Merchant Currency)']))

sales_db = pd.concat(sales)
# print(sales_db[-61:-1].to_string())

# only use charges for com.vansteinengroentjes.apps.ddfive
sales_db = sales_db.rename(columns={'Product id': 'Product_id'})
sales_db = sales_db[(sales_db['Product_id'] == 'com.vansteinengroentjes.apps.ddfive')]
# print(sales_db.to_string())


# --------------- STATS CRASHES --------------------------------------------------
path_name = Path('assignment1_data').glob(r'stats_crashes*')
stats_crashes = []
for csv in path_name:
    df = pd.read_csv(csv, encoding='utf-16', sep=',')[:5]
    stats_crashes.append(df)

stats_db = pd.concat(stats_crashes)


# --------------- RATINGS COUNTRY --------------------------------------------------
path_name = Path('assignment1_data').glob(r'stats_ratings*country*')
ratings_countries = []
for csv in path_name:
    df = pd.read_csv(csv, encoding='utf-16', sep=',')
    ratings_countries.append(df)

ratings_countries_db = pd.concat(ratings_countries)
# print(ratings_countries_db[:20].to_string())


# --------------- DASHBOARD --------------------------------------------------
# Sales
days = []
months = []
daily_merchant_amount = {}
daily_transaction_count = {}
monthly_merchant_amount = {}
monthly_transaction_count = {}
for i, row in sales_db.iterrows():
    date = row['Transaction Date']
    if date not in days:
        days.append(date)
        daily_merchant_amount[date] = float(row['Amount (Merchant Currency)'])
        daily_transaction_count[date] = 1
    else:
        daily_merchant_amount[date] += float(row['Amount (Merchant Currency)'])
        daily_transaction_count[date] += 1

    if date[:3] not in months:
        months.append(date[:3])
        monthly_merchant_amount[date[:3]] = float(row['Amount (Merchant Currency)'])
        monthly_transaction_count[date[:3]] = 1
    else:
        monthly_merchant_amount[date[:3]] += float(row['Amount (Merchant Currency)'])
        monthly_transaction_count[date[:3]] += 1

# print months
# for date, merchant_amount in monthly_merchant_amount.items():
#     print(date, merchant_amount)
#
# for date, transaction_count in monthly_transaction_count.items():
#     print(date, transaction_count)

sales_source = models.ColumnDataSource(data=sales_db)
x = months

p1 = plotting.figure(x_range=x, title='Monthly Sales')
y = list(monthly_merchant_amount.values())
p1.vbar(x, top=y, width=0.5)

p2 = plotting.figure(x_range=x, title='Monthly Transaction Counts')
y = list(monthly_transaction_count.values())
p2.vbar(x, top=y, width=0.5)

x = days

p3 = plotting.figure(x_range=x, title='Daily Sales')
y = list(daily_merchant_amount.values())
p3.line(x, y)


p4 = plotting.figure(x_range=x, title='Daily Transaction Counts')
y = list(daily_transaction_count.values())
p4.line(x, y)

graphs = [p1, p2, p3, p4]
cols = []
row_num = 2
for i in range(0, len(graphs), row_num):
    r = layouts.row(graphs[i : i + row_num])
    cols.append(r)

plotting.show(layouts.column(cols))

crashes_source = models.ColumnDataSource(data=stats_db)
ratings_countries_source = models.ColumnDataSource(data=ratings_countries_db)


# print(stats_db)

# Keep only the sales apps we want to visualize

#
# datasets = [r'reviews*', r'sales*', r'stats_crashes*', r'stats_ratings*overview*', r'stats_ratings*country*']
#
#
# def make_full_db(regex):
#     path_name = Path('assignment1_data').glob(regex)
#     lst = []
#     for csv in path_name:
#         df = pd.read_csv(csv, encoding='utf-16', sep=',')
#         lst.append(df)
#     result = pd.concat(lst)
#     return result
#
#
# for dataset in datasets:
#     full_dataset = make_full_db(dataset)
#     print(full_dataset.to_string())
#
#
